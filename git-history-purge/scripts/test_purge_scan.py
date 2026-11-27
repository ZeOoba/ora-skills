"""Tests for purge_scan.py (stdlib unittest; gated by tools/run_skill_suites.sh).

All values are synthetic (555-01xx phones, made-up figures and names).
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "purge_scan.py")
sys.path.insert(0, HERE)
import purge_scan  # noqa: E402  (in-process checks where a git fixture cannot reach, e.g. a 256 MB member)
FIG = "123,457"
LIT = "Project Blue Heron"
PHONE = "614-555-0199"
TIP_FIG = "987,651"
ENV = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="t",
           GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "core.autocrlf=false"] + list(args), capture_output=True,
                          text=True, check=True, env=ENV).stdout


def show_bytes(repo, spec):
    """`git show` output as raw bytes (the text=True helper decodes with the locale code page)."""
    return subprocess.run(["git", "-C", repo, "show", spec], capture_output=True, check=True, env=ENV).stdout


def run(*args):
    return subprocess.run([sys.executable, "-I", SCRIPT] + list(args), capture_output=True, text=True, env=ENV)


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def rules_match(rules_path, text):
    """True if any rule in the file matches text (rules are regex: lines)."""
    for line in read_bytes(rules_path).splitlines():
        pat = line.rpartition(b"==>")[0]
        rx = re.compile(pat[6:]) if pat.startswith(b"regex:") else re.compile(re.escape(pat))
        if rx.search(text.encode()):
            return True
    return False


class Repo:
    def __init__(self, root):
        self.path = os.path.join(root, "repo")
        os.makedirs(self.path)
        git(self.path, "init", "-q", "-b", "main")

    def commit(self, files=None, delete=(), msg="c"):
        for path, text in (files or {}).items():
            full = os.path.join(self.path, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            if isinstance(text, bytes):
                with open(full, "wb") as fh:
                    fh.write(text)
                continue
            with open(full, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        for path in delete:
            git(self.path, "rm", "-q", "-r", path)
        git(self.path, "add", "-A")
        git(self.path, "commit", "-q", "--allow-empty", "-m", msg)

    def filter(self, rules, remove=r"(^|/)notes/"):
        git(self.path, "filter-repo", "--force", "--invert-paths", "--path-regex", remove,
            "--replace-text", rules, "--replace-message", rules)

    def history_text(self):
        return git(self.path, "log", "--all", "-p", "--format=%B") + git(
            self.path, "for-each-ref", "--format=%(contents)", "refs/tags")


class PurgeScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.r = Repo(self.tmp.name)
        self.cfg_path = os.path.join(self.tmp.name, "private", "purge-config.json")
        os.makedirs(os.path.dirname(self.cfg_path))
        self.rules = os.path.join(self.tmp.name, "private", "rules.txt")
        self.config()

    def tearDown(self):
        self.tmp.cleanup()

    def config(self, **over):
        cfg = {"remove_path_regex": r"(^|/)notes/", "values": [123457, 987651, 50000, 9876.54, 123456.5],
               "literals": [LIT], "phones": True, "public_phones": ["6145550100"]}
        cfg.update(over)
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)

    def scan(self):
        r = run("scan", self.r.path, self.cfg_path, self.rules)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def verify(self):
        return run("verify", self.r.path, self.cfg_path, self.rules)

    # ---- scan -------------------------------------------------------------------------
    def test_scan_finds_values_and_never_prints_them(self):
        self.r.commit({"docs/deal.md": "Price %s; call %s about %s.\n" % (FIG, PHONE, LIT)})
        self.r.commit({"docs/deal.md": "scrubbed\n"})
        r = self.scan()
        for secret in (FIG, LIT, PHONE, "123457", "6145550199"):
            self.assertNotIn(secret, r.stdout + r.stderr)
        for secret in (FIG, LIT, PHONE):
            self.assertTrue(rules_match(self.rules, secret), secret)

    def test_rule_present_at_tip_is_dropped_and_counted(self):
        self.r.commit({"docs/a.md": "old %s\n" % FIG})
        self.r.commit({"docs/a.md": "tip still has %s\n" % TIP_FIG})
        r = self.scan()
        self.assertFalse(rules_match(self.rules, TIP_FIG))
        self.assertTrue(rules_match(self.rules, FIG))
        self.assertIn("dropped (present at tip): 1", r.stdout)

    def test_round_and_below_threshold_figures_get_no_rule_and_are_counted(self):
        self.config(values=[50000, 5250, 12.5, 123457])
        self.r.commit({"docs/a.md": "budget 50,000 and 50000; fee 5,250; rate 12.50; noi 123,457\n"})
        self.r.commit({"docs/a.md": "x\n"})
        r = self.scan()
        for decoy in ("50,000", " 50000 ", "5,250", "12.50"):
            self.assertFalse(rules_match(self.rules, decoy), decoy)
        self.assertTrue(rules_match(self.rules, FIG))
        self.assertIn("NOT searched): 3", r.stdout)

    def test_all_figure_forms_found(self):
        self.r.commit({"data/m.json": '{"noi": 123457}\n',
                       "docs/b.md": "psf 9,876.54 raw 9876.54 cam 123,456.5 / 123456.5 / 123456.50 / 123,456.50\n"})
        self.r.commit({"data/m.json": "{}\n", "docs/b.md": "x\n"})
        self.scan()
        for form in ("123457", "9,876.54", "9876.54", "123,456.5", "123456.5", "123456.50", "123,456.50"):
            self.assertTrue(rules_match(self.rules, " %s " % form), form)

    def test_non_listed_extensions_are_scanned_by_content(self):
        self.r.commit({"r.xml": "<noi>%s</noi>\n" % FIG, "run.log": "%s\n" % LIT})
        self.r.commit(delete=["r.xml", "run.log"])
        r = self.scan()
        self.assertIn("found: numbers ", r.stdout)
        self.assertTrue(rules_match(self.rules, FIG))
        self.assertTrue(rules_match(self.rules, LIT))

    def test_blob_shared_by_removed_and_kept_path_is_scanned(self):
        self.r.commit({"notes/x.md": "noi %s\n" % FIG, "z/x.md": "noi %s\n" % FIG})
        self.r.commit(delete=["notes", "z"])
        self.scan()
        self.assertTrue(rules_match(self.rules, FIG))
        self.r.filter(self.rules)
        self.assertNotIn(FIG, self.r.history_text())
        self.assertEqual(self.verify().returncode, 0)

    def test_phone_only_in_commit_message_gets_rule_public_phone_does_not(self):
        self.r.commit({"a.md": "office 614-555-0100\n"}, msg="owner cell 614-555-0177")
        self.r.commit(delete=["a.md"])     # public phone now only in history, not at the tip
        self.scan()
        self.assertTrue(rules_match(self.rules, "614-555-0177"))
        self.assertFalse(rules_match(self.rules, "614-555-0100"))

    def test_figure_at_start_of_a_hash_at_tip_does_not_drop_the_rule(self):
        self.r.commit({"deal.txt": "price 123457\n"})
        self.r.commit({"deal.txt": "see commit 123457ab9f0e1d2c3b4a5f6e\n"})
        r = self.scan()
        self.assertIn("dropped (present at tip): 0", r.stdout)
        self.r.filter(self.rules)
        self.assertEqual("price [figure: private]\n", git(self.r.path, "show", "main~1:deal.txt"))
        self.assertEqual("see commit 123457ab9f0e1d2c3b4a5f6e\n", git(self.r.path, "show", "main:deal.txt"))

    def test_paths_file_lists_affected_paths(self):
        self.r.commit({"docs/d.md": "%s\n" % FIG, "docs/clean.md": "nothing\n"})
        self.r.commit({"docs/d.md": "x\n"})
        self.scan()
        self.assertEqual(read_bytes(self.rules + ".paths.txt").decode().split(), ["docs/d.md"])

    def test_missing_tip_ref_is_an_error(self):
        self.config(tip_ref="refs/heads/nope")
        self.r.commit({"a.md": "%s\n" % FIG})
        r = run("scan", self.r.path, self.cfg_path, self.rules)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertFalse(os.path.exists(self.rules))

    def test_literal_with_line_break_is_an_error(self):
        for lit in ("Acme Tower\nSuite 9", "Acme Tower\rSuite 9"):
            self.config(literals=[lit])
            self.r.commit({"a.md": "x\n"})
            r = run("scan", self.r.path, self.cfg_path, self.rules)
            self.assertEqual(r.returncode, 2, r.stdout)

    def test_figure_in_csv_row_and_json_array_is_found_and_purged(self):
        self.r.commit({"rentroll.csv": "BldgA,123457,2450001\n98001,123457\n", "arr.json": "[123457,98001]\n"})
        self.r.commit(delete=["rentroll.csv", "arr.json"])
        self.scan()
        self.assertTrue(rules_match(self.rules, "A,123457,2"))
        self.r.filter(self.rules)
        self.assertNotIn("123457", self.r.history_text())
        self.assertEqual(self.verify().returncode, 0)

    def test_verify_catches_a_value_the_rules_missed(self):
        self.r.commit({"a.md": "noi %s\n" % FIG}, msg="note about %s" % LIT)
        self.r.commit({"a.md": "x\n"})
        self._empty_rules()                       # as if the scan had missed everything
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("values still present: 2", v.stdout)
        self.assertNotIn(FIG, v.stdout + v.stderr)
        self.assertNotIn(LIT, v.stdout + v.stderr)

    def test_value_after_byte_8192_with_a_late_nul_is_still_text(self):
        self.r.commit({"big.txt": "noi %s\n" % FIG + "y" * 9000 + "\0\n"})
        self.r.commit({"big.txt": "x\n"})
        self.scan()
        self.assertTrue(rules_match(self.rules, FIG))

    def test_configured_min_integer_is_honoured(self):
        self.config(values=[5250], min_integer=1000)
        self.r.commit({"a.md": "fee 5,250\n"})
        self.r.commit({"a.md": "x\n"})
        self.scan()
        self.assertTrue(rules_match(self.rules, " 5,250 "))

    def test_phone_after_a_country_code_glued_to_text_is_found(self):
        self.r.commit({"a.md": "cell x1-614-555-0177 only\n"})
        self.r.commit({"a.md": "x\n"})
        r = self.scan()
        self.assertIn("phones 1", r.stdout)
        self.assertTrue(rules_match(self.rules, "x1-614-555-0177"))

    def test_many_refs_do_not_exceed_the_command_line(self):
        self.r.commit({"a.md": "noi %s\n" % FIG})
        self.r.commit({"a.md": "x\n"})
        head = git(self.r.path, "rev-parse", "HEAD").strip()
        lines = "".join("create refs/heads/branch-with-a-fairly-long-name-%04d %s\n" % (i, head) for i in range(800))
        subprocess.run(["git", "-C", self.r.path, "update-ref", "--stdin"], input=lines.encode(), check=True, env=ENV)
        self.scan()
        self.assertTrue(rules_match(self.rules, FIG))
        self.assertEqual(self.verify().returncode, 1)

    def test_annotated_tag_message_is_scanned_and_rewritten(self):
        self.r.commit({"a.md": "x\n"})
        git(self.r.path, "tag", "-a", "v1", "-m", "closed %s" % LIT)
        self.scan()
        self.assertTrue(rules_match(self.rules, LIT))
        self.r.filter(self.rules)
        self.assertNotIn(LIT, self.r.history_text())

    def test_boundaries_hashes_and_longer_numbers_untouched(self):
        decoys = ("sha deadbeef123,457 x; n 123,4579 x; m 1123,457 x; order 9614-555-01991 x; "
                  "id 614-555-01991 x; p 9614-555-0199 x; a 1,123,457 x; b 0.123457 x; c 123,457,000 x; "
                  "d 123457.12 x; h 123457ab9f x\n")
        self.r.commit({"docs/d.md": decoys + "real %s and %s\n" % (FIG, PHONE)})
        self.r.commit({"docs/d.md": "x\n"})
        self.scan()
        self.r.filter(self.rules)
        old = git(self.r.path, "show", "main~1:docs/d.md")
        self.assertIn(decoys, old)
        self.assertIn("real [figure: private] and [phone: private]", old)

    # ---- verify -----------------------------------------------------------------------
    def _empty_rules(self):
        with open(self.rules, "wb"):
            pass

    def test_verify_fails_on_removed_path_alone(self):
        self.r.commit({"notes/p.md": "nothing private\n"})
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("removed paths still reachable: 1", v.stdout)

    def test_verify_fails_on_blob_match_alone(self):
        self.r.commit({"a.md": "has %s\n" % FIG})
        self.r.commit({"a.md": "x\n"})
        self.scan()
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("blobs matching a rule: 1", v.stdout)
        self.assertIn("message hits: 0", v.stdout)
        self.assertNotIn(FIG, v.stdout + v.stderr)

    def test_verify_fails_on_message_match_alone(self):
        self.r.commit({"a.md": "x\n"}, msg="about %s" % LIT)
        self.scan()
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("blobs matching a rule: 0", v.stdout)
        self.assertIn("message hits: 1", v.stdout)
        self.assertNotIn(LIT, v.stdout + v.stderr)

    def test_full_purge_verifies_clean_and_keeps_tip_tree(self):
        self.r.commit({"docs/deal.md": "Price %s; call %s re %s\n" % (FIG, PHONE, LIT),
                       "notes/private.md": "%s\n" % LIT}, msg="add notes for %s" % LIT)
        self.r.commit({"docs/deal.md": "tip %s\n" % TIP_FIG}, delete=["notes"])
        self.scan()
        self.assertEqual(self.verify().returncode, 1)
        tree = git(self.r.path, "rev-parse", "main^{tree}")
        self.r.filter(self.rules)
        v = self.verify()
        self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
        self.assertEqual(tree, git(self.r.path, "rev-parse", "main^{tree}"))
        hist = self.r.history_text()
        for secret in (FIG, PHONE, LIT):
            self.assertNotIn(secret, hist)


    # ---- R4-05: residual search covers binary blobs and file names ----------------------
    def _rules_file(self, *lines):
        with open(self.rules, "wb") as fh:
            fh.write(b"".join(l.encode() + b"\n" for l in lines))

    def test_verify_finds_value_in_binary_blob(self):
        self.r.commit({"img.bin": b"\x00\x01\x02noi 123,457 end\x00\xff"})
        self.r.commit(delete=["img.bin"])
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("in binary blobs: 1", v.stdout)
        self.assertIn("in text objects: 0", v.stdout)
        self.assertNotIn(FIG, v.stdout + v.stderr)

    def test_verify_and_scan_find_values_in_file_and_directory_names(self):
        self.r.commit({"docs/%s.md" % LIT: "nothing\n", "deal-123457/a.md": "nothing\n"})
        self.r.commit(delete=["docs", "deal-123457"])
        s = self.scan()
        self.assertIn("literals found in file names: 1 (filter-repo text rules do not rename paths; "
                      "remove or rename by path)", s.stdout)
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("in file names: 2", v.stdout)
        self.assertIn("in text objects: 0", v.stdout)
        for secret in (LIT, "123457"):
            self.assertNotIn(secret, s.stdout + s.stderr + v.stdout + v.stderr)

    def test_binary_blob_and_file_name_at_tip_are_kept_at_tip(self):
        self.r.commit({"docs/%s.md" % LIT: "nothing\n", "img.bin": b"\x00tip 987,651\x00"})
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 0, v.stdout)
        self.assertIn("kept at tip (accepted): 2", v.stdout)

    # ---- R4-08: negative figures and configured compact phone numbers ------------------
    def test_negative_value_matches_parenthesised_and_minus_forms(self):
        self.config(values=[-123457], phones=False)
        self.r.commit({"pl.md": "loss (123,457) and net -123,457 and (123457.00)\n"})
        self.r.commit({"pl.md": "x\n"})
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("values still present: 1", v.stdout)
        self.scan()
        for form in ("(123,457)", "-123,457", "(123457.00)"):
            self.assertTrue(rules_match(self.rules, form), form)
        self.r.filter(self.rules)
        self.assertNotIn("123,457", self.r.history_text())
        self.assertNotIn("123457", self.r.history_text())
        self.assertEqual(self.verify().returncode, 0)

    def test_configured_phone_numbers_match_every_form_and_spare_longer_runs(self):
        self.config(phones=False, phone_numbers=["6145550123"])
        forms = ["614-555-0123", "(614) 555-0123", "(614)555-0123", "614.555.0123", "614 555 0123",
                 "6145550123", "+1 614-555-0123", "+16145550123", "1-614-555-0123", "+1 (614) 555-0123"]
        decoys = "long 96145550123 x; 61455501234 x; 614-555-01234 x\n"
        self.r.commit({"c.md": "".join("p %s x\n" % f for f in forms) + decoys})
        self.r.commit({"c.md": "x\n"})
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("values still present: 1", v.stdout)
        s = self.scan()
        self.assertIn("phones 1", s.stdout)
        self.assertNotIn("6145550123", s.stdout + s.stderr)
        self.r.filter(self.rules)
        old = git(self.r.path, "show", "main~1:c.md")
        self.assertEqual(old, "p [phone: private] x\n" * len(forms) + decoys)
        self.assertEqual(self.verify().returncode, 0)

    def test_phone_numbers_must_be_ten_digits(self):
        self.config(phone_numbers=["555-0123"])
        self.r.commit({"a.md": "x\n"})
        for mode in ("scan", "verify"):
            self._empty_rules()
            r = run(mode, self.r.path, self.cfg_path, self.rules)
            self.assertEqual(r.returncode, 2, mode + r.stdout)
            self.assertNotIn("555-0123", r.stdout + r.stderr)

    # ---- R4-07: each verify branch fails alone; tag-only reachability; min_integer -------
    def test_verify_fails_on_rule_hit_in_blob_alone(self):
        self.r.commit({"a.md": "has zq-marker-77\n"})
        self.r.commit({"a.md": "x\n"})
        self._rules_file("regex:zq-marker-77==>[gone]")
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        for line in ("removed paths still reachable: 0", "blobs matching a rule: 1", "message hits: 0",
                     "values still present: 0"):
            self.assertIn(line, v.stdout)

    def test_verify_fails_on_rule_hit_in_commit_message_alone(self):
        self.r.commit({"a.md": "x\n"}, msg="about zq-marker-77")
        self._rules_file("regex:zq-marker-77==>[gone]")
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        for line in ("removed paths still reachable: 0", "blobs matching a rule: 0", "message hits: 1",
                     "values still present: 0"):
            self.assertIn(line, v.stdout)

    def test_verify_fails_on_rule_hit_in_annotated_tag_message_alone(self):
        self.r.commit({"a.md": "x\n"})
        git(self.r.path, "tag", "-a", "v1", "-m", "closed zq-marker-77")
        self._rules_file("regex:zq-marker-77==>[gone]")
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        for line in ("removed paths still reachable: 0", "blobs matching a rule: 0", "message hits: 1",
                     "values still present: 0"):
            self.assertIn(line, v.stdout)

    def test_verify_fails_on_residual_hit_alone(self):
        self.r.commit({"a.md": "noi %s\n" % FIG})
        self.r.commit({"a.md": "x\n"})
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        for line in ("removed paths still reachable: 0", "blobs matching a rule: 0", "message hits: 0",
                     "values still present: 1", "in text objects: 1"):
            self.assertIn(line, v.stdout)

    def test_blob_reachable_only_from_a_tag_is_scanned(self):
        self.r.commit({"a.md": "x\n"})
        git(self.r.path, "checkout", "-q", "-b", "side")
        # G1-06: the tag-only commit's MESSAGE holds a phone found only by "phones": true (not a
        # configured value, so verify's residual search cannot catch a miss): scan must see it.
        self.r.commit({"s.md": "noi %s\n" % FIG}, msg="owner cell 614-555-0177")
        git(self.r.path, "tag", "only-tag")
        git(self.r.path, "checkout", "-q", "main")
        git(self.r.path, "branch", "-q", "-D", "side")
        self.scan()
        self.assertTrue(rules_match(self.rules, FIG))
        self.assertTrue(rules_match(self.rules, "614-555-0177"))
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("blobs matching a rule: 1", v.stdout)
        self.assertIn("message hits: 1", v.stdout)
        self.r.filter(self.rules)
        self.assertNotIn("614-555-0177", self.r.history_text())

    def test_residual_covers_annotated_tag_message(self):
        self.r.commit({"a.md": "x\n"})
        git(self.r.path, "tag", "-a", "v1", "-m", "closed %s" % LIT)
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("values still present: 1", v.stdout)
        self.assertNotIn(LIT, v.stdout + v.stderr)

    def test_residual_honours_min_integer(self):
        self.config(values=[5250])
        self.r.commit({"a.md": "fee 5,250\n"})
        self.r.commit({"a.md": "x\n"})
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 0, v.stdout)
        self.assertIn("values skipped (round thousands or below min_integer, NOT searched): 1", v.stdout)
        self.config(values=[5250], min_integer=1000)
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("values still present: 1", v.stdout)

    # ---- G1-08: more written forms of a configured phone number -------------------------
    def test_configured_phone_numbers_cover_slash_paren_dash_and_eleven_digit_forms(self):
        self.config(phones=False, phone_numbers=["6145550124"])
        forms = ["(614)-555-0124", "(614)/555-0124", "614/555-0124", "16145550124", "1 (614) 555-0124",
                 "1.614.555.0124", "+1/614/555/0124"]
        decoys = "long 96145550124 x; 616145550124 x; 614/555-01245 x; (614)-555-01245 x\n"
        self.r.commit({"c.md": "".join("p %s x\n" % f for f in forms) + decoys})
        self.r.commit({"c.md": "x\n"})
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("values still present: 1 (%d occurrences)" % len(forms), v.stdout)
        s = self.scan()
        self.assertIn("phones 1", s.stdout)
        self.assertNotIn("6145550124", s.stdout + s.stderr)
        self.r.filter(self.rules)
        old = git(self.r.path, "show", "main~1:c.md")
        self.assertEqual(old, "p [phone: private] x\n" * len(forms) + decoys)
        self.assertEqual(self.verify().returncode, 0)

    def test_verify_flags_configured_phone_digits_in_any_punctuated_span(self):
        """Verify's independent search strips punctuation inside a phone-shaped span, so a written
        form the rule pattern does not know (spaced dashes, brackets) still fails verify."""
        self.config(phones=False, phone_numbers=["6145550124"])
        self.r.commit({"c.md": "decoys 614 - 555 - 01245 x; 9614 - 555 - 0124 x\n"})
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 0, v.stdout)       # never inside a longer digit run
        self.r.commit({"d.md": "call 614 - 555 - 0124 or [614] 555 0124 now\n"})
        self.r.commit(delete=["d.md"])
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("values still present: 1 (2 occurrences)", v.stdout)
        self.assertNotIn("6145550124", v.stdout + v.stderr)

    # ---- G1-09: a figure right after letters (currency codes) ---------------------------
    def test_figure_glued_to_a_currency_code_is_found_but_hashes_are_not(self):
        self.config(values=[123457, 987653], phones=False)
        sha = "a1b2c3d4e5f6a7b8c9d0123457e1f2a3b4c5d6e7"      # 40 hex, figure inside
        keep = "sha %s x\nx deadbeef123457 y\nz deadbeef987653\n" % sha
        self.r.commit({"d.md": "price USD123,457\nbid CAD987653\n" + keep})
        self.r.commit({"d.md": keep})
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("values still present: 2 (2 occurrences)", v.stdout)
        s = self.scan()
        self.assertIn("found: numbers 2", s.stdout)
        self.assertIn("dropped (present at tip): 0", s.stdout)
        self.r.filter(self.rules)
        old = git(self.r.path, "show", "main~1:d.md")
        self.assertEqual(old, "price USD[figure: private]\nbid CAD[figure: private]\n" + keep)
        self.assertEqual(git(self.r.path, "show", "main:d.md"), keep)
        self.assertEqual(self.verify().returncode, 0)

    # ---- G1-16 (S32): the tip's ROOT tree is part of the tip ----------------------------
    def test_file_name_in_tip_root_tree_is_kept_at_tip(self):
        self.r.commit({"%s.md" % LIT: "nothing\n"})
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 0, v.stdout)
        self.assertIn("kept at tip (accepted): 1", v.stdout)
        self.assertIn("in file names: 0 (0 occurrences)", v.stdout)

    # ---- R2-10 / S41: a currency code after a figure; a hash that starts with a figure ----
    def test_figure_followed_by_a_currency_code_is_found_but_hash_like_runs_are_not(self):
        # Decided: a following run of 1-3 hex letters with no digit is text (EUR, CAD, ABC) and
        # matches; a run holding a digit (ab9f0e), or of 4+ hex letters ending at a non-letter
        # (ABCD, deadbeef), is a hash and does not. 4+ letters running on into a non-hex letter
        # (DEADLINE) is a word, so it matches.
        self.config(values=[123457, 987653], phones=False)
        keep = "h 123457ab9f0e x\nk 123457ABCD x\nm 987653deadbeef\nn 987653abc1 x\no 123,457Fa0 x\n"
        self.r.commit({"d.md": "price 123,457EUR\ncap 987653CAD\nfee 123457ABC\nby 987,653DEADLINE\n" + keep})
        self.r.commit({"d.md": keep})
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("values still present: 2 (4 occurrences)", v.stdout)
        s = self.scan()
        self.assertIn("found: numbers 4", s.stdout)          # 123,457 123457 987653 987,653
        self.assertIn("dropped (present at tip): 0", s.stdout)
        self.r.filter(self.rules)
        old = git(self.r.path, "show", "main~1:d.md")
        self.assertEqual(old, "price [figure: private]EUR\ncap [figure: private]CAD\nfee [figure: private]ABC\n"
                              "by [figure: private]DEADLINE\n" + keep)
        self.assertEqual(git(self.r.path, "show", "main:d.md"), keep)
        self.assertEqual(self.verify().returncode, 0)

    def test_verify_ignores_a_hash_that_starts_with_a_figure_only_in_history(self):
        # S41: verify's own search must keep the trailing-hash guard, not only the scan rules.
        self.config(values=[123457], phones=False)
        self.r.commit({"a.md": "see commit 123457ab9f0e1d2c3b4a5f6e\nand 123457deadbeef\n"})
        self.r.commit({"a.md": "x\n"})
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 0, v.stdout)
        self.assertIn("values still present: 0 (0 occurrences)", v.stdout)

    # ---- R2-13: Unicode dash / space phone separators; values in ref names ----------------
    def test_configured_phone_number_with_unicode_dashes_and_spaces_is_found_and_purged(self):
        self.config(phones=False, phone_numbers=["6145550124"])
        forms = ["614‐555‐0124", "614‑555‑0124", "614‒555‒0124",
                 "614–555–0124", "614—555—0124", "614―555―0124",
                 "614−555−0124", "614 555 0124", "614 555 0124",
                 "614 – 555 – 0124", "(614) 555–0124", "+1 614–555–0124"]
        decoys = "long 614–555–01245 x; 9614–555–0124 x\n"
        self.r.commit({"c.md": "".join("p %s x\n" % f for f in forms) + decoys})
        self.r.commit({"c.md": "x\n"})
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("values still present: 1 (%d occurrences)" % len(forms), v.stdout)
        s = self.scan()
        self.assertIn("phones 1", s.stdout)
        self.r.filter(self.rules)
        old = show_bytes(self.r.path, "main~1:c.md").decode("utf-8")
        self.assertEqual(old, "p [phone: private] x\n" * len(forms) + decoys)
        self.assertEqual(self.verify().returncode, 0)

    def test_found_phone_with_a_unicode_dash_gets_a_rule(self):
        self.config(values=[], phone_numbers=[])
        self.r.commit({"a.md": "x\n"}, msg="owner cell 614–555–0177; desk 614 555 0178")
        self.scan()
        self.assertTrue(rules_match(self.rules, "614–555–0177"))
        self.assertTrue(rules_match(self.rules, "614 555 0178"))

    def test_verify_fails_on_a_value_or_rule_hit_in_a_branch_or_tag_name(self):
        self.config(values=[123457, 987653], phones=False)
        self.r.commit({"a.md": "x\n"})
        git(self.r.path, "branch", "deal-123457")
        git(self.r.path, "tag", "noi-987,653")
        git(self.r.path, "branch", "zq-marker-77")
        self._rules_file("regex:zq-marker-77==>[gone]")
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("branch and tag names holding a value or matching a rule: 3", v.stdout)
        self.assertIn("REF-NAME refs/heads/deal-[private]", v.stdout)
        self.assertIn("REF-NAME refs/tags/noi-[private]", v.stdout)
        self.assertIn("REF-NAME refs/heads/[private]", v.stdout)
        for secret in ("123457", "987,653", "zq-marker-77"):
            self.assertNotIn(secret, v.stdout + v.stderr)
        for line in ("removed paths still reachable: 0", "blobs matching a rule: 0", "message hits: 0",
                     "values still present: 0"):
            self.assertIn(line, v.stdout)

    # ---- R2-09: values inside zip containers, UTF-16 text and PDF Flate streams ------------
    @staticmethod
    def _zip(members, compression=zipfile.ZIP_DEFLATED):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression) as z:
            for name, data in members.items():
                z.writestr(name, data)
        return buf.getvalue()

    @staticmethod
    def _pdf(*streams, trailer=b""):
        """A minimal PDF; each stream is (filter or None, raw stream bytes); trailer is added to the
        trailer dictionary."""
        out = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        for i, (flt, data) in enumerate(streams, 1):
            f = b" /Filter /" + flt.encode() if flt else b""
            out += b"%d 0 obj\n<< /Length %d%s >>\nstream\n" % (i, len(data), f) + data + b"\nendstream\nendobj\n"
        return out + b"trailer\n<< /Root 1 0 R" + trailer + b" >>\n%%EOF\n"

    def test_verify_finds_values_inside_zip_utf16_and_pdf_flate_blobs(self):
        self.config(values=[987653], literals=[LIT], phone_numbers=["6145550124"], phones=False)
        sheet = "<sst><si><t>NOI 987,653 owner 614-555-0124</t></si></sst>" + "<x/>" * 50
        xlsx = self._zip({"[Content_Types].xml": "<Types/>", "xl/sharedStrings.xml": sheet})
        inner = self._zip({"word/document.xml": "<w:t>%s</w:t>" % LIT + "<x/>" * 50})
        docx = self._zip({"word/document.xml": "<w/>", "word/embeddings/pack.docx": inner})
        u16le = "﻿NOI 987,653\r\n".encode("utf-16-le")
        u16be = ("deal %s call 614-555-0124\n" % LIT).encode("utf-16-be")          # no BOM
        pdf = self._pdf(("FlateDecode", zlib.compress(b"BT (NOI 987,653) Tj ET" + b" " * 200)))
        for blob in (xlsx, inner, docx, pdf):
            for raw in (b"987,653", b"987653", LIT.encode(), b"614-555-0124"):
                self.assertNotIn(raw, blob)
        self.r.commit({"a.md": "x\n"})
        files = {"deal.xlsx": xlsx, "memo.docx": docx, "le.txt": u16le, "be.txt": u16be, "om.pdf": pdf}
        for name, data in files.items():
            self.r.commit({name: data})
            self.r.commit(delete=[name])
            self._empty_rules()
            v = self.verify()
            self.assertEqual(v.returncode, 1, name + v.stdout)
            self.assertRegex(v.stdout, r"in binary blobs: [1-9]", name)
            self.assertIn("opaque blobs (NOT searched inside): 0", v.stdout, name)
            git(self.r.path, "reset", "-q", "--hard", "HEAD~2")
            git(self.r.path, "reflog", "expire", "--expire=now", "--all")
            git(self.r.path, "gc", "-q", "--prune=now")
        for secret in ("987,653", "987653", LIT, "6145550124", "614-555-0124"):
            self.assertNotIn(secret, v.stdout + v.stderr)

    def test_values_inside_a_tip_xlsx_are_kept_at_tip(self):
        self.config(values=[987653], phones=False)
        self.r.commit({"deal.xlsx": self._zip({"xl/s.xml": "<t>987,653</t>" + "<x/>" * 50})})
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 0, v.stdout)
        self.assertIn("kept at tip (accepted): 1", v.stdout)

    def test_blobs_verify_cannot_read_are_listed_as_opaque_with_path_and_commit(self):
        self.config(values=[987653], phones=False)
        enc = bytearray(self._zip({"xl/s.xml": "<t>secret-ish</t>"}, zipfile.ZIP_STORED))
        for sig, off in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):         # set the "encrypted" flag bit
            i = enc.index(sig)
            enc[i + off] |= 1
        png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + bytes(range(256))
        jpeg_pdf = self._pdf(("DCTDecode", b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + bytes(64)))
        self.r.commit({"locked.xlsx": bytes(enc), "scan.png": png, "photo.pdf": jpeg_pdf})
        commit = git(self.r.path, "rev-parse", "HEAD").strip()
        self.r.commit(delete=["locked.xlsx", "scan.png", "photo.pdf"])
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 0, v.stdout)        # opaque is reported, not a failure
        self.assertIn("opaque blobs (NOT searched inside): 3", v.stdout)
        lines = [l for l in v.stdout.splitlines() if l.startswith("OPAQUE ")]
        self.assertEqual(len(lines), 3, v.stdout)
        for path, why in (("locked.xlsx", "encrypted"), ("scan.png", "image"), ("photo.pdf", "DCTDecode")):
            line = [l for l in lines if (" path=%s " % path) in l]
            self.assertEqual(len(line), 1, v.stdout)
            self.assertIn(why, line[0])
            self.assertIn("commit=%s" % commit, line[0])
        self.assertTrue(v.stdout.rstrip().splitlines()[-1].startswith("OPAQUE "), v.stdout)

    # ---- R3-07 / R3-10: each layout verify decodes, checked one history at a time ----------
    def _verify_each_layout(self, layouts):
        """layouts: {name: {path: bytes}}. Each goes into its OWN history (added, then deleted, so
        never at the tip) and verify runs with no rules. Returns the names verify let through
        (exit 0, or a value printed)."""
        cfg = os.path.join(self.tmp.name, "private", "layouts.json")
        with open(cfg, "w", encoding="utf-8") as fh:
            json.dump({"values": [987653], "literals": [LIT], "phone_numbers": ["6145550124"], "phones": False}, fh)
        self._empty_rules()
        missed = []
        for n, (name, files) in enumerate(sorted(layouts.items())):
            r = Repo(os.path.join(self.tmp.name, "layout-%02d" % n))
            r.commit({"a.md": "x\n"})
            r.commit(files)
            r.commit(delete=list(files))
            v = run("verify", r.path, cfg, self.rules)
            out = v.stdout + v.stderr
            # R4-07 (P05/P08): a crash also exits 1; only verify's own count says the value was found.
            if v.returncode != 1 or "values still present: 1 (" not in v.stdout or "Traceback" in out or \
                    any(s in out for s in ("987,653", "987653", LIT, "6145550124", "555-0124")):
                missed.append("%s (exit %d)" % (name, v.returncode))
        return missed

    def test_verify_finds_values_in_layouts_pdf_embedded_files_tj_arrays_hex_strings_split_runs(self):
        # R3-07: each of these held the value and verify exited 0.
        xlsx = self._zip({"[Content_Types].xml": "<Types/>", "xl/sharedStrings.xml": "<sst><si><t>Price 987,653</t></si></sst>"})
        docx = self._zip({"[Content_Types].xml": "<Types/>", "word/document.xml":
                          '<w:document><w:body><w:p><w:r><w:t xml:space="preserve">Price 987,</w:t></w:r>'
                          '<w:r w:rsidR="00A1"><w:t>653</w:t></w:r></w:p></w:body></w:document>'})
        layouts = {
            "xlsx embedded in a PDF": {"memo.pdf": self._pdf(("FlateDecode", zlib.compress(xlsx)))},
            "PDF TJ array split inside the figure": {
                "memo.pdf": self._pdf(("FlateDecode", zlib.compress(b"BT /F1 12 Tf [(Price 987,)-15(653)] TJ ET")))},
            "PDF TJ array, escaped parentheses and octal": {
                "memo.pdf": self._pdf(("FlateDecode", zlib.compress(b"BT [(\\(NOI\\) 98)12(\\067,653)] TJ ET")))},
            "PDF hex string": {
                "memo.pdf": self._pdf(("FlateDecode", zlib.compress(b"BT /F1 12 Tf <507269636520393837363533> Tj ET")))},
            "PDF hex string outside every stream": {
                "memo.pdf": self._pdf((None, b"BT (cover) Tj ET"), trailer=b" /Info << /Title <4e4f4920393837363533> >>")},
            "PDF hex string in an unfiltered stream": {
                "memo.pdf": self._pdf((None, b"BT [<5072696365203938> 7 <37363533>] TJ ET"))},
            "docx with the figure split across runs": {"memo.docx": docx},
            "xlsx with (614) - 555-0124": {"deal.xlsx": self._zip({"xl/sharedStrings.xml": "<t>Call (614) - 555-0124</t>"})},
        }
        self.assertEqual(self._verify_each_layout(layouts), [])

    def test_verify_finds_values_in_each_decoded_layout_the_mutants_hid(self):
        # R3-10: PS01 / PS12 / PS13 / PS15 / PS22 / PS24 / PS25 / PS56 each turned verify's exit 1 into 0.
        two = self._pdf(("FlateDecode", zlib.compress(b"BT (cover page) Tj ET")),
                        ("FlateDecode", zlib.compress(b"BT (NOI 987,653) Tj ET")))
        layouts = {
            "PS01 value only in a zip member name": {"deal.zip": self._zip({"rent-roll-987653.csv": "a,b\n" + "x\n" * 40})},
            "PS12 UTF-16LE without a byte-order mark": {"export.csv": ("tenant,noi\r\nA,987653\r\n" * 3).encode("utf-16-le")},
            "PS13 UTF-16LE, half CJK, no byte-order mark": {
                "export.csv": (("Tenant 大楼租金大楼 " * 20) + " NOI 987,653\r\n").encode("utf-16-le")},
            "PS15 UTF-16 with a byte-order mark, no NUL in the first 8 KB": {
                "export.txt": b"\xff\xfe" + ("大楼租金" * 1100 + " NOI 987,653").encode("utf-16-le")},
            "PS22 PDF value in unfiltered XMP metadata (raw bytes only)": {
                "memo.pdf": self._pdf((None, b"<x:xmpmeta><dc:title>NOI 987,653</dc:title></x:xmpmeta>"))},
            "PS24 PDF stream under the /Fl abbreviation": {"memo.pdf": self._pdf(("Fl", zlib.compress(b"BT (NOI 987,653) Tj ET")))},
            "PS25 PDF value in the second stream": {"memo.pdf": two},
            "PS56 phone with narrow no-break spaces": {"c.md": "call 614 555 0124 today\n".encode("utf-8")},
        }
        self.assertEqual(self._verify_each_layout(layouts), [])

    def test_every_blob_verify_cannot_read_is_listed_opaque_with_its_reason(self):
        # R3-11: PS02-04 / PS08 / PS19 / PS20 / PS28-33 dropped one of these OPAQUE lines silently.
        self.config(values=[987653], phones=False)
        enc = bytearray(self._zip({"x.xml": "<t>hidden</t>"}, zipfile.ZIP_STORED))
        for sig, off in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):          # the "encrypted" flag bit
            i = enc.index(sig)
            enc[i + off] |= 1
        d64 = bytearray(self._zip({"s.xml": "<t>x</t>" * 20}))
        for sig, off in ((b"PK\x03\x04", 8), (b"PK\x01\x02", 10)):         # compression method 9 (Deflate64)
            i = d64.index(sig)
            d64[i + off:i + off + 2] = (9).to_bytes(2, "little")
        lvl1 = self._zip({"s.xml": "<t>x</t>" * 20})
        lvl3 = self._zip({"word/embeddings/pack.docx": self._zip({"embed/inner.xlsx": lvl1})})
        pad = bytes(300)
        expect = {      # path -> words its OPAQUE reason must hold
            "nested-encrypted.docx": "word/embeddings/inner.xlsx: encrypted zip member x.xml",
            "broken.xlsx": "unreadable zip",
            "deflate64.xlsx": "unknown compression or damaged s.xml",
            "too-deep.docx": "zip nested more than one level",
            "locked.pdf": "encrypted PDF",
            "damaged.pdf": "damaged Flate data",
            "nested.pdf": "PDF stream: PDF stream: PDF nested more than one level",
            "i.png": "image (PNG)", "i.jpg": "image (JPEG)", "i.gif": "image (GIF)", "i-le.tif": "image (TIFF)",
            "i-be.tif": "image (TIFF)", "i.bmp": "image (BMP)", "a.gz": "compressed (gzip)", "a.bz2": "compressed (bzip2)",
            "a.xz": "compressed (xz)", "a.7z": "compressed (7z)", "a.rar": "compressed (rar)",
            "old.xls": "legacy Office/OLE2 file",
        }
        files = {
            "nested-encrypted.docx": self._zip({"word/document.xml": "<w/>", "word/embeddings/inner.xlsx": bytes(enc)}),
            "broken.xlsx": b"PK\x03\x04" + bytes(200),
            "deflate64.xlsx": bytes(d64),
            "too-deep.docx": lvl3,
            "locked.pdf": self._pdf((None, b"\x8a\x13\xfe" + bytes(100)), trailer=b" /Encrypt 9 0 R"),
            "damaged.pdf": self._pdf(("FlateDecode", b"\x00\x01garbage" * 10)),
            "nested.pdf": self._pdf(("FlateDecode", zlib.compress(self._pdf(("FlateDecode", zlib.compress(
                self._pdf((None, b"BT (x) Tj ET")))))))),
            "i.png": b"\x89PNG\r\n\x1a\n" + pad, "i.jpg": b"\xff\xd8\xff\xe0" + pad, "i.gif": b"GIF89a" + pad,
            "i-le.tif": b"II*\x00" + pad, "i-be.tif": b"MM\x00*" + pad, "i.bmp": b"BM" + pad,
            "a.gz": b"\x1f\x8b\x08\x00" + pad, "a.bz2": b"BZh9" + pad, "a.xz": b"\xfd7zXZ\x00" + pad,
            "a.7z": b"7z\xbc\xaf\x27\x1c" + pad, "a.rar": b"Rar!\x1a\x07\x00" + pad,
            "old.xls": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + pad,
        }
        self.r.commit({"a.md": "x\n"})
        self.r.commit(files)
        self.r.commit(delete=list(files))
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 0, v.stdout)
        self.assertIn("opaque blobs (NOT searched inside): %d" % len(files), v.stdout)
        lines = [l for l in v.stdout.splitlines() if l.startswith("OPAQUE ")]
        for path, why in expect.items():
            line = [l for l in lines if (" path=%s " % path) in l]
            self.assertEqual(len(line), 1, "%s: %s" % (path, v.stdout))
            self.assertIn(why, line[0], path)

    def test_zip_member_over_the_size_cap_is_opaque(self):
        # PS05: a 256 MB member cannot sit in a fixture, so the cap is lowered for this check only.
        xlsx = self._zip({"xl/s.xml": "<t>987,653</t>" + "<x/>" * 50})
        with mock.patch.object(purge_scan, "MAX_MEMBER", 100):
            parts, why = purge_scan.expand(xlsx)
        self.assertEqual(why, {"zip member too large xl/s.xml"})
        self.assertFalse(any(b"987,653" in p for p in parts))

    def test_pdf_text_in_font_glyph_codes_is_opaque(self):
        # R3-07: text drawn with a font's own glyph codes (Identity-H) cannot be read: say so.
        pdf = self._pdf(("FlateDecode", zlib.compress(b"BT /F1 12 Tf <00340035> Tj ET")),
                        (None, b"<< /Type /Font /Subtype /Type0 /Encoding /Identity-H >>"))
        parts, why = purge_scan.expand(pdf)
        self.assertEqual(why, {"PDF text in font glyph codes (Identity-H/V)"})

    # ---- R4-07: PDF layouts the round-4 mutants P01-P08 hid -----------------------------------
    @staticmethod
    def _pdf_objs(*objs):
        """A minimal PDF from raw object bodies (see _stream)."""
        out = b"%PDF-1.4\n"
        for i, o in enumerate(objs, 1):
            out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
        return out + b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"

    @staticmethod
    def _stream(data, dict_extra=b"", nl=b"\n"):
        return b"<< /Length %d%s >>\nstream" % (len(data), dict_extra) + nl + data + b"\nendstream"

    def test_verify_finds_values_in_pdf_stream_and_string_layouts_round5(self):
        fl = b" /Filter /FlateDecode"
        text = zlib.compress(b"BT /F1 12 Tf (NOI 987,653) Tj ET")
        layouts = {
            "P01 'stream' keyword followed by CR LF": {"m.pdf": self._pdf_objs(self._stream(text, fl, b"\r\n"))},
            "P02 /Filter in array form [/FlateDecode]": {
                "m.pdf": self._pdf_objs(self._stream(text, b" /Filter [/FlateDecode]"))},
            "P06 nested balanced parentheses in a TJ piece": {"m.pdf": self._pdf_objs(self._stream(zlib.compress(
                b"BT [(Price (net) 987,)-15(653)] TJ ET"), fl))},
            "P07 literal split by a backslash-newline continuation": {"m.pdf": self._pdf_objs(self._stream(
                zlib.compress(b"BT (NOI 987,\\\n653) Tj ET"), fl))},
            "P07 literal split by a backslash-CRLF continuation": {"m.pdf": self._pdf_objs(self._stream(
                zlib.compress(b"BT (NOI 987,\\\r\n653) Tj ET"), fl))},
            "P05 odd-length hex string before the value": {"m.pdf": self._pdf_objs(self._stream(zlib.compress(
                b"BT <414> Tj (NOI 987,653) Tj ET"), fl))},
            "P08 octal escape before the value": {"m.pdf": self._pdf_objs(self._stream(zlib.compress(
                b"BT (caf\\351) Tj (NOI 987,653) Tj ET"), fl))},
        }
        for files in layouts.values():
            for raw in (b"987,653", b"987653"):
                self.assertNotIn(raw, files["m.pdf"])
        self.assertEqual(self._verify_each_layout(layouts), [])

    def test_verify_never_crashes_on_malformed_pdf_strings(self):
        # P05 / P08: an odd-length hex string or an octal escape crashed verify, and a crash exits 1
        # like a real find. With no value present verify must exit 0 with no traceback.
        self.config(values=[987653], phones=False)
        self.r.commit({"a.md": "x\n"})
        for name, content in (("odd.pdf", b"BT <414> Tj [<4e4f4> 12 (x)] TJ ET"),
                              ("octal.pdf", b"BT (caf\\351 \\0 \\777 \\8) Tj ET")):
            self.r.commit({name: self._pdf_objs(self._stream(zlib.compress(content), b" /Filter /FlateDecode"))})
            self.r.commit(delete=[name])
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
        self.assertNotIn("Traceback", v.stderr)
        self.assertIn("values still present: 0 (0 occurrences)", v.stdout)

    def test_identity_h_font_as_a_plain_object_is_opaque(self):
        # P04: the font dictionary sits outside every stream.
        pdf = self._pdf_objs(self._stream(zlib.compress(b"BT /F1 12 Tf <00340035> Tj ET"), b" /Filter /FlateDecode"),
                             b"<< /Type /Font /Subtype /Type0 /BaseFont /X /Encoding /Identity-H >>")
        self.assertEqual(purge_scan.expand(pdf)[1], {"PDF text in font glyph codes (Identity-H/V)"})

    def test_identity_h_font_only_inside_a_compressed_object_stream_is_opaque(self):
        # P03: the font dictionary is only inside a FlateDecode /ObjStm, so the raw bytes never show it.
        objstm = zlib.compress(b"5 0 << /Type /Font /Subtype /Type0 /Encoding /Identity-H >>")
        pdf = self._pdf_objs(self._stream(zlib.compress(b"BT /F1 12 Tf <00340035> Tj ET"), b" /Filter /FlateDecode"),
                             self._stream(objstm, b" /Type /ObjStm /N 1 /First 4 /Filter /FlateDecode"))
        self.assertNotIn(b"Identity", pdf)
        self.assertEqual(purge_scan.expand(pdf)[1], {"PDF text in font glyph codes (Identity-H/V)"})

    def test_zip_member_at_the_real_size_cap(self):
        # P18: a member whose central directory declares exactly MAX_MEMBER bytes is read; one byte
        # more is opaque. Only the declared size is forged (stored, the real data is small).
        def forged(size):
            z = bytearray(self._zip({"xl/s.xml": "<t>987,653</t>"}, zipfile.ZIP_STORED))
            i = z.index(b"PK\x01\x02")
            z[i + 24:i + 28] = size.to_bytes(4, "little")
            return bytes(z)
        parts, why = purge_scan.expand(forged(256 << 20))
        self.assertEqual(why, set())
        self.assertTrue(any(b"987,653" in p for p in parts))
        parts, why = purge_scan.expand(forged((256 << 20) + 1))
        self.assertEqual(why, {"zip member too large xl/s.xml"})
        self.assertFalse(any(b"987,653" in p for p in parts))

    def test_opaque_line_masks_values_in_its_path_and_reason(self):
        # PS39 / PS40: the OPAQUE line printed the path and an encrypted member's name unmasked.
        self.config(values=[987653], phones=False)
        enc = bytearray(self._zip({"noi-987653.xml": "<t>hidden</t>"}, zipfile.ZIP_STORED))
        for sig, off in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
            i = enc.index(sig)
            enc[i + off] |= 1
        self.r.commit({"a.md": "x\n"})
        self.r.commit({"d/noi-987653.png": b"\x89PNG\r\n\x1a\n" + bytes(200), "d/locked.xlsx": bytes(enc)})
        self.r.commit(delete=["d"])
        self._empty_rules()
        v = self.verify()
        self.assertNotIn("987653", v.stdout + v.stderr)
        self.assertIn(" path=d/noi-[private].png ", v.stdout)
        self.assertIn("reason=encrypted zip member noi-[private].xml", v.stdout)

    # ---- R3-13: PS53 (U+202F in the scan rule), PS46 (7 hex characters before a figure) ------
    def test_scan_rule_purges_a_configured_phone_written_with_narrow_no_break_spaces(self):
        self.config(phones=False, phone_numbers=["6145550124"])
        self.r.commit({"c.md": "p 614 555 0124 x\np (614) 555-0124 x\n"})
        self.r.commit({"c.md": "x\n"})
        self.scan()
        self.r.filter(self.rules)
        self.assertEqual(show_bytes(self.r.path, "main~1:c.md").decode("utf-8"), "p [phone: private] x\n" * 2)
        self.assertEqual(self.verify().returncode, 0)

    def test_figure_right_after_seven_hex_characters_is_part_of_a_hash(self):
        self.config(values=[987653], phones=False)
        self.r.commit({"a.md": "id a1b2c3d987653 x\nsha abcdefa987,653 x\n"})
        self.r.commit({"a.md": "x\n"})
        s = self.scan()
        self.assertIn("found: numbers 0", s.stdout)
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 0, v.stdout)
        self.assertIn("values still present: 0 (0 occurrences)", v.stdout)

    # ---- R3-05: refs/notes ----------------------------------------------------------------
    def test_verify_and_scan_read_notes_refs(self):
        self.config(values=[987653], phones=False)
        self.r.commit({"a.md": "x\n"})
        git(self.r.path, "notes", "add", "-m", "agreed zq-marker-77 and 987,653", "HEAD")
        git(self.r.path, "notes", "--ref", "refs/notes/deal-987653", "add", "-m", "x", "HEAD")
        s = self.scan()
        self.assertIn("found: numbers 1", s.stdout)
        self._rules_file("regex:zq-marker-77==>[gone]")
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("notes refs read: 2", v.stdout)
        self.assertIn("blobs matching a rule: 1", v.stdout)
        self.assertIn("REF-NAME refs/notes/deal-[private]", v.stdout)
        self.assertNotIn("987653", v.stdout + v.stderr)

    def test_rule_match_in_a_notes_commit_message_fails_verify(self):
        # P22: the message is on a commit of refs/notes/commits only (no branch or tag reaches it),
        # and the rule is not a configured value, so only the message check can catch it.
        self.config(values=[987653], phones=False)
        self.r.commit({"a.md": "x\n"})
        git(self.r.path, "notes", "add", "-m", "plain note", "HEAD")
        tree = git(self.r.path, "rev-parse", "refs/notes/commits^{tree}").strip()
        parent = git(self.r.path, "rev-parse", "refs/notes/commits").strip()
        c = git(self.r.path, "commit-tree", tree, "-p", parent, "-m", "notes: zq-marker-77 agreed").strip()
        git(self.r.path, "update-ref", "refs/notes/commits", c)
        self._rules_file("regex:zq-marker-77==>[gone]")
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        for line in ("removed paths still reachable: 0", "blobs matching a rule: 0", "message hits: 1",
                     "values still present: 0", "names holding a value or matching a rule: 0"):
            self.assertIn(line, v.stdout)

    def test_opaque_blob_only_in_a_notes_ref_names_its_note_path_commit_and_ref(self):
        # P21: a PNG stored only as a note: its OPAQUE line must say where it lives, not "(unreachable)".
        self.config(values=[987653], phones=False)
        self.r.commit({"a.md": "x\n"})
        head = git(self.r.path, "rev-parse", "HEAD").strip()
        png = subprocess.run(["git", "-C", self.r.path, "hash-object", "-w", "--stdin"], input=b"\x89PNG\r\n\x1a\n" +
                             bytes(300), capture_output=True, check=True, env=ENV).stdout.decode().strip()
        git(self.r.path, "notes", "add", "-C", png, "HEAD")
        notes_commit = git(self.r.path, "rev-parse", "refs/notes/commits").strip()
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 0, v.stdout)
        lines = [l for l in v.stdout.splitlines() if l.startswith("OPAQUE ")]
        self.assertEqual(lines, ["OPAQUE %s path=%s commit=%s ref=refs/notes/commits reason=image (PNG)"
                                 % (png, head, notes_commit)], v.stdout)

    # ---- round 6: OPAQUE ref= (L02, L03, L04, L05, correctness F5) ---------------------------
    def _git_at(self, date, *args):
        """git with fixed author and committer dates, so log order never depends on the clock."""
        env = dict(ENV, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        subprocess.run(["git", "-C", self.r.path] + list(args), capture_output=True, check=True, env=env)

    def _hash(self, data):
        return subprocess.run(["git", "-C", self.r.path, "hash-object", "-w", "--stdin"], input=data,
                              capture_output=True, check=True, env=ENV).stdout.decode().strip()

    def _opaque_lines(self):
        self._empty_rules()
        v = self.verify()
        self.assertNotIn("Traceback", v.stderr)
        self.assertNotIn("987653", v.stdout + v.stderr)
        return v, sorted(l for l in v.stdout.splitlines() if l.startswith("OPAQUE "))

    def test_round6_opaque_ref_is_the_ref_that_reaches_the_commit_not_the_newest_ref(self):
        # L03 / L02: the PNG is only on refs/heads/side; a newer notes commit is the first thing log
        # prints, so a ref= that sticks to the first ref seen names refs/notes/commits instead.
        self.config(values=[987653], phones=False)
        with open(os.path.join(self.r.path, "a.md"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("x\n")
        self._git_at("2020-01-01T00:00:00Z", "add", "-A")
        self._git_at("2020-01-01T00:00:00Z", "commit", "-q", "-m", "a")
        self._git_at("2020-01-02T00:00:00Z", "switch", "-q", "-c", "side")
        with open(os.path.join(self.r.path, "scan.png"), "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n" + bytes(300))
        self._git_at("2020-01-02T00:00:00Z", "add", "-A")
        self._git_at("2020-01-02T00:00:00Z", "commit", "-q", "-m", "png on side")
        png_commit = git(self.r.path, "rev-parse", "HEAD").strip()
        png = git(self.r.path, "rev-parse", "HEAD:scan.png").strip()
        self._git_at("2020-01-03T00:00:00Z", "rm", "-q", "scan.png")
        self._git_at("2020-01-03T00:00:00Z", "commit", "-q", "-m", "drop png")
        self._git_at("2020-01-04T00:00:00Z", "switch", "-q", "main")
        self._git_at("2020-01-09T00:00:00Z", "notes", "add", "-m", "plain note", "HEAD")
        first = git(self.r.path, "log", "--format=%S", "--source", "--branches", "--tags",
                    "--glob=refs/notes/*").split()[0]
        self.assertEqual(first, "refs/notes/commits")          # the fixture really puts notes first
        v, lines = self._opaque_lines()
        self.assertEqual(lines, ["OPAQUE %s path=scan.png commit=%s ref=refs/heads/side reason=image (PNG)"
                                 % (png, png_commit)], v.stdout)

    def test_round6_opaque_ref_name_holding_a_value_is_masked(self):
        # L05: ref= was printed unmasked; only refs/notes/commits (nothing to mask) was ever tested.
        self.config(values=[987653], phones=False)
        self.r.commit({"a.md": "x\n"})
        git(self.r.path, "switch", "-q", "-c", "deal-987653")
        self.r.commit({"scan.png": b"\x89PNG\r\n\x1a\n" + bytes(300)})
        commit = git(self.r.path, "rev-parse", "HEAD").strip()
        png = git(self.r.path, "rev-parse", "HEAD:scan.png").strip()
        git(self.r.path, "switch", "-q", "main")
        v, lines = self._opaque_lines()
        self.assertEqual(lines, ["OPAQUE %s path=scan.png commit=%s ref=refs/heads/deal-[private] reason=image (PNG)"
                                 % (png, commit)], v.stdout)

    def test_round6_opaque_blob_reached_by_a_tag_on_a_blob_or_tree_names_the_tag(self):
        # Correctness F5: a tag pointing straight at a blob, or at a tree holding it, publishes the
        # blob on a tag push, but its OPAQUE line said commit=(unreachable) ref=(none). L04: a blob
        # nothing reaches still says ref=(none).
        self.config(values=[987653], phones=False)
        self.r.commit({"a.md": "x\n"})
        png1, png2, png3 = (self._hash(b"\x89PNG\r\n\x1a\n" + bytes(n)) for n in (300, 301, 302))
        git(self.r.path, "tag", "blobtag", png1)                               # lightweight tag -> blob
        mk = lambda text: subprocess.run(["git", "-C", self.r.path, "mktree"], input=text.encode(),
                                         capture_output=True, check=True, env=ENV).stdout.decode().strip()
        inner = mk("100644 blob %s\tscan-987653.png\n" % png2)
        outer = mk("040000 tree %s\td\n" % inner)
        git(self.r.path, "tag", "-a", "-m", "t", "treetag", outer)              # annotated tag -> tree
        v, lines = self._opaque_lines()
        self.assertEqual(v.returncode, 1, v.stdout)                            # the tree's file name holds the value
        self.assertEqual(lines, sorted([
            "OPAQUE %s path=(none) commit=(none) ref=refs/tags/blobtag reason=image (PNG)" % png1,
            "OPAQUE %s path=d/scan-[private].png commit=(none) ref=refs/tags/treetag reason=image (PNG)" % png2,
            "OPAQUE %s path=(none) commit=(unreachable) ref=(none) reason=image (PNG)" % png3]), v.stdout)

    def test_round7_opaque_blob_stored_by_a_branch_commit_keeps_that_origin_when_also_tagged(self):
        # S005 / S006: a blob a branch commit stored is ALSO tagged directly, and the tree holding a
        # second one is tagged. The commit origin must stand: the tag fallback is only for a blob no
        # commit stored (it used to overwrite path and commit with (none)).
        self.config(values=[987653], phones=False)
        os.makedirs(os.path.join(self.r.path, "d"))
        with open(os.path.join(self.r.path, "scan.png"), "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n" + bytes(300))
        with open(os.path.join(self.r.path, "d", "plan.png"), "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n" + bytes(301))
        self._git_at("2020-01-01T00:00:00Z", "add", "-A")
        self._git_at("2020-01-01T00:00:00Z", "commit", "-q", "-m", "pngs")
        commit = git(self.r.path, "rev-parse", "HEAD").strip()
        png, png2 = (git(self.r.path, "rev-parse", "HEAD:" + p).strip() for p in ("scan.png", "d/plan.png"))
        git(self.r.path, "tag", "zz-blobtag", png)                                    # tag -> blob
        git(self.r.path, "tag", "zz-treetag", git(self.r.path, "rev-parse", "HEAD:d").strip())   # tag -> tree
        self._git_at("2020-01-02T00:00:00Z", "rm", "-q", "-r", "scan.png", "d")        # not at tip
        self._git_at("2020-01-02T00:00:00Z", "commit", "-q", "-m", "drop pngs")
        v, lines = self._opaque_lines()
        self.assertEqual(lines, sorted([
            "OPAQUE %s path=scan.png commit=%s ref=refs/heads/main reason=image (PNG)" % (png, commit),
            "OPAQUE %s path=d/plan.png commit=%s ref=refs/heads/main reason=image (PNG)" % (png2, commit)]),
            v.stdout)

    def test_round7_opaque_blob_on_a_commit_only_a_tag_reaches_names_the_tag(self):
        # S008: a release tag on a detached commit is the only ref reaching it; a tag push publishes
        # the blob, so OPAQUE must name that commit and tag, never commit=(unreachable) ref=(none).
        self.config(values=[987653], phones=False)
        with open(os.path.join(self.r.path, "a.md"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("x\n")
        self._git_at("2020-01-01T00:00:00Z", "add", "-A")
        self._git_at("2020-01-01T00:00:00Z", "commit", "-q", "-m", "a")
        self._git_at("2020-01-02T00:00:00Z", "checkout", "-q", "--detach")
        with open(os.path.join(self.r.path, "scan.png"), "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n" + bytes(300))
        self._git_at("2020-01-02T00:00:00Z", "add", "-A")
        self._git_at("2020-01-02T00:00:00Z", "commit", "-q", "-m", "release")
        commit = git(self.r.path, "rev-parse", "HEAD").strip()
        png = git(self.r.path, "rev-parse", "HEAD:scan.png").strip()
        self._git_at("2020-01-02T00:00:00Z", "tag", "-a", "v1", "-m", "release")
        self._git_at("2020-01-03T00:00:00Z", "checkout", "-q", "main")
        v, lines = self._opaque_lines()
        self.assertEqual(lines, ["OPAQUE %s path=scan.png commit=%s ref=refs/tags/v1 reason=image (PNG)"
                                 % (png, commit)], v.stdout)

    def test_round7_unreachable_opaque_blob_is_found_by_the_documented_command(self):
        # Scope F2: commit=(unreachable) ref=(none) is documented as "no branch, tag or notes ref
        # reaches it, but it is still here"; the find-object command the help prints names the holder.
        self.config(values=[987653], phones=False)
        with open(os.path.join(self.r.path, "a.md"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("x\n")
        self._git_at("2020-01-01T00:00:00Z", "add", "-A")
        self._git_at("2020-01-01T00:00:00Z", "commit", "-q", "-m", "a")
        self._git_at("2020-01-02T00:00:00Z", "checkout", "-q", "--detach")
        with open(os.path.join(self.r.path, "scan.png"), "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n" + bytes(300))
        self._git_at("2020-01-02T00:00:00Z", "add", "-A")
        self._git_at("2020-01-02T00:00:00Z", "commit", "-q", "-m", "pull request only")
        commit = git(self.r.path, "rev-parse", "HEAD").strip()
        png = git(self.r.path, "rev-parse", "HEAD:scan.png").strip()
        git(self.r.path, "update-ref", "refs/pull/1/head", commit)
        self._git_at("2020-01-03T00:00:00Z", "checkout", "-q", "main")
        v, lines = self._opaque_lines()
        self.assertEqual(lines, ["OPAQUE %s path=(none) commit=(unreachable) ref=(none) reason=image (PNG)" % png],
                         v.stdout)
        doc = run("--help").stdout
        self.assertIn("commit=(unreachable) ref=(none)", doc)
        self.assertIn('`git log --all --reflog --source\n         --find-object=<blob> --format="%H %S"`', doc)
        held = git(self.r.path, "log", "--all", "--reflog", "--source", "--find-object=" + png, "--format=%H %S")
        self.assertEqual(held.split(), [commit, "refs/pull/1/head"])

    # ---- round 6: PDF string decoding (M01, M06, M12, M13, M14) -------------------------------
    def _pdf_found(self, content):
        """True if verify's search finds 987653 or 614-555-0124 in a PDF whose one Flate stream is
        content. The raw content never holds the value, so only the decoded strings can."""
        pats, _ = purge_scan.value_patterns({"values": [987653], "phone_numbers": ["6145550124"]})
        for p in pats:
            self.assertFalse(p.search(content), content)
        pdf = self._pdf_objs(self._stream(zlib.compress(content), b" /Filter /FlateDecode"))
        parts, _ = purge_scan.expand(pdf)
        return any(p.search(x) for p in pats for x in parts)

    def test_round6_pdf_escapes_n_r_t_b_f_are_decoded(self):
        # M01: "\t" read as the letter t joined the phone's digit groups into one word; "\b" read as
        # the letter b made seven hex characters, so the figure after it looked like part of a hash.
        for esc in (b"n", b"r", b"t", b"f"):
            self.assertTrue(self._pdf_found(b"BT (Call 614\\" + esc + b"555\\" + esc + b"0124) Tj ET"), esc)
        for esc in (b"b", b"f"):
            self.assertTrue(self._pdf_found(b"BT (ref abcdef\\" + esc + b"\\071\\070\\067\\066\\065\\063) Tj ET"), esc)

    def test_round6_pdf_comment_inside_a_tj_array_is_skipped(self):
        # M06: a comment holding "]" ended the array early and split the figure.
        self.assertTrue(self._pdf_found(b"BT [(NOI 987,) % ](x\n (653)] TJ ET"))

    def test_round6_pdf_percent_in_inline_image_data_hides_no_later_string(self):
        # M06 (code): a "%" in binary inline image data on a content stream with no line breaks
        # swallowed every string after it.
        self.assertTrue(self._pdf_found(b"BT (a) Tj ET BI /W 1 /H 1 /CS /G /BPC 8 ID %\x01 EI BT (NOI 987\\054653) Tj ET"))

    def test_round6_pdf_hex_string_with_tab_newline_or_nul_inside(self):
        # M12: whitespace other than a space inside a hex string crashed the decode; NUL is PDF
        # whitespace too and left the hex string unread.
        for c in (b"BT <414\t> Tj <393\t83736\n3533> Tj ET", b"BT <3938\x003736\x003533> Tj ET",
                  b"BT <3938\r\n3736\x0c3533> Tj ET"):
            self.assertTrue(self._pdf_found(c), c)

    def test_round6_pdf_identity_v_font_is_opaque(self):
        # M13: a vertical (Identity-V) font was only covered by the Identity-H tests.
        pdf = self._pdf_objs(self._stream(zlib.compress(b"BT /F1 12 Tf <00340035> Tj ET"), b" /Filter /FlateDecode"),
                             b"<< /Type /Font /Subtype /Type0 /BaseFont /X /Encoding /Identity-V >>")
        self.assertEqual(purge_scan.expand(pdf)[1], {"PDF text in font glyph codes (Identity-H/V)"})
        for other in (b"/Identity-Vx", b"/Identity-HV1"):
            pdf2 = self._pdf_objs(self._stream(b"BT (x) Tj ET"), b"<< /Encoding " + other + b" >>")
            self.assertEqual(purge_scan.expand(pdf2)[1], set(), other)

    def test_round6_pdf_unterminated_tj_array(self):
        # M14: the pieces of an array still open at the end of the stream are joined too.
        self.assertTrue(self._pdf_found(b"BT [(Price 987,)-15(653)"))
        # M14 (code): an unclosed "[" glued every later string to the one before it, so a figure
        # after a digit ("123" + "987,653") read as a longer number.
        self.assertTrue(self._pdf_found(b"BT [(NOI 123) Tj (987\\054653) Tj ET"))
        self.assertTrue(self._pdf_found(b"BT [(Unit 4) Tj (614\\055555\\0550124) Tj ET"))

    def test_round7_pdf_hex_strings_in_an_unterminated_array_stand_alone(self):
        # S025: the hex twin of the case above. A hex string inside an open "[" must also be a line
        # of its own, or "NOI 123" + "987,653" glue into one longer number and hide the figure.
        self.assertTrue(self._pdf_found(b"BT [<4e4f4920313233> Tj <3938372c363533> Tj ET"))
        self.assertTrue(self._pdf_found(b"BT [<556e69742034> Tj <3631342d3535352d30313234> Tj ET"))

    def test_round7_pdf_strings_lists_each_line_once(self):
        # S023: both readings (with and without "%" comments) usually give the same lines. Each must
        # appear once: a repeated line puts a string's end next to its own start, so "0124 614-555"
        # read twice holds "614-555\n0124", a phone number the PDF never shows.
        self.assertEqual(purge_scan.pdf_strings(b"BT (a) Tj (b) Tj (a) Tj ET"), b"a\nb")
        self.assertFalse(self._pdf_found(b"BT (0124 614-555) Tj ET"))
        self.assertFalse(self._pdf_found(b"BT (0124 Call 614 555) Tj ET"))

    def test_round8_pdf_strings_keep_their_order(self):
        # S031: sorting the lines put " 614-555" (a later string) before "0124 Call", so the phone
        # read whole in a PDF that never shows it. The lines keep the order they appear in.
        self.assertEqual(purge_scan.pdf_strings(b"BT (b) Tj (a) Tj ET"), b"b\na")
        self.assertFalse(self._pdf_found(b"BT (0124 Call) Tj ( 614-555) Tj ET"))

    def test_round8_pdf_odd_hex_string_final_digit_is_padded_with_zero(self):
        # S037: PDF 32000-1 7.3.4.3, an odd final hex digit is followed by an implied 0, not dropped.
        self.assertEqual(purge_scan.pdf_strings(b"<414>"), b"A@")
        pats, _ = purge_scan.value_patterns({"values": [], "phone_numbers": ["6145550120"]})
        content = b"BT <3631342d3535352d303132 3> Tj ET"            # "614-555-012" + "3" -> "614-555-0120"
        self.assertFalse(any(p.search(content) for p in pats))
        parts, _ = purge_scan.expand(self._pdf_objs(self._stream(zlib.compress(content), b" /Filter /FlateDecode")))
        self.assertTrue(any(p.search(x) for p in pats for x in parts))
        self.assertFalse(self._pdf_found(b"BT <3938373635333> Tj ET"))   # "9876530": a longer number

    def test_round8_pdf_nested_array_joins_at_the_outermost_bracket(self):
        # S038: an inner "]" must not end the outer array's join.
        self.assertTrue(self._pdf_found(b"BT [(987,) [] (653)] TJ ET"))
        self.assertTrue(self._pdf_found(b"BT [(987,) [ ] (653)] TJ ET"))

    # ---- round 8 (R7-03): UTF-16 strings, object streams, re-mapped font codes ---------------
    U16 = b"\xfe\xff" + "NOI 987653".encode("utf-16-be")

    def _found_in(self, pdf):
        pats, _ = purge_scan.value_patterns({"values": [987653], "phone_numbers": ["6145550124"]})
        self.assertFalse(any(p.search(pdf) for p in pats), pdf)
        parts, why = purge_scan.expand(pdf)
        return any(p.search(x) for p in pats for x in parts), why

    def test_round8_pdf_utf16_text_strings_are_decoded(self):
        # R7-03: a PDF text string (/Title, a form /V, an annotation) starting with the byte-order mark
        # FE FF (or FF FE) is UTF-16. Its bytes alone hold no figure, so its decoding is searched too.
        octal = b"".join(b"\\%03o" % c for c in self.U16)
        le = b"\xff\xfe" + "NOI 987653".encode("utf-16-le")
        for title in (b"<" + self.U16.hex().encode() + b">", b"(" + octal + b")", b"<" + le.hex().encode() + b">",
                      b"(" + b"".join(b"\\%03o" % c for c in le) + b")"):
            pdf = self._pdf_objs(b"<< /Type /Catalog >>", b"<< /Title " + title + b" /Producer (t) >>")
            self.assertEqual(self._found_in(pdf), (True, set()), title)
        self.assertIn("NOI 987653".encode(), purge_scan.pdf_strings(b"<" + self.U16.hex().encode() + b">"))
        # pieces of an array of UTF-16 strings are joined as text
        arr = b"[<" + (b"\xfe\xff" + "NOI 987,".encode("utf-16-be")).hex().encode() + b"> <" + \
              (b"\xfe\xff" + "653".encode("utf-16-be")).hex().encode() + b">]"
        self.assertEqual(self._found_in(self._pdf_objs(b"<< /Subject " + arr + b" >>")), (True, set()))
        # an odd-length or broken UTF-16 string never crashes
        for s in (b"<FEFF00>", b"<FFFE>", b"<FEFF>", b"<FEFFD800>", b"(\\376\\377\\000)"):
            purge_scan.pdf_strings(s)
        self.assertEqual(purge_scan.pdf_utf16(b"\xfe\xff\x00A\x00"), b"A")       # an odd last byte is dropped
        self.assertIsNone(purge_scan.pdf_utf16(b"\x00A"))

    def test_round8_pdf_form_value_in_an_object_stream_is_read(self):
        # R7-03: PDF 1.5+ writers put most dictionaries, form fields among them, in a compressed
        # /ObjStm; the field's /V value is read there, as plain text and as UTF-16.
        for v in (b"(987,653)", b"<" + self.U16.hex().encode() + b">"):
            objstm = zlib.compress(b"5 0 << /FT /Tx /T (amount) /V " + v + b" >>")
            pdf = self._pdf_objs(b"<< /Type /Catalog /AcroForm << /Fields [5 0 R] >> >>",
                                 self._stream(objstm, b" /Type /ObjStm /N 1 /First 4 /Filter /FlateDecode"))
            self.assertEqual(self._found_in(pdf), (True, set()), v)

    def test_round8_verify_finds_utf16_pdf_strings_in_history(self):
        # R7-03 end to end (repro gate297r7-correctness/pdf_utf16.py): each case held the figure
        # and verify exited 0 with nothing opaque.
        u16hex = b"<" + self.U16.hex().encode() + b">"
        objstm = zlib.compress(b"5 0 << /FT /Tx /T (amount) /V " + u16hex + b" >>")
        layouts = {
            "info title hex UTF-16BE": {"s.pdf": self._pdf_objs(b"<< /Type /Catalog >>", b"<< /Title " + u16hex + b" >>")},
            "info title literal UTF-16BE": {"s.pdf": self._pdf_objs(
                b"<< /Type /Catalog >>", b"<< /Title (" + b"".join(b"\\%03o" % c for c in self.U16) + b") >>")},
            "form value in an object stream": {"s.pdf": self._pdf_objs(
                b"<< /Type /Catalog >>", self._stream(objstm, b" /Type /ObjStm /N 1 /First 4 /Filter /FlateDecode"))},
        }
        self.assertEqual(self._verify_each_layout(layouts), [])

    REMAP = "PDF text in re-mapped font codes"

    def _font_pdf(self, *objs):
        content = self._stream(zlib.compress(b"BT /F1 12 Tf <010203040506> Tj ET"), b" /Filter /FlateDecode")
        return self._pdf_objs(content, *objs)

    def test_round8_pdf_text_in_re_mapped_font_codes_is_opaque(self):
        # R7-03: a subset font draws "987653" with codes 1..6 through /Differences (cairo-style), so
        # neither the bytes nor the strings hold the figure: verify must say it cannot read it.
        diff = b"<< /Type /Font /Subtype /TrueType /BaseFont /ABCDEF+Arial /FirstChar 1 /LastChar 6 " \
               b"/Encoding << /Type /Encoding /Differences [1 /nine /eight /seven /six /five /three] >> >>"
        opaque = {
            "Differences, codes below 32": diff,
            "Differences, named glyphs": b"<< /Encoding << /Differences [1 /g1 /g2 /g3] >> >>",
            "Differences, a digit moved to another ASCII code": b"<< /Encoding << /Differences [65 /nine] >> >>",
            "Differences, a digit at a high code": b"<< /Encoding << /Differences [200 /nine] >> >>",
            "Differences, uniXXXX digit at a high code": b"<< /Encoding << /Differences [200 /uni0039] >> >>",
            "Differences, ASCII code given another glyph": b"<< /Encoding << /Differences [57 /eacute] >> >>",
            "predefined CMap": b"<< /Type /Font /Subtype /Type0 /Encoding /UniJIS-UCS2-H >>",
            "predefined CMap, one letter": b"<< /Type /Font /Subtype /Type0 /Encoding /H >>",
            "embedded CMap": self._stream(zlib.compress(
                b"/CIDInit /ProcSet findresource begin begincmap 1 begincodespacerange <00> <FF> endcodespacerange "
                b"1 begincidrange <01> <06> 20 endcidrange endcmap"), b" /Type /CMap /Filter /FlateDecode"),
            "ToUnicode bfchar re-map": self._stream(zlib.compress(
                b"begincmap 2 beginbfchar <01> <0039> <02> <0038> endbfchar endcmap"), b" /Filter /FlateDecode"),
            "ToUnicode bfrange re-map": self._stream(zlib.compress(
                b"begincmap 1 beginbfrange <01> <06> <0031> endbfrange endcmap"), b" /Filter /FlateDecode"),
            "ToUnicode bfrange array re-map": self._stream(zlib.compress(
                b"begincmap 1 beginbfrange <01> <02> [<0039> <0038>] endbfrange endcmap"), b" /Filter /FlateDecode"),
            "ToUnicode two-byte codes": self._stream(
                b"begincmap 1 beginbfchar <0039> <0039> endbfchar endcmap"),
            "ToUnicode bfrange array shorter than its range": self._stream(
                b"begincmap 1 beginbfrange <41> <43> [<0041> <0042>] endbfrange endcmap"),
            "ToUnicode bfrange ending before it starts": self._stream(
                b"begincmap 1 beginbfrange <39> <30> <0039> endbfrange endcmap"),
            "ToUnicode bfrange one-byte destination": self._stream(
                b"begincmap 1 beginbfrange <41> <42> <41> endbfrange endcmap"),
            "ToUnicode entry it cannot read": self._stream(b"begincmap 1 beginbfchar <41> /A endbfchar endcmap"),
            "Differences in an object stream": self._stream(zlib.compress(
                b"5 0 << /Type /Encoding /Differences [1 /nine] >>"), b" /Type /ObjStm /N 1 /First 4 /Filter /FlateDecode"),
            "Differences, unparseable entry": b"<< /Encoding << /Differences [48 (x) /zero] >> >>",
            "Differences never closed": b"<< /Encoding << /Differences [1 /nine /eight",
        }
        for name, obj in opaque.items():
            self.assertEqual(purge_scan.expand(self._font_pdf(obj))[1], {self.REMAP}, name)
        plain = {
            "Differences, high codes only": b"<< /Encoding << /BaseEncoding /WinAnsiEncoding "
                                            b"/Differences [128 /Euro 233 /eacute /egrave] >> >>",
            "Differences, ASCII names at their own codes": b"<< /Encoding << /Differences [48 /zero /one /two "
                                                          b"39 /quotesingle 96 /grave 32 /space 45 /hyphen] >> >>",
            "Differences, uniXXXX at its own code and .notdef": b"<< /Encoding << /Differences [57 /uni0039 1 /.notdef] >> >>",
            "Differences, quoteright and quoteleft at 39 and 96": b"<< /Encoding << /Differences [39 /quoteright 96 /quoteleft] >> >>",
            "ToUnicode identity": self._stream(zlib.compress(
                b"begincmap 1 beginbfchar <39> <0039> endbfchar 1 beginbfrange <30> <38> <0030> endbfrange "
                b"1 beginbfrange <41> <42> [<0041> <0042>] endbfrange 1 beginbfchar <E9> <00E9> endbfchar endcmap"),
                b" /Filter /FlateDecode"),
            "ToUnicode high code to a ligature": self._stream(b"begincmap 1 beginbfchar <AE> <00660069> endbfchar endcmap"),
            "ToUnicode control code to itself": self._stream(b"begincmap 1 beginbfchar <01> <0001> endbfchar endcmap"),
            "simple encodings": b"<< /Encoding /WinAnsiEncoding >> << /Encoding /MacRomanEncoding >> "
                                b"<< /Encoding /StandardEncoding >> << /Encoding /PDFDocEncoding >> << /Encoding /MacExpertEncoding >>",
            "names that are not CMaps": b"<< /Encoding /Identity-Vx >> << /Encoding /Identity-HV1 >> << /Encoding /Custom >> "
                                        b"<< /Encoding /GBK-EUC-Hx >>",
        }
        for name, obj in plain.items():
            self.assertEqual(purge_scan.expand(self._font_pdf(obj))[1], set(), name)
        # Identity-H/V keep their own reason, and are not called re-mapped too
        self.assertEqual(purge_scan.expand(self._font_pdf(b"<< /Subtype /Type0 /Encoding /Identity-H >>"))[1],
                         {"PDF text in font glyph codes (Identity-H/V)"})

    def test_round8_font_code_scan_reads_a_run_of_unclosed_blocks_once(self):
        # A run of block starts with no end (damaged or hostile PDF) is read once, not once per
        # start: a rescan per start took minutes on 2 MB and verify looked hung.
        import time
        for blob in (b"beginbfchar <41> " * 120000, b"/Differences [1 /one " * 100000, b"beginbfrange " * 160000):
            t = time.perf_counter()
            self.assertTrue(purge_scan.remapped_font_codes(blob))
            self.assertLess(time.perf_counter() - t, 5, blob[:20])

    def test_round8_verify_lists_a_pdf_in_re_mapped_font_codes_as_opaque(self):
        self.config(values=[987653], phones=False)
        self.r.commit({"a.md": "x\n"})
        self.r.commit({"statement.pdf": self._font_pdf(
            b"<< /Type /Font /Subtype /TrueType /Encoding << /Differences [1 /nine /eight /seven /six /five /three] >> >>")})
        self.r.commit(delete=["statement.pdf"])
        self._empty_rules()
        v = self.verify()
        self.assertEqual(v.returncode, 0, v.stdout)
        self.assertIn("opaque blobs (NOT searched inside): 1", v.stdout)
        line = [l for l in v.stdout.splitlines() if l.startswith("OPAQUE ")]
        self.assertEqual(len(line), 1, v.stdout)
        self.assertIn("path=statement.pdf ", line[0])
        self.assertIn("reason=" + self.REMAP, line[0])

    # ---- R3-06: renaming a tag whose name holds a value ------------------------------------
    def test_tag_rename_recipe_leaves_no_old_tag_object(self):
        self.config(values=[987653], phones=False)
        self.r.commit({"a.md": "x\n"})
        git(self.r.path, "tag", "-a", "v-987653", "-m", "release notes")
        self._empty_rules()
        self.assertEqual(self.verify().returncode, 1)
        # The old recipe (a lightweight tag on the old tag) keeps the old tag object and its name.
        git(self.r.path, "tag", "v-lightweight", "v-987653")
        git(self.r.path, "tag", "-d", "v-987653")
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("values still present: 1", v.stdout)
        git(self.r.path, "tag", "-d", "v-lightweight")
        # The recipe: a NEW annotated tag on the peeled commit, delete the old, expire reflogs, prune.
        git(self.r.path, "tag", "-a", "v-987653", "-m", "release notes", "HEAD")
        msg = os.path.join(self.tmp.name, "private", "tagmsg.txt")
        with open(msg, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(git(self.r.path, "tag", "-l", "--format=%(contents)", "v-987653"))
        git(self.r.path, "tag", "-a", "v-renamed", "-F", msg, "v-987653^{}")
        git(self.r.path, "tag", "-d", "v-987653")
        self.assertEqual(self.verify().returncode, 1)          # the old tag object is still in the store
        git(self.r.path, "reflog", "expire", "--expire=now", "--all")
        git(self.r.path, "gc", "-q", "--prune=now")
        v = self.verify()
        self.assertEqual(v.returncode, 0, v.stdout)
        self.assertEqual(git(self.r.path, "cat-file", "-p", "v-renamed").splitlines()[2], "tag v-renamed")
        self.assertEqual(git(self.r.path, "rev-parse", "v-renamed^{}"), git(self.r.path, "rev-parse", "HEAD"))


if __name__ == "__main__":
    unittest.main()
