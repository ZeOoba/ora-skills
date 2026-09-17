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

# 2026-08-05: the ora-operations-extensions bundle was RETIRED (Gabriel's call
# during the automation audit) and its manifest archived to
# _archive/plugins/ora-operations-extensions/. All seven member skills already
# lived at the repo root and simply revert to standalone Save-skill installs, so
# plugin_of() now returns None for every skill in the repo.
#
# The tests below therefore exercise build_plugin.py against a SYNTHETIC fixture
# plugin rather than a live one. That is deliberate: the regression coverage here
# encodes real past incidents (the 8-vs-7 membership defect, the 2026-07-24
# outdir collision, the validate-before-bump reorder) and must survive the
# retirement of any particular bundle. build_plugin.py itself is unchanged and
# still works the moment a new plugin manifest lands under plugins/.


def make_fixture_plugin(td, skills=('fake-skill',), description='Seven test skills',
                        version='0.1.0', with_skillmd=True):
    """Build a synthetic plugin tree under `td`; returns (root, plugins_dir)."""
    root = Path(td)
    plugins_dir = root / 'plugins'
    pdir = plugins_dir / PLUGIN
    pdir.mkdir(parents=True)
    for s in skills:
        sdir = root / s
        sdir.mkdir(exist_ok=True)
        if with_skillmd:
            (sdir / 'SKILL.md').write_text(f'---\nname: {s}\n---\nbody of {s}')
    (pdir / 'README.md').write_text('# fixture plugin\n')
    manifest = {
        'name': PLUGIN, 'version': version,
        'description': description, 'skills': list(skills),
    }
    (pdir / 'plugin-build.json').write_text(json.dumps(manifest))
    return root, plugins_dir


class PluginMembership(unittest.TestCase):
    def test_members_map_to_owning_plugin(self):
        # Membership is derived from manifests, not hardcoded. Verify the mapping
        # logic directly so it stays covered with no live bundle in the repo.
        manifests = {PLUGIN: {'skills': ['deal-retirement', 'submarket-spatial-analysis']}}
        members = ps._build_plugin_members(manifests)
        self.assertEqual(members['deal-retirement'], PLUGIN)
        self.assertEqual(members['submarket-spatial-analysis'], PLUGIN)

    def test_standalone_skill_is_not_a_member(self):
        self.assertIsNone(ps.plugin_of('acquisition-underwriting'))
        # debt-management is a standalone skill, NOT bundled (the 8-vs-7 defect)
        self.assertIsNone(ps.plugin_of('debt-management'))

    def test_retired_bundle_members_are_now_standalone(self):
        # Post-retirement invariant: nothing in the repo routes to a plugin.
        for s in ('deal-retirement', 'submarket-spatial-analysis',
                  'investor-relations', 'vendor-management'):
            self.assertIsNone(ps.plugin_of(s))

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
        with tempfile.TemporaryDirectory() as td:
            _root, plugins_dir = make_fixture_plugin(td)
            with mock.patch.object(bp, 'PLUGINS_DIR', plugins_dir):
                bm = bp.load_manifest(PLUGIN)
            shipped = bp.shipped_manifest(bm)
        self.assertNotIn('skills', shipped)
        self.assertIn('version', shipped)
        self.assertEqual(shipped['name'], PLUGIN)


