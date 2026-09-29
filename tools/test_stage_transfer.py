"""Tests for tools/stage_transfer.py (run: python tools/test_stage_transfer.py).

unittest, not bare pytest functions: tools/run_suite.sh fails any file whose
module-level `def test_*` never runs under `python <file>` (BARE) -- see its header.
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import stage_transfer as st  # noqa: E402


def make_skill(path: Path, top="demo", extra=None, backslash=False, dirrec=False):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"{top}/SKILL.md", "---\nname: demo\n---\n# demo\n")
        if extra:
            zf.writestr(extra, "x")
        if backslash:
            # zipfile rewrites '\\' -> '/' on Windows at write time, so patch the
            # bytes: same-length swap, valid in both the local header and the
            # central directory.
            zf.writestr(f"{top}/bad.md", "x")
        if dirrec:
            zf.writestr(f"{top}/refs/", "")
    if backslash:
        raw = path.read_bytes()
        needle = f"{top}/bad.md".encode()
        assert raw.count(needle) == 2
        path.write_bytes(raw.replace(needle, f"{top}\\bad.md".encode()))
    return path


class StageTransferTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)

    def run_main(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = st.main(argv)
        return rc, buf.getvalue()

    def test_emit_writes_manifest(self):
        make_skill(self.tmp / "a.skill")
        rc, _ = self.run_main(["emit", str(self.tmp)])
        self.assertEqual(rc, 0)
        m = json.loads((self.tmp / st.MANIFEST_NAME).read_text())
        self.assertEqual(m["files"][0]["name"], "a.skill")
        self.assertEqual(len(m["files"][0]["prefix16"]), 16)
        self.assertTrue(m["files"][0]["zip_ok"])

    def test_emit_flags_bad_zip_entries(self):
        make_skill(self.tmp / "a.skill", backslash=True)
        rc, _ = self.run_main(["emit", str(self.tmp)])
        self.assertEqual(rc, 1)

    def test_backslash_entry_visible_on_every_os(self):
        # Regression: zipfile.namelist() hides backslashes on Windows.
        p = make_skill(self.tmp / "a.skill", backslash=True)
        self.assertTrue(any("backslash" in x for x in st.zip_problems(p)),
                        st.zip_problems(p))

    def test_directory_record_flagged(self):
        p = make_skill(self.tmp / "a.skill", dirrec=True)
        self.assertTrue(any("directory record" in x for x in st.zip_problems(p)))

    def test_clean_zip_has_no_problems(self):
        self.assertEqual(st.zip_problems(make_skill(self.tmp / "a.skill")), [])

    def test_receive_pass_copies_and_verifies(self):
        src, out = self.tmp / "staged", self.tmp / "out"
        src.mkdir()
        make_skill(src / "a.skill")
        prefix = st.sha256_file(src / "a.skill")[:16].upper()  # case-insensitive
        rc, _ = self.run_main(["receive", "--staged-dir", str(src), "--outputs", str(out),
                               "--expect", f"a.skill={prefix}"])
        self.assertEqual(rc, 0)
        self.assertEqual(st.sha256_file(out / "a.skill"), st.sha256_file(src / "a.skill"))
        self.assertFalse(list(out.glob("*.part")))

    def test_receive_mismatch_copies_nothing(self):
        src, out = self.tmp / "staged", self.tmp / "out"
        src.mkdir()
        make_skill(src / "a.skill")
        make_skill(src / "b.skill", extra="demo/refs/x.md")
        good = st.sha256_file(src / "a.skill")[:16]
        rc, _ = self.run_main(["receive", "--staged-dir", str(src), "--outputs", str(out),
                               "--expect", f"a.skill={good}",
                               "--expect", "b.skill=" + "0" * 16])
        self.assertEqual(rc, 1)
        self.assertTrue(not out.exists() or not list(out.iterdir()))  # all-or-nothing

    def test_receive_invisible_file_fails_and_reports_path(self):
        src = self.tmp / "staged"
        src.mkdir()
        rc, out = self.run_main(["receive", "--staged-dir", str(src),
                                 "--outputs", str(self.tmp / "o"),
                                 "--expect", "gone.skill=" + "a" * 16])
        self.assertEqual(rc, 1)
        self.assertIn(str(src / "gone.skill"), out)

    def test_receive_never_substitutes_lookalike(self):
        src = self.tmp / "staged"
        src.mkdir()
        make_skill(src / "old.skill")  # not named -> must be UNUSED, not picked up
        rc, out = self.run_main(["receive", "--staged-dir", str(src),
                                 "--outputs", str(self.tmp / "o"),
                                 "--expect", "new.skill=" + "b" * 16])
        self.assertEqual(rc, 1)
        self.assertIn("UNUSED  old.skill", out)
        self.assertFalse((self.tmp / "o").exists())

    def test_short_prefix_rejected(self):
        (self.tmp / "s").mkdir()
        rc, _ = self.run_main(["receive", "--staged-dir", str(self.tmp / "s"),
                               "--expect", "a.skill=abc123"])
        self.assertEqual(rc, 2)

    def test_manifest_roundtrip(self):
        src = self.tmp / "staged"
        src.mkdir()
        make_skill(src / "a.skill")
        self.assertEqual(self.run_main(["emit", str(src)])[0], 0)
        rc, _ = self.run_main(["receive", "--staged-dir", str(src),
                               "--outputs", str(self.tmp / "o"),
                               "--manifest", str(src / st.MANIFEST_NAME)])
        self.assertEqual(rc, 0)

    def test_hash_ok_but_bad_zip_fails(self):
        src = self.tmp / "staged"
        src.mkdir()
        make_skill(src / "a.skill", backslash=True)
        prefix = st.sha256_file(src / "a.skill")[:16]
        rc, _ = self.run_main(["receive", "--staged-dir", str(src),
                               "--outputs", str(self.tmp / "o"),
                               "--expect", f"a.skill={prefix}"])
        self.assertEqual(rc, 1)


class HardeningTests(unittest.TestCase):
    """Regressions for defects found by the independent review (2026-09-28)."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)
        self.src = self.tmp / "staged"
        self.src.mkdir()

    def recv(self, *extra, out="o"):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = st.main(["receive", "--staged-dir", str(self.src),
                          "--outputs", str(self.tmp / out), *extra])
        return rc, buf.getvalue()

    def test_only_naming_nothing_is_not_a_vacuous_pass(self):
        make_skill(self.src / "c.skill")
        pre = st.sha256_file(self.src / "c.skill")[:16]
        rc, out = self.recv("--expect", f"c.skill={pre}", "--only", "typo.skill")
        self.assertEqual(rc, 2)
        self.assertNotIn("ALL PASS", out)

    def test_empty_manifest_digest_rejected(self):
        make_skill(self.src / "g.skill")
        m = self.tmp / "m.json"
        m.write_text(json.dumps({"files": [{"name": "g.skill", "sha256": ""}]}))
        rc, _ = self.recv("--manifest", str(m))
        self.assertEqual(rc, 2)

    def test_uppercase_manifest_digest_accepted(self):
        make_skill(self.src / "g.skill")
        m = self.tmp / "m.json"
        m.write_text(json.dumps({"files": [
            {"name": "g.skill", "sha256": st.sha256_file(self.src / "g.skill").upper()}]}))
        self.assertEqual(self.recv("--manifest", str(m))[0], 0)

    def test_malformed_manifests_fail_cleanly(self):
        for body in ("[]", '{"files":[{"sha256":"ab"}]}', '{"files":5}', "not json"):
            m = self.tmp / "m.json"
            m.write_text(body)
            self.assertEqual(self.recv("--manifest", str(m))[0], 2, body)

    def test_non_bare_names_rejected(self):
        rc, _ = self.recv("--expect", "../x.skill=" + "a" * 16)
        self.assertEqual(rc, 2)
        rc, _ = self.recv("--expect", "sub/x.skill=" + "a" * 16)
        self.assertEqual(rc, 2)

    def test_corrupt_deflate_fails_cleanly(self):
        p = self.src / "a.skill"
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("demo/SKILL.md", "hello world " * 200)
        raw = bytearray(p.read_bytes())
        raw[40:60] = b"\xff" * 20  # smash the deflate stream inside the local entry
        p.write_bytes(bytes(raw))
        self.assertTrue(st.zip_problems(p))  # a problem list, never an exception

    def test_encrypted_flag_fails_cleanly(self):
        p = make_skill(self.src / "a.skill")
        raw = bytearray(p.read_bytes())
        for sig, off in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
            i = raw.find(sig)
            raw[i + off] |= 1
        p.write_bytes(bytes(raw))
        self.assertTrue(st.zip_problems(p))

    def test_dotdot_entry_flagged(self):
        p = self.src / "a.skill"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("../SKILL.md", "x")
        self.assertTrue(any("unsafe" in x for x in st.zip_problems(p)))

    def test_unhashable_manifest_name_fails_cleanly(self):
        m = self.tmp / "m.json"
        for bad in (["g.skill"], {"a": 1}):
            m.write_text(json.dumps({"files": [{"name": bad, "sha256": "a" * 64}]}))
            self.assertEqual(self.recv("--manifest", str(m))[0], 2)

    def test_dot_segment_entry_flagged(self):
        p = self.src / "a.skill"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("./SKILL.md", "x")
        self.assertTrue(any("unsafe" in x for x in st.zip_problems(p)))

    def test_directory_destination_leaves_no_partial_set(self):
        make_skill(self.src / "a.skill")
        make_skill(self.src / "b.skill", extra="demo/refs/x.md")
        (self.tmp / "o" / "b.skill").mkdir(parents=True)
        exp = [f"{n}={st.sha256_file(self.src / n)[:16]}" for n in ("a.skill", "b.skill")]
        rc, _ = self.recv("--expect", exp[0], "--expect", exp[1])
        self.assertEqual(rc, 1)
        self.assertFalse((self.tmp / "o" / "a.skill").exists())
        self.assertFalse(list((self.tmp / "o").glob("*.part")))

    def test_partial_outputs_never_left_behind(self):
        make_skill(self.src / "a.skill")
        make_skill(self.src / "b.skill", extra="demo/refs/x.md")
        real = st.sha256_file
        calls = {"n": 0}

        def flaky(path):  # verification passes; the 2nd .part copy hashes wrong
            if str(path).endswith(".part"):
                calls["n"] += 1
                if calls["n"] == 2:
                    return "0" * 64
            return real(path)

        exp = [f"{n}={real(self.src / n)[:16]}" for n in ("a.skill", "b.skill")]
        st.sha256_file = flaky
        try:
            rc, _ = self.recv("--expect", exp[0], "--expect", exp[1])
        finally:
            st.sha256_file = real
        self.assertEqual(rc, 1)
        out = self.tmp / "o"
        self.assertTrue(not out.exists() or not list(out.iterdir()))


if __name__ == "__main__":
    unittest.main()
