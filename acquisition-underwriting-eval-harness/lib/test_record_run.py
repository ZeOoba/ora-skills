import csv
import errno
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from record_run import record_run


def _result(deal_id, status="PASS", scored=True):
    return {"deal_id": deal_id, "status": status, "scored": scored}


class TestRecordRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="eval_harness_runs_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_writes_dated_snapshot_json(self):
        out = record_run(
            [_result("a"), _result("b", status="FLAG")],
            self.tmp,
            skill_sha="abc123",
            run_label="unit-test",
            run_timestamp="2026-08-14T120000Z",
        )
        self.assertTrue(os.path.exists(out["snapshot_path"]))
        with open(out["snapshot_path"]) as f:
            snap = json.load(f)
        self.assertEqual(snap["scored_deals"], 2)
        self.assertEqual(snap["scored_pass"], 1)
        self.assertEqual(snap["scored_flag"], 1)
        self.assertEqual(snap["skill_sha"], "abc123")

    def test_informational_rows_excluded_from_scored_counts(self):
        out = record_run(
            [_result("a", scored=True), _result("b", scored=False, status="FLAG")],
            self.tmp,
            run_timestamp="2026-08-14T120100Z",
        )
        self.assertEqual(out["summary"]["scored_deals"], 1)
        self.assertEqual(out["summary"]["informational_deals"], 1)

    def test_second_run_appends_not_overwrites(self):
        record_run([_result("a")], self.tmp, run_timestamp="2026-08-14T120200Z")
        record_run([_result("a")], self.tmp, run_timestamp="2026-08-14T130200Z")
        json_files = [f for f in os.listdir(self.tmp) if f.endswith(".json")]
        self.assertEqual(len(json_files), 2)
        with open(os.path.join(self.tmp, "summary.csv")) as f:
            rows = list(csv.reader(f))
        self.assertEqual(len(rows), 3)  # header + 2 runs

    def test_refuses_to_clobber_same_timestamp(self):
        record_run([_result("a")], self.tmp, run_timestamp="2026-08-14T120300Z")
        with self.assertRaises(ValueError):
            record_run([_result("a")], self.tmp, run_timestamp="2026-08-14T120300Z")

    def test_empty_results_rejected(self):
        with self.assertRaises(ValueError):
            record_run([], self.tmp)

    def test_missing_required_key_rejected(self):
        with self.assertRaises(ValueError):
            record_run([{"deal_id": "a"}], self.tmp)  # missing status/scored

    def test_run_label_with_unsafe_filename_characters_is_sanitized(self):
        """REFUTE-pass finding: SKILL.md's own Step 4 example run_label
        ('post-<doctrine-change>') contains characters invalid in Windows
        filenames; a colon in a label crashes outright. Must not raise and
        must not silently produce a mis-scoped file."""
        out = record_run(
            [_result("a")],
            self.tmp,
            run_label="post-<doctrine-change>: v4.12",
            run_timestamp="2026-08-14T120400Z",
        )
        self.assertTrue(os.path.exists(out["snapshot_path"]))
        for char in '<>:"/\\|?*':
            self.assertNotIn(char, os.path.basename(out["snapshot_path"]))

    def test_no_orphaned_tmp_file_after_clobber_refusal(self):
        record_run([_result("a")], self.tmp, run_timestamp="2026-08-14T120500Z")
        with self.assertRaises(ValueError):
            record_run([_result("a")], self.tmp, run_timestamp="2026-08-14T120500Z")
        tmp_files = [f for f in os.listdir(self.tmp) if f.endswith(".tmp")]
        self.assertEqual(tmp_files, [], f"orphaned temp file(s): {tmp_files}")

    def test_foreign_tmp_not_deleted(self):
        ts = "2026-08-14T120500Z"
        tmp_path = os.path.join(self.tmp, ts + ".json.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write("{}")
        with self.assertRaises(ValueError):
            record_run([_result("a")], self.tmp, run_timestamp=ts)
        self.assertTrue(os.path.exists(tmp_path), "another writer's in-flight tmp was deleted")

    def test_filesystem_without_hardlinks_still_writes_and_refuses_clobber(self):
        ts = "2026-08-14T120600Z"
        with mock.patch("record_run.os.link", side_effect=OSError(errno.EPERM, "no hard links")):
            out = record_run([_result("a")], self.tmp, run_timestamp=ts)
            self.assertTrue(os.path.exists(out["snapshot_path"]))
            self.assertFalse(os.path.exists(out["snapshot_path"] + ".tmp"))
            with open(out["snapshot_path"], encoding="utf-8") as f:
                self.assertEqual(json.load(f)["results"][0]["deal_id"], "a")
            with open(out["snapshot_path"], "rb") as f:
                before = f.read()
            with self.assertRaises(ValueError):
                record_run([_result("b")], self.tmp, run_timestamp=ts)
            with open(out["snapshot_path"], "rb") as f:
                self.assertEqual(f.read(), before, "refused write altered the snapshot")

    def test_fallback_replace_failure_leaves_no_placeholder(self):
        ts = "2026-08-14T120700Z"
        with mock.patch("record_run.os.link", side_effect=OSError(errno.EPERM, "no hard links")), \
                mock.patch("record_run.os.replace", side_effect=PermissionError(errno.EACCES, "denied")):
            with self.assertRaises(PermissionError):
                record_run([_result("a")], self.tmp, run_timestamp=ts)
        leftovers = [n for n in os.listdir(self.tmp) if n.startswith(ts)]
        self.assertEqual(leftovers, [], "failed fallback left a snapshot or tmp behind")
        out = record_run([_result("a")], self.tmp, run_timestamp=ts)
        with open(out["snapshot_path"], encoding="utf-8") as f:
            self.assertEqual(json.load(f)["results"][0]["deal_id"], "a")

    def test_fallback_cleanup_failure_preserves_original_exception(self):
        ts = "2026-08-14T120800Z"
        real_remove = os.remove
        snapshot_name = ts + ".json"

        def remove(path, *a, **kw):
            if os.path.basename(path) == snapshot_name:
                raise PermissionError(errno.EACCES, "cleanup")
            return real_remove(path, *a, **kw)

        with mock.patch("record_run.os.link", side_effect=OSError(errno.EPERM, "no hard links")), \
                mock.patch("record_run.os.replace", side_effect=PermissionError(errno.EACCES, "orig")), \
                mock.patch("record_run.os.remove", side_effect=remove):
            with self.assertRaises(PermissionError) as cm:
                record_run([_result("a")], self.tmp, run_timestamp=ts)
        self.assertEqual(cm.exception.strerror, "orig", "cleanup error replaced the original exception")

    def test_fallback_keyboard_interrupt_leaves_no_placeholder(self):
        ts = "2026-08-14T120900Z"
        with mock.patch("record_run.os.link", side_effect=OSError(errno.EPERM, "no hard links")), \
                mock.patch("record_run.os.replace", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                record_run([_result("a")], self.tmp, run_timestamp=ts)
        leftovers = [n for n in os.listdir(self.tmp) if n.startswith(ts)]
        self.assertEqual(leftovers, [], "interrupted fallback left a snapshot or tmp behind")

    def test_fallback_completed_replace_then_error_keeps_full_snapshot(self):
        ts = "2026-08-14T121000Z"
        real_replace = os.replace

        def replace_then_fail(src, dst, *a, **kw):
            real_replace(src, dst, *a, **kw)
            raise PermissionError(errno.EACCES, "after move")

        with mock.patch("record_run.os.link", side_effect=OSError(errno.EPERM, "no hard links")), \
                mock.patch("record_run.os.replace", side_effect=replace_then_fail):
            with self.assertRaises(PermissionError):
                record_run([_result("a")], self.tmp, run_timestamp=ts)
        snapshot_path = os.path.join(self.tmp, ts + ".json")
        self.assertTrue(os.path.exists(snapshot_path), "completed snapshot was deleted")
        self.assertGreater(os.path.getsize(snapshot_path), 0)
        with open(snapshot_path, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["results"][0]["deal_id"], "a")


if __name__ == "__main__":
    unittest.main()
