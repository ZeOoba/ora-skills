"""Tests for migrate_deal_json.py: saved walk-solver deal files across the v4.53 / v4.54 input changes.

The migrated output must be accepted by the current solver (no "Unknown deal fields"), carry no land credit
until land comps are recorded, and every rollover deal without gpr must be reported, not guessed.
Run: python test_migrate_deal_json.py
"""
import contextlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import migrate_deal_json as M  # noqa: E402
from ora_walk.solver import Deal  # noqa: E402

OLD = {"name": "Old deal", "sf": 20000, "market": "Columbus OH", "year_built": 1995,
       "construction_type": "tilt-up", "stabilized_noi": 150000, "land_value": 300000}


def _run(*args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = M.main([str(a) for a in args])
    return code, buf.getvalue()


class Migrate(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def _write(self, name, obj):
        p = self.dir / name
        p.write_text(json.dumps(obj), encoding="utf-8")
        return p

    def test_land_value_becomes_market_land_value_with_no_comps(self):
        p = self._write("a.json", OLD)
        code, out = _run(self.dir)
        self.assertEqual(code, 0, out)
        d = json.loads(p.read_text(encoding="utf-8"))
        self.assertNotIn("land_value", d)
        self.assertEqual(d["market_land_value"], 300000)
        self.assertTrue(d["land_flood_cleared"])
        self.assertNotIn("land_comp_count", d)       # no credit until >= 3 comps are recorded by hand
        Deal(**d)                                     # the current solver accepts every migrated field
        self.assertTrue((self.dir / "a.pre-v453.json").exists())
        self.assertIn("land_value", json.loads((self.dir / "a.pre-v453.json").read_text(encoding="utf-8")))

    def test_zero_land_value_dropped(self):
        p = self._write("z.json", dict(OLD, land_value=0))
        _run(p)
        d = json.loads(p.read_text(encoding="utf-8"))
        self.assertNotIn("land_value", d)
        self.assertNotIn("market_land_value", d)

    def test_dry_run_changes_nothing(self):
        p = self._write("a.json", OLD)
        before = p.read_text(encoding="utf-8")
        code, out = _run(p, "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("WOULD MIGRATE", out)
        self.assertEqual(p.read_text(encoding="utf-8"), before)
        self.assertFalse((self.dir / "a.pre-v453.json").exists())

    def test_rollover_without_gpr_is_reported_not_guessed(self):
        p = self._write("r.json", dict(OLD, lease_expiry_month=60))
        code, out = _run(p)
        self.assertIn("NEEDS gpr", out)
        self.assertNotIn("gpr", json.loads(p.read_text(encoding="utf-8")))
        q = self._write("r2.json", {k: v for k, v in dict(OLD, lease_expiry_month=60).items() if k != "land_value"})
        code, out = _run(q)
        self.assertIn("CHECK", out)                   # nothing to migrate, but the gap is still reported
        self.assertFalse((self.dir / "r2.pre-v453.json").exists())

    def test_portfolio_and_list_shapes(self):
        p = self._write("p.json", {"buildings": [OLD, dict(OLD, name="B", land_value=0)]})
        l = self._write("l.json", [OLD])
        _run(self.dir)
        b = json.loads(p.read_text(encoding="utf-8"))["buildings"]
        self.assertEqual(b[0]["market_land_value"], 300000)
        self.assertNotIn("land_value", b[1])
        self.assertEqual(json.loads(l.read_text(encoding="utf-8"))[0]["market_land_value"], 300000)

    def test_backups_and_non_deal_json_skipped(self):
        self._write("x.pre-v453.json", OLD)
        self._write("other.json", {"hello": "world"})
        (self.dir / "broken.json").write_text("{not json", encoding="utf-8")
        code, out = _run(self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn("0 file(s) migrated", out)

    def test_unreadable_file_is_skipped_and_reported_not_fatal(self):
        a = self._write("a.json", OLD)
        z = self._write("z.json", OLD)                # sorts AFTER a.json, so it proves the run continued
        real = Path.read_text

        def deny(self_, *args, **kw):
            if self_.name == "a.json":
                raise PermissionError(13, "Permission denied", str(self_))
            return real(self_, *args, **kw)

        with mock.patch.object(Path, "read_text", deny):
            code, out = _run(self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn(f"SKIP {a}: cannot read", out)
        self.assertNotIn("land_value", json.loads(z.read_text(encoding="utf-8")))
        self.assertIn("1 file(s) migrated; 1 file(s) skipped", out)

    def test_folder_that_cannot_be_listed_is_reported_not_silent(self):
        # stands in for a subfolder past Windows MAX_PATH: listing it fails, which must surface as SKIP
        deep = self.dir / "deep"
        deep.mkdir()
        (deep / "d.json").write_text(json.dumps(OLD), encoding="utf-8")
        z = self._write("z.json", OLD)
        real = os.scandir

        def scandir(path="."):
            if Path(path) == deep:
                raise FileNotFoundError(2, "No such file or directory", str(path))
            return real(path)

        with mock.patch.object(os, "scandir", scandir):
            code, out = _run(self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn("SKIP", out)
        self.assertIn("cannot list folder", out)
        self.assertIn("deep", out)
        self.assertNotIn("land_value", json.loads(z.read_text(encoding="utf-8")))
        self.assertIn("1 file(s) skipped", out)

    def test_missing_or_unreachable_argument_is_reported(self):
        code, out = _run(self.dir / "nope")
        self.assertEqual(code, 0)
        self.assertIn("SKIP", out)
        self.assertIn("nope", out)
        self.assertIn("1 file(s) skipped", out)

    def test_directory_named_json_is_not_a_file(self):
        (self.dir / "dir.json").mkdir()
        code, out = _run(self.dir)
        self.assertEqual(code, 0, out)
        self.assertNotIn("SKIP", out)

    def test_non_numeric_land_value_is_skipped_not_fatal(self):
        a = self._write("a.json", dict(OLD, land_value="300,000"))
        b = self._write("b.json", OLD)
        code, out = _run(self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn(f"SKIP {a}", out)
        self.assertEqual(json.loads(a.read_text(encoding="utf-8"))["land_value"], "300,000")   # untouched
        self.assertFalse((self.dir / "a.pre-v453.json").exists())
        self.assertNotIn("land_value", json.loads(b.read_text(encoding="utf-8")))
        self.assertIn("1 file(s) migrated; 1 file(s) skipped", out)

    def test_out_of_range_land_values_are_skipped(self):
        bad = {"t.json": "true", "n.json": "NaN", "i.json": "Infinity", "m.json": "-5", "h.json": "1" + "0" * 400}
        for name, raw in bad.items():
            (self.dir / name).write_text(json.dumps(dict(OLD, land_value=0)).replace(
                '"land_value": 0', '"land_value": ' + raw), encoding="utf-8")
        code, out = _run(self.dir)
        self.assertEqual(code, 0, out)
        for name in bad:
            self.assertIn(name + ": land_value", out)
            self.assertFalse((self.dir / name.replace(".json", ".pre-v453.json")).exists())
        self.assertIn(f"0 file(s) migrated; {len(bad)} file(s) skipped", out)

    def test_deeply_nested_json_is_skipped_not_fatal(self):
        (self.dir / "deep.json").write_text("[" * 200000 + "]" * 200000, encoding="utf-8")
        z = self._write("z.json", OLD)
        code, out = _run(self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn("deep.json", out)
        self.assertNotIn("land_value", json.loads(z.read_text(encoding="utf-8")))

    def test_uppercase_extension_is_migrated_and_its_backup_ignored(self):
        p = self._write("A.JSON", OLD)
        _run(self.dir)
        self.assertNotIn("land_value", json.loads(p.read_text(encoding="utf-8")))
        code, out = _run(self.dir)                    # rerun: backup A.pre-v453.json must not be re-processed
        self.assertIn("0 file(s) migrated", out)
        self.assertNotIn("SKIP", out)

    def test_bad_second_building_leaves_whole_file_untouched(self):
        p = self._write("p.json", {"buildings": [OLD, dict(OLD, name="B", land_value="x")]})
        before = p.read_bytes()
        code, out = _run(self.dir)
        self.assertEqual(code, 0, out)
        self.assertEqual(p.read_bytes(), before)
        self.assertFalse((self.dir / "p.pre-v453.json").exists())
        self.assertIn("1 file(s) skipped", out)

    def test_read_only_stale_temp_file_is_cleared(self):
        a = self._write("a.json", OLD)
        tmp = self.dir / "a.json.migrating.tmp"
        tmp.write_text("stale", encoding="utf-8")
        os.chmod(tmp, stat.S_IREAD)
        code, out = _run(self.dir)
        if tmp.exists():                              # let tearDown-free temp dirs stay deletable
            os.chmod(tmp, stat.S_IREAD | stat.S_IWRITE)
        self.assertFalse(tmp.exists(), out)
        self.assertIn(f"MIGRATED {a}", out)
        self.assertNotIn("land_value", json.loads(a.read_text(encoding="utf-8")))

    def test_unserializable_result_is_skipped_before_any_backup(self):
        a = self._write("a.json", OLD)
        before = a.read_bytes()
        with mock.patch.object(M.json, "dumps", side_effect=RecursionError("too deep")):
            code, out = _run(self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn(f"SKIP {a}", out)
        self.assertEqual(a.read_bytes(), before)
        self.assertFalse((self.dir / "a.pre-v453.json").exists())

    def test_unserializable_result_is_skipped_in_dry_run_too(self):
        self._write("a.json", OLD)
        with mock.patch.object(M.json, "dumps", side_effect=RecursionError("too deep")):
            code, out = _run(self.dir, "--dry-run")
        self.assertIn("SKIP", out)
        self.assertNotIn("WOULD MIGRATE", out)
        self.assertIn("0 file(s) to migrate; 1 file(s) skipped", out)

    def test_overlapping_arguments_count_each_file_once(self):
        sub = self.dir / "f"
        sub.mkdir()
        (sub / "a.json").write_text(json.dumps(OLD), encoding="utf-8")
        code, out = _run(self.dir, sub / "a.json", sub, "--dry-run")
        self.assertIn("1 file(s) to migrate", out)

    def test_narrow_console_encoding_cannot_abort_or_hide_a_migration(self):
        # piped stdout on Windows is cp1252: a character outside it used to crash print() mid-run
        bad = self._write("a.json", dict(OLD, land_value="≈300k"))
        odd = self._write("b_Łódź.json", OLD)
        z = self._write("z.json", OLD)
        raw = io.BytesIO()
        narrow = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
        with mock.patch.object(sys, "stdout", narrow):
            code = M.main([str(self.dir)])
            narrow.flush()
        out = raw.getvalue().decode("cp1252")
        self.assertEqual(code, 0, out)
        self.assertIn(f"SKIP {bad}", out)
        self.assertIn("MIGRATED", out)
        self.assertNotIn("land_value", json.loads(odd.read_text(encoding="utf-8")))
        self.assertNotIn("land_value", json.loads(z.read_text(encoding="utf-8")))
        self.assertIn("2 file(s) migrated; 1 file(s) skipped", out)

    def test_hardlinked_file_is_skipped_not_split(self):
        a = self._write("a.json", OLD)
        b = self.dir / "b.json"
        os.link(a, b)                                 # NTFS and POSIX both support hard links: must succeed
        before = a.read_bytes()
        code, out = _run(self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn("hard link", out)
        self.assertEqual(a.read_bytes(), before)
        self.assertTrue(os.path.samefile(a, b))       # the link is not broken
        self.assertIn("0 file(s) migrated", out)

    def test_hardlinked_file_is_skipped_in_dry_run_too(self):
        a = self._write("a.json", OLD)
        os.link(a, self.dir / "b.json")
        code, out = _run(self.dir, "--dry-run")
        self.assertIn("hard link", out)
        self.assertNotIn("WOULD MIGRATE", out)

    def test_access_denied_argument_is_skipped_not_fatal(self):
        a = self._write("a.json", OLD)
        z = self._write("z.json", OLD)
        real = Path.is_file

        def deny(self_):
            if self_.name == "a.json":
                raise PermissionError(13, "Access is denied", str(self_))
            return real(self_)

        with mock.patch.object(Path, "is_file", deny):
            code, out = _run(a, z)
        self.assertEqual(code, 0, out)
        self.assertIn(f"SKIP {a}: cannot open", out)
        self.assertIn("1 file(s) migrated; 1 file(s) skipped", out)

    def _symlink(self, target, link, is_dir):
        """A real symlink where the OS allows it. On Windows without symlink privilege (WinError 1314) a
        plain stand-in plus mocked os.path.islink/realpath drives the same code path. Never skips: the
        skill-suite skip baseline is zero. Returns (context manager, real?)."""
        try:
            os.symlink(target, link, target_is_directory=is_dir)
            return contextlib.nullcontext(), True
        except OSError as e:
            if os.name != "nt" or getattr(e, "winerror", None) != 1314:   # only "privilege not held" falls back
                raise
        if is_dir:
            link.mkdir()
        else:
            shutil.copyfile(target, link)
        key = os.path.normcase(os.path.abspath(link))
        real_islink, real_realpath = os.path.islink, os.path.realpath

        def islink(p):
            return os.path.normcase(os.path.abspath(p)) == key or real_islink(p)

        def realpath(p, *a, **kw):
            if os.path.normcase(os.path.abspath(p)) == key:
                return real_realpath(target, *a, **kw)
            return real_realpath(p, *a, **kw)

        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.object(os.path, "islink", islink))
        stack.enter_context(mock.patch.object(os.path, "realpath", realpath))
        return stack, False

    def test_directory_symlink_is_reported(self):
        target = self.dir / "target"
        target.mkdir()
        root = self.dir / "root"
        root.mkdir()
        ctx, _ = self._symlink(target, root / "link", is_dir=True)
        with ctx:
            code, out = _run(root)
        self.assertIn("directory symlink not followed", out)
        self.assertIn("1 file(s) skipped", out)

    def test_symlinked_file_migrates_the_target(self):
        target = self._write("real.json", OLD)
        link = self.dir / "a_link.json"               # sorts before its target
        ctx, real = self._symlink(target, link, is_dir=False)
        with ctx:
            code, out = _run(self.dir)
        self.assertEqual(code, 0, out)
        self.assertNotIn("land_value", json.loads(target.read_text(encoding="utf-8")))
        if real:
            self.assertTrue(link.is_symlink())        # the link itself is left as a link
        else:
            self.assertIn("land_value", json.loads(link.read_text(encoding="utf-8")))  # link path not written
        self.assertIn("1 file(s) migrated", out)

    def test_empty_argument_is_rejected_not_treated_as_current_folder(self):
        cwd = os.getcwd()
        os.chdir(self.dir)
        try:
            a = self._write("a.json", OLD)
            code, out = _run("")
        finally:
            os.chdir(cwd)
        self.assertIn("SKIP", out)
        self.assertIn("land_value", json.loads(a.read_text(encoding="utf-8")))   # cwd NOT migrated

    def test_no_arguments_prints_usage(self):
        code, out = _run()
        self.assertNotEqual(code, 0)
        self.assertIn("Usage", out)

    if os.name == "nt":  # junctions exist only on Windows; defined (not skipped) there, since skips fail the gate
        def test_junction_is_followed_and_a_loop_is_visited_once(self):
            import subprocess
            outside = Path(tempfile.mkdtemp())
            (outside / "deal.json").write_text(json.dumps(OLD), encoding="utf-8")
            root = self.dir / "root"
            root.mkdir()
            for link, target in ((root / "linked", outside), (outside / "loop", root)):
                p = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
                self.assertEqual(p.returncode, 0, p.stderr)   # needs no privilege: must succeed
            code, out = _run(root, "--dry-run")
            self.assertEqual(code, 0, out)
            self.assertIn("deal.json", out)           # HEAD followed junctions; so must this
            self.assertIn("1 file(s) to migrate", out)   # the loop back to root does not repeat it
            self.assertNotIn("SKIP", out)

    def test_existing_market_land_value_is_kept_and_said_so(self):
        p = self._write("a.json", dict(OLD, market_land_value=100))
        code, out = _run(p)
        self.assertEqual(json.loads(p.read_text(encoding="utf-8"))["market_land_value"], 100)
        self.assertIn("kept unchanged", out)

    def test_utf8_bom_file_is_migrated(self):
        p = self.dir / "bom.json"
        p.write_text(json.dumps(OLD), encoding="utf-8-sig")
        code, out = _run(p)
        self.assertIn("MIGRATED", out)
        self.assertEqual(json.loads(p.read_text(encoding="utf-8"))["market_land_value"], 300000)

    def test_invalid_json_is_reported(self):
        (self.dir / "broken.json").write_text("{not json", encoding="utf-8")
        code, out = _run(self.dir)
        self.assertEqual(code, 0)
        self.assertIn("SKIP", out)
        self.assertIn("broken.json", out)
        self.assertIn("1 file(s) skipped", out)

    def test_write_failure_is_skipped_and_run_continues(self):
        a = self._write("a.json", OLD)
        b = self._write("b.json", OLD)
        before = a.read_text(encoding="utf-8")
        real = Path.write_text

        def disk_full(self_, data, *args, **kw):
            # a.json's new content is written to a temp file first; fail half-way through that write
            if self_.name.startswith("a.json"):
                real(self_, data[: len(data) // 2], *args, **kw)
                raise OSError(28, "No space left on device", str(self_))
            return real(self_, data, *args, **kw)

        with mock.patch.object(Path, "write_text", disk_full):
            code, out = _run(self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn("cannot write", out)
        self.assertNotIn(f"MIGRATED {a}", out)        # never claims a migration that did not land
        self.assertEqual(a.read_text(encoding="utf-8"), before)   # original intact, not truncated
        self.assertEqual([p.name for p in self.dir.iterdir() if p.name.endswith(".tmp")], [])
        self.assertNotIn("land_value", json.loads(b.read_text(encoding="utf-8")))
        self.assertIn("1 file(s) migrated; 1 file(s) skipped", out)

    def test_read_only_original_recovers_on_rerun(self):
        a = self._write("a.json", OLD)
        os.chmod(a, stat.S_IREAD)
        try:
            _, first = _run(self.dir)                 # Windows refuses the replace; POSIX allows it. Either is fine
            if "SKIP" in first:                       # ...but a refusal must name the deal file, not the temp file
                self.assertIn(f"cannot write {a} ", first)
                self.assertNotIn(".migrating.tmp", first)
        finally:
            os.chmod(a, stat.S_IREAD | stat.S_IWRITE)
        code, out = _run(self.dir)                    # user clears read-only and reruns
        self.assertEqual(code, 0, out)
        self.assertNotIn("SKIP", out)
        self.assertNotIn("land_value", json.loads(a.read_text(encoding="utf-8")))
        backup = self.dir / "a.pre-v453.json"
        self.assertIn("land_value", json.loads(backup.read_text(encoding="utf-8")))
        self.assertTrue(os.access(backup, os.W_OK))  # backup must not inherit read-only


if __name__ == "__main__":
    unittest.main()
