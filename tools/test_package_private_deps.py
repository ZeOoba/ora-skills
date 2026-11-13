"""Packager handling of PRIVATE_LOCAL_DEPS (the gitignored RCT table). Run: python tools/test_package_private_deps.py

Every figure here is INVENTED (acquisition-underwriting/scripts/fixtures/rct-table.synthetic.json).
Never use a real RCT value in this file.
"""
import copy
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import package_skills  # noqa: E402

TOOLS = Path(__file__).resolve().parent
FIXTURE = TOOLS.parent / 'acquisition-underwriting' / 'scripts' / 'fixtures' / 'rct-table.synthetic.json'
SYN = json.loads(FIXTURE.read_text(encoding='utf-8'))


def ratified_shape():
    t = copy.deepcopy(SYN)
    t.pop('_synthetic', None)
    t['rctVersion'] = 'RCT v03'
    return t


def engine_schema(t):
    """The same figures in the authoritative file's (engine) schema, with its own Chicago key."""
    inv = {v: k for k, v in package_skills.RCT_MASTER_ALIASES.items()}
    return {'rctVersion': 'replacement-cost.vX', 'markets': {
        inv.get(k, k): {'low': m['low'], 'point': m['point'], 'high': m['high'], 'cwHardPsf': m['cwHard'],
                        'proxy': False} for k, m in t['markets'].items()}}


def synthetic_cw(t):
    """Invented C&W tiers that the table's own derivation parameters reproduce exactly (inverse of
    rct_table.derivation_mismatches), so the packaging tie can be exercised without real data."""
    import math
    d = t['derivation']
    out = {}
    for name, m in t['markets'].items():
        small = m['cwHard']
        b = math.log(m['point'] / (small * d['softCostMultiplier'] * d['escalation'])) / math.log(109_200 / d['referenceSf'])
        out[f'SYN {name}'] = {'small25': small, 'med25': small / math.exp(b * math.log(476_400 / 109_200))}
    return out


