"""Tests for purge_scan.py (stdlib unittest; gated by tools/run_skill_suites.sh).

All values are synthetic (555-01xx phones, made-up figures and names).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "purge_scan.py")
FIG = "123,457"
LIT = "Project Blue Heron"
PHONE = "614-555-0199"
TIP_FIG = "987,651"
ENV = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="t",
           GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "core.autocrlf=false"] + list(args), capture_output=True,
                          text=True, check=True, env=ENV).stdout


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
        self.r.commit({"s.md": "noi %s\n" % FIG})
        git(self.r.path, "tag", "only-tag")
        git(self.r.path, "checkout", "-q", "main")
        git(self.r.path, "branch", "-q", "-D", "side")
        self.scan()
        self.assertTrue(rules_match(self.rules, FIG))
        v = self.verify()
        self.assertEqual(v.returncode, 1, v.stdout)
        self.assertIn("blobs matching a rule: 1", v.stdout)

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

if __name__ == "__main__":
    unittest.main()
