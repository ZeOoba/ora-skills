#!/usr/bin/env python3
"""Unit tests for build_plugin.py + plugin-membership wiring in package_skills.py.
Run: python tools/test_build_plugin.py   (stdlib unittest; no pytest dependency)"""
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_plugin as bp  # noqa: E402
import package_skills as ps  # noqa: E402

PLUGIN = 'ora-operations-extensions'


class PluginMembership(unittest.TestCase):
    def test_members_map_to_owning_plugin(self):
        self.assertEqual(ps.plugin_of('deal-retirement'), PLUGIN)
        self.assertEqual(ps.plugin_of('submarket-spatial-analysis'), PLUGIN)

    def test_standalone_skill_is_not_a_member(self):
        self.assertIsNone(ps.plugin_of('acquisition-underwriting'))
        # debt-management is a standalone skill, NOT bundled (the 8-vs-7 defect)
        self.assertIsNone(ps.plugin_of('debt-management'))

    def test_no_plugins_dir_yields_empty(self):
        self.assertEqual(ps._build_plugin_members({}), {})


class VersionBump(unittest.TestCase):
    def test_patch_minor_major(self):
        self.assertEqual(bp.bump_version('0.1.2', 'patch'), '0.1.3')
        self.assertEqual(bp.bump_version('0.1.2', 'minor'), '0.2.0')
        self.assertEqual(bp.bump_version('0.1.2', 'major'), '1.0.0')

    def test_bad_part_and_bad_version_raise(self):
        with self.assertRaises(SystemExit):
            bp.bump_version('0.1.2', 'sideways')
        with self.assertRaises(SystemExit):
            bp.bump_version('v0.1', 'patch')


class ShippedManifest(unittest.TestCase):
    def test_strips_build_only_skills_key(self):
        bm = bp.load_manifest(PLUGIN)
        shipped = bp.shipped_manifest(bm)
        self.assertNotIn('skills', shipped)
        self.assertIn('version', shipped)
        self.assertEqual(shipped['name'], PLUGIN)


class Entries(unittest.TestCase):
    def setUp(self):
        self.entries = bp.plugin_entries(PLUGIN)

    def test_all_forward_slash(self):
        self.assertFalse([a for a in self.entries if '\\' in a])

    def test_has_manifest_and_readme(self):
        self.assertIn('.claude-plugin/plugin.json', self.entries)
        self.assertIn('README.md', self.entries)

    def test_every_member_skill_present_with_skillmd(self):
        skills = bp.load_manifest(PLUGIN)['skills']
        self.assertEqual(len(skills), 7)
        for s in skills:
            self.assertIn(f'skills/{s}/SKILL.md', self.entries)

    def test_shipped_manifest_has_no_debt_and_no_skills_key(self):
        pj = json.loads(self.entries['.claude-plugin/plugin.json'])
        self.assertNotIn('skills', pj)
        self.assertNotIn('debt', pj['description'].lower())
        self.assertTrue(pj['description'].startswith('Seven'))

    def test_member_skillmd_bytes_equal_repo(self):
        for s in bp.load_manifest(PLUGIN)['skills']:
            repo_bytes = (ps.REPO / s / 'SKILL.md').read_bytes()
            self.assertEqual(self.entries[f'skills/{s}/SKILL.md'], repo_bytes)


class BuildRoundTrip(unittest.TestCase):
    def test_build_writes_valid_zip(self):
        with tempfile.TemporaryDirectory() as td:
            dest = bp.build_plugin(PLUGIN, Path(td))
            self.assertTrue(dest.is_file())
            with zipfile.ZipFile(dest) as z:
                names = z.namelist()
                self.assertIn('.claude-plugin/plugin.json', names)
                self.assertFalse([n for n in names if '\\' in n])
                pj = json.loads(z.read('.claude-plugin/plugin.json'))
                self.assertEqual(pj['name'], PLUGIN)