class PrivateDeps(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='pkg_private_'))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        skill = self.tmp / 'demo-skill'
        skill.mkdir()
        (skill / 'SKILL.md').write_text('---\nname: demo-skill\ndescription: d\n---\n# Demo\n', encoding='utf-8')
        self.out = self.tmp / 'out'
        self.out.mkdir()
        self.cw = self.tmp / 'cw.json'
        self.write(self.cw, synthetic_cw(ratified_shape()))
        self.master = self.tmp / 'private' / 'replacement-cost.json'
        self.write(self.master, engine_schema(ratified_shape()))
        env = {k: v for k, v in os.environ.items() if k not in ('ORA_RCT_TABLE', 'ORA_RCT_TABLE_PATH')}
        env['ORA_RCT_TABLE_PATH'] = str(self.master)
        for p in (mock.patch.dict(os.environ, env, clear=True),
                  mock.patch.object(package_skills, 'REPO', self.tmp),
                  mock.patch.object(package_skills, 'SHARED_ROOT_DEPS', {}),
                  mock.patch.object(package_skills, 'RCT_CW_FILE', self.cw),
                  mock.patch.object(package_skills, 'PRIVATE_LOCAL_DEPS',
                                    {'demo-skill': [package_skills.RCT_TABLE_FILE]}),
                  mock.patch.object(package_skills, 'validate_frontmatter', lambda *a, **k: None)):
            p.start()
            self.addCleanup(p.stop)

    def write(self, path, table):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(table if isinstance(table, str) else json.dumps(table), encoding='utf-8')

    def package(self):
        with redirect_stdout(io.StringIO()):
            return package_skills.package('demo-skill', self.out)

    def assert_refused(self, needle):
        with self.assertRaises(SystemExit) as cm:
            self.package()
        self.assertIn(needle, str(cm.exception))
        self.assertFalse((self.out / 'demo-skill.skill').exists(), 'no partial package may be written')
        return str(cm.exception)

    def test_missing_table_refuses(self):
        self.assert_refused('not found')

    def test_synthetic_table_refused(self):
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, SYN)
        self.assert_refused('not a valid ratified RCT table')

    def test_malformed_table_refused(self):
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, '{nope')
        self.assert_refused('not a valid ratified RCT table')

    def test_valid_repo_root_copy_ships_at_skill_root(self):
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, ratified_shape())
        with zipfile.ZipFile(self.package()) as z:
            self.assertIn('demo-skill/rct-table.local.json', z.namelist())
            self.assertEqual(json.loads(z.read('demo-skill/rct-table.local.json')), ratified_shape())

    def test_private_folder_copy_used_from_a_clean_worktree(self):
        self.write(self.master.parent / package_skills.RCT_TABLE_FILE, ratified_shape())
        with zipfile.ZipFile(self.package()) as z:
            self.assertIn('demo-skill/rct-table.local.json', z.namelist())

    def test_copy_that_does_not_tie_to_the_authoritative_table_refuses(self):
        master = engine_schema(ratified_shape())
        row = master['markets']['Columbus OH']
        row.update(point=row['point'] + 10, low=row['low'] + 9, high=row['high'] + 11)
        self.write(self.master, master)
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, ratified_shape())
        msg = self.assert_refused('does not tie to the authoritative')
        self.assertIn('Columbus OH.point', msg)
        self.assertNotIn(str(row['point']), msg, 'never print a figure')

    def test_cw_hard_must_tie_too(self):
        master = engine_schema(ratified_shape())
        master['markets']['Madison WI']['cwHardPsf'] += 1
        self.write(self.master, master)
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, ratified_shape())
        self.assert_refused('Madison WI.cwHard')

    def test_derivation_parameters_must_reproduce_every_row(self):
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, ratified_shape())
        shifted = ratified_shape()
        shifted['derivation']['escalation'] += 0.01  # a stale escalation no longer reproduces the rows
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, shifted)
        msg = self.assert_refused('do not reproduce')
        self.assertIn('Columbus OH', msg)

    def test_unreadable_cw_tiers_refuse(self):
        self.cw.unlink()
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, ratified_shape())
        self.assert_refused('cannot read the C&W tiers')

    def test_mixed_case_stray_copy_never_ships(self):
        self.write(self.tmp / 'demo-skill' / 'RCT-Table.local.json', '{"stray": true}')
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, ratified_shape())
        with zipfile.ZipFile(self.package()) as z:
            self.assertNotIn('demo-skill/RCT-Table.local.json', z.namelist())

    def test_mirror_sync_moves_a_stale_copy_out_when_validation_fails(self):
        # Round-2 review: leaving the old mirror copy in place meant Code kept running on stale figures.
        mirror = self.tmp / 'mirror' / 'demo-skill'
        self.write(mirror / package_skills.RCT_TABLE_FILE, ratified_shape())
        archive = self.tmp / 'archive'
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, SYN)  # source now invalid
        files, _ = self.listing()
        lines = package_skills.retire_stale_private('demo-skill', mirror, files, archive_root=archive)
        self.assertFalse((mirror / package_skills.RCT_TABLE_FILE).exists())
        moved = list(archive.rglob(package_skills.RCT_TABLE_FILE))
        self.assertEqual(len(moved), 1, 'moved, never deleted')
        self.assertIn('moved to', lines[0])

    def test_mirror_sync_keeps_a_copy_that_still_validates(self):
        mirror = self.tmp / 'mirror' / 'demo-skill'
        self.write(mirror / package_skills.RCT_TABLE_FILE, ratified_shape())
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, ratified_shape())
        files, _ = self.listing()
        self.assertEqual(package_skills.retire_stale_private('demo-skill', mirror, files, self.tmp / 'a'), [])
        self.assertTrue((mirror / package_skills.RCT_TABLE_FILE).exists())

    def test_missing_authoritative_table_refuses(self):
        self.master.unlink()
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, ratified_shape())
        self.assert_refused('cannot read the authoritative RCT table')

    def test_stray_copy_inside_skill_dir_never_ships(self):
        self.write(self.tmp / 'demo-skill' / package_skills.RCT_TABLE_FILE, '{"stray": true}')
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, ratified_shape())
        with zipfile.ZipFile(self.package()) as z:
            names = z.namelist()
            self.assertEqual(names.count('demo-skill/rct-table.local.json'), 1)
            self.assertEqual(json.loads(z.read('demo-skill/rct-table.local.json')), ratified_shape())

    def listing(self):
        with redirect_stderr(io.StringIO()) as err:
            files = package_skills.skill_source_files('demo-skill', self.tmp)
        return files, err.getvalue()

    def test_source_listing_includes_a_valid_tied_file_without_raising(self):
        self.assertNotIn('rct-table.local.json', self.listing()[0])
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, ratified_shape())
        self.assertEqual(self.listing()[0]['rct-table.local.json'], self.tmp / package_skills.RCT_TABLE_FILE)

    def test_source_listing_leaves_out_an_invalid_or_untied_file(self):
        # The listing feeds the ~/.claude/skills and AppData mirror syncs (adversarial review 2026-11-13).
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, SYN)  # synthetic: invalid
        files, err = self.listing()
        self.assertNotIn('rct-table.local.json', files)
        self.assertIn('left out', err)
        master = engine_schema(ratified_shape())
        master['markets']['Columbus OH']['point'] += 10
        self.write(self.master, master)
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, ratified_shape())  # valid but untied
        files, err = self.listing()
        self.assertNotIn('rct-table.local.json', files)
        self.assertNotIn(str(master['markets']['Columbus OH']['point']), err, 'never print a figure')

    def test_master_row_that_is_not_an_object_is_a_mismatch(self):
        master = engine_schema(ratified_shape())
        master['markets']['Columbus OH'] = None
        self.write(self.master, master)
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, ratified_shape())
        self.assert_refused('Columbus OH (no row object')

    def test_alias_collision_in_master_is_a_mismatch(self):
        master = engine_schema(ratified_shape())
        master['markets']['Chicago-Cook IL'] = dict(master['markets']['Chicago Cook County IL'], point=1.0)
        self.write(self.master, master)
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, ratified_shape())
        self.assert_refused('alias collision')

    def test_stray_copy_at_any_depth_never_ships(self):
        self.write(self.tmp / 'demo-skill' / 'references' / package_skills.RCT_TABLE_FILE, '{"stray": true}')
        self.write(self.tmp / package_skills.RCT_TABLE_FILE, ratified_shape())
        with zipfile.ZipFile(self.package()) as z:
            self.assertEqual([n for n in z.namelist() if n.endswith(package_skills.RCT_TABLE_FILE)],
                             ['demo-skill/rct-table.local.json'])


class Declared(unittest.TestCase):
    def test_every_rct_reading_skill_is_declared(self):
        # A SKILL.md that tells the agent to read the private table must ship it, or it fails closed forever.
        repo = TOOLS.parent
        readers = {d.name for d in repo.iterdir()
                   if (d / 'SKILL.md').is_file()
                   and package_skills.RCT_TABLE_FILE in (d / 'SKILL.md').read_text(encoding='utf-8')}
        self.assertEqual(readers - set(package_skills.PRIVATE_LOCAL_DEPS), set(),
                         'a SKILL.md reads the table but its package would not carry it')
        self.assertEqual(set(package_skills.PRIVATE_LOCAL_DEPS) - readers, set(),
                         'a skill ships the table but its SKILL.md never says where to read it')


if __name__ == '__main__':
    unittest.main()