class Entries(unittest.TestCase):
    """Packaging-shape coverage, run against a synthetic manifest so it survives
    the retirement of any individual bundle."""

    MEMBERS = ('alpha-skill', 'beta-skill', 'gamma-skill')

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root, self.plugins_dir = make_fixture_plugin(
            self._td.name, skills=self.MEMBERS,
            description='Three institutional skills for testing')
        with mock.patch.object(bp, 'PLUGINS_DIR', self.plugins_dir):
            self.bm = bp.load_manifest(PLUGIN)
            self.entries = bp.plugin_entries(PLUGIN, repo_root=self.root, bm=self.bm)

    def tearDown(self):
        self._td.cleanup()

    def test_all_forward_slash(self):
        self.assertFalse([a for a in self.entries if '\\' in a])

    def test_has_manifest_and_readme(self):
        self.assertIn('.claude-plugin/plugin.json', self.entries)
        self.assertIn('README.md', self.entries)

    def test_every_member_skill_present_with_skillmd(self):
        skills = self.bm['skills']
        self.assertEqual(len(skills), len(self.MEMBERS))
        for s in skills:
            self.assertIn(f'skills/{s}/SKILL.md', self.entries)

    def test_shipped_manifest_drops_skills_key_and_keeps_description(self):
        # Guards the 8-vs-7 defect class: the build-only `skills` key must never
        # ship, and the shipped description must be the manifest's own text (it
        # once drifted to name a skill that was not actually a member).
        pj = json.loads(self.entries['.claude-plugin/plugin.json'])
        self.assertNotIn('skills', pj)
        self.assertEqual(pj['description'], self.bm['description'])
        for s in self.MEMBERS:
            self.assertNotIn(s, pj.get('description', ''))

    def test_member_skillmd_bytes_equal_repo(self):
        for s in self.bm['skills']:
            repo_bytes = (self.root / s / 'SKILL.md').read_bytes()
            self.assertEqual(self.entries[f'skills/{s}/SKILL.md'], repo_bytes)


class BuildRoundTrip(unittest.TestCase):
    def test_build_writes_valid_zip(self):
        with tempfile.TemporaryDirectory() as td:
            root, plugins_dir = make_fixture_plugin(
                td, skills=('alpha-skill', 'beta-skill'))
            with mock.patch.object(bp, 'PLUGINS_DIR', plugins_dir):
                dest = bp.build_plugin(PLUGIN, root / 'out', repo_root=root)
            self.assertTrue(dest.is_file())
            with zipfile.ZipFile(dest) as z:
                names = z.namelist()
                self.assertIn('.claude-plugin/plugin.json', names)
                self.assertFalse([n for n in names if '\\' in n])
                pj = json.loads(z.read('.claude-plugin/plugin.json'))
                self.assertEqual(pj['name'], PLUGIN)


class RetiredBundleArchived(unittest.TestCase):
    """2026-08-05 retirement: the live manifest is gone, the archived copy remains
    as an audit trail, and every former member either still exists at the repo root
    or was deliberately retired to _archive/<name>_retired-<date>/."""

    MEMBERS = ('annual-cycle', 'capex-budgeting', 'cash-position-monitor',
               'deal-retirement', 'investor-relations',
               'submarket-spatial-analysis', 'vendor-management')

    # Former members later retired as standalone skills (Gabriel's call, per the
    # retiring commit). Declaring the date here is what distinguishes a deliberate
    # retirement from an accidental loss -- an undeclared missing member still fails.
    # Adding an entry is step 7.3 of README.md's retirement check.
    RETIRED = {
        'investor-relations': '2026-09-09',  # 2b24e9e
    }

    def test_live_manifest_is_gone(self):
        self.assertFalse((ps.REPO / 'plugins' / PLUGIN / 'plugin-build.json').exists())

    def test_archived_manifest_retained(self):
        self.assertTrue(
            (ps.REPO / '_archive' / 'plugins' / PLUGIN / 'plugin-build.json').is_file())

    def test_all_former_members_survive_at_repo_root(self):
        for s in self.MEMBERS:
            if s in self.RETIRED:
                continue
            self.assertTrue((ps.REPO / s / 'SKILL.md').is_file(), f'{s} lost its SKILL.md')

    def test_retired_former_members_are_archived_not_live(self):
        self.assertLessEqual(set(self.RETIRED), set(self.MEMBERS))
        for s, date in self.RETIRED.items():
            archived = ps.REPO / '_archive' / f'{s}_retired-{date}' / 'SKILL.md'
            self.assertTrue(archived.is_file(), f'{s} retired but not archived at {archived}')
            self.assertFalse((ps.REPO / s).exists(),
                             f'{s} is declared retired but is live at the repo root')


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
