#!/usr/bin/env python3
"""Regression tests for sync_local_skills_mirror.py.

Stdlib only — run with `python tools/test_sync_local_skills_mirror.py` (no pytest).

Covers the 2026-08-16 fix for Automation Audit R13-2: ora-setup-audit's local
Code-surface mirror (~/.claude/skills/<skill>) had silently diverged from the
canonical repo copy, and nothing kept the two in sync. These tests build
synthetic repo/mirror fixture trees (never the real ora-skills repo or the
real ~/.claude/skills) so they're deterministic regardless of live drift state.
"""
import shutil
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_local_skills_mirror as slm  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='')


class FixtureTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='sync_local_skills_mirror_test_'))
        self.repo = self.tmp / 'repo'
        self.mirror = self.tmp / 'mirror'
        self.repo.mkdir()
        self.mirror.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class SyncSkill(FixtureTestCase):
    def test_no_local_mirror_is_skipped_not_created(self):
        _write(self.repo / 'some-skill' / 'SKILL.md', 'name: some-skill\ncontent\n')
        # No mirror dir created — sync must not auto-create one.

        result = slm.sync_skill('some-skill', repo_root=self.repo, mirror_root=self.mirror)

        self.assertIn('no local mirror, skipped', result)
        self.assertFalse((self.mirror / 'some-skill').exists())

    def test_diverged_mirror_is_repaired(self):
        _write(self.repo / 'drifted-skill' / 'SKILL.md', 'name: drifted-skill\nv2 content\n')
        _write(self.mirror / 'drifted-skill' / 'SKILL.md', 'name: drifted-skill\nv1 STALE content\n')

        result = slm.sync_skill('drifted-skill', repo_root=self.repo, mirror_root=self.mirror)

        self.assertIn('synced', result)
        self.assertEqual(
            (self.mirror / 'drifted-skill' / 'SKILL.md').read_text(encoding='utf-8'),
            'name: drifted-skill\nv2 content\n',
        )

    def test_already_synced_mirror_is_a_noop(self):
        _write(self.repo / 'synced-skill' / 'SKILL.md', 'name: synced-skill\ncontent\n')
        _write(self.mirror / 'synced-skill' / 'SKILL.md', 'name: synced-skill\ncontent\n')

        result = slm.sync_skill('synced-skill', repo_root=self.repo, mirror_root=self.mirror)

        self.assertIn('already in sync', result)

    def test_multi_file_skill_syncs_new_and_changed_files(self):
        _write(self.repo / 'multi-skill' / 'SKILL.md', 'name: multi-skill\ncontent\n')
        _write(self.repo / 'multi-skill' / 'references' / 'notes.md', 'notes v2\n')
        _write(self.mirror / 'multi-skill' / 'SKILL.md', 'name: multi-skill\ncontent\n')
        # references/notes.md doesn't exist in the mirror yet — a new bundled file.

        result = slm.sync_skill('multi-skill', repo_root=self.repo, mirror_root=self.mirror)

        self.assertIn('synced', result)
        self.assertEqual(
            (self.mirror / 'multi-skill' / 'references' / 'notes.md').read_text(encoding='utf-8'),
            'notes v2\n',
        )

    def test_non_bundled_files_are_not_copied(self):
        # PACKAGING-NOTE.md and versions/ are excluded from every bundle
        # (package_skills.is_bundled) — the mirror sync must respect the same
        # rule as the packager, not ship repo-reader-only or archival content.
        _write(self.repo / 'noted-skill' / 'SKILL.md', 'name: noted-skill\ncontent\n')
        _write(self.repo / 'noted-skill' / 'PACKAGING-NOTE.md', 'internal note\n')
        _write(self.repo / 'noted-skill' / 'versions' / 'old.md', 'archived\n')
        _write(self.mirror / 'noted-skill' / 'SKILL.md', 'name: noted-skill\ncontent\n')

        slm.sync_skill('noted-skill', repo_root=self.repo, mirror_root=self.mirror)

        self.assertFalse((self.mirror / 'noted-skill' / 'PACKAGING-NOTE.md').exists())
        self.assertFalse((self.mirror / 'noted-skill' / 'versions').exists())


class Main(unittest.TestCase):
    def test_no_affected_skills_does_not_raise(self):
        # A commit touching nothing skill-shaped (empty affected_skills()) must
        # be a silent no-op, matching pending_reimport's own non-blocking design.
        with unittest.mock.patch.object(slm, 'changed_files', return_value=['README.md']):
            slm.main()  # must not raise


if __name__ == '__main__':
    unittest.main()