class OutdirCollision(unittest.TestCase):
    """Regression coverage for the 2026-07-24 outdir-collision guard, mirrored from
    package_skills.py's resolve_outdir_collision into build_plugin() (build_plugin.py
    <plugin-name> <outdir> has the same swapped-argument footgun, with outdir landing
    on a skill's own source directory)."""

    def _make_plugin(self, td):
        root = Path(td)
        plugins_dir = root / 'plugins'
        pdir = plugins_dir / PLUGIN
        pdir.mkdir(parents=True)
        skill_dir = root / 'fake-skill'
        skill_dir.mkdir()
        (skill_dir / 'SKILL.md').write_text('---\nname: fake-skill\n---\nbody')
        manifest = {
            'name': PLUGIN, 'version': '0.1.0',
            'description': 'test plugin', 'skills': ['fake-skill'],
        }
        (pdir / 'plugin-build.json').write_text(json.dumps(manifest))
        return root, plugins_dir, skill_dir

    def test_outdir_matching_skill_dir_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root, plugins_dir, skill_dir = self._make_plugin(td)
            with mock.patch.object(bp, 'PLUGINS_DIR', plugins_dir):
                with self.assertRaises(SystemExit):
                    bp.build_plugin(PLUGIN, skill_dir, repo_root=root)
            # Guard must fire before any bundle is written into the colliding dir.
            self.assertFalse(list(skill_dir.glob('*.plugin')))

    def test_genuine_outside_outdir_is_unaffected(self):
        with tempfile.TemporaryDirectory() as td:
            root, plugins_dir, _skill_dir = self._make_plugin(td)
            with mock.patch.object(bp, 'PLUGINS_DIR', plugins_dir):
                dest = bp.build_plugin(PLUGIN, root / 'out', repo_root=root)
            self.assertTrue(dest.is_file())


class BumpOrdering(unittest.TestCase):
    """Regression coverage for the validate-before-bump reorder in build_plugin():
    a failed build must never leave a phantom version increment on the tracked
    plugin-build.json, and a successful --bump build must land the new version
    in both the shipped plugin.json and the on-disk manifest."""

    def _make_plugin(self, td, skill_has_skillmd):
        root = Path(td)
        plugins_dir = root / 'plugins'
        pdir = plugins_dir / PLUGIN
        pdir.mkdir(parents=True)
        skill_name = 'fake-skill'
        skill_dir = root / skill_name
        skill_dir.mkdir()
        if skill_has_skillmd:
            (skill_dir / 'SKILL.md').write_text('---\nname: fake-skill\n---\nbody')
        manifest = {
            'name': PLUGIN, 'version': '0.1.0',
            'description': 'test plugin', 'skills': [skill_name],
        }
        (pdir / 'plugin-build.json').write_text(json.dumps(manifest))
        return root, plugins_dir

    def test_failed_build_does_not_bump_manifest_on_disk(self):
        with tempfile.TemporaryDirectory() as td:
            root, plugins_dir = self._make_plugin(td, skill_has_skillmd=False)
            with mock.patch.object(bp, 'PLUGINS_DIR', plugins_dir):
                with self.assertRaises(SystemExit):
                    bp.build_plugin(PLUGIN, root / 'out', bump='patch', repo_root=root)
            on_disk = json.loads((plugins_dir / PLUGIN / 'plugin-build.json').read_text())
            self.assertEqual(on_disk['version'], '0.1.0')

    def test_successful_bump_lands_in_shipped_and_disk_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root, plugins_dir = self._make_plugin(td, skill_has_skillmd=True)
            with mock.patch.object(bp, 'PLUGINS_DIR', plugins_dir):
                dest = bp.build_plugin(PLUGIN, root / 'out', bump='patch', repo_root=root)
                with zipfile.ZipFile(dest) as z:
                    pj = json.loads(z.read('.claude-plugin/plugin.json'))
                on_disk = json.loads((plugins_dir / PLUGIN / 'plugin-build.json').read_text())
            self.assertEqual(pj['version'], '0.1.1')
            self.assertEqual(on_disk['version'], '0.1.1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
