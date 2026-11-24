"""Tests for tools/capture_runtime_cache.py: pure helpers, plus an end-to-end run against
a synthetic git repo / origin / cache (never the live repo or runtime cache)."""
import io
import os
import subprocess
import sys
from contextlib import redirect_stdout
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture_runtime_cache as crc  # noqa: E402

# Hermetic: never read the real AppData rpm store-plugin root (R34-6 follow-up). The
# pinned root exists (empty) because every sweep requires BOTH install roots reachable;
# tests that need an rpm install build one under their own fixture and pass rpm_root.
import pending_reimport as _pr_pin  # noqa: E402
_pr_pin.RPM_ROOT = Path(tempfile.mkdtemp(prefix='rpm_pin_')) / 'rpm'
_pr_pin.RPM_ROOT.mkdir()


class FingerprintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name) / 'demo-skill'
        self.d.mkdir()
        (self.d / 'SKILL.md').write_text('---\nname: demo-skill\n---\nbody\n', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_stable_when_nothing_changes(self):
        self.assertEqual(crc.fingerprint(self.d), crc.fingerprint(self.d))

    def test_changes_when_a_file_is_added(self):
        before = crc.fingerprint(self.d)
        (self.d / 'references').mkdir()
        (self.d / 'references' / 'x.md').write_text('x', encoding='utf-8')
        self.assertNotEqual(before, crc.fingerprint(self.d))

    def test_changes_when_content_size_changes(self):
        before = crc.fingerprint(self.d)
        (self.d / 'SKILL.md').write_text('---\nname: demo-skill\n---\nlonger body\n',
                                         encoding='utf-8')
        self.assertNotEqual(before, crc.fingerprint(self.d))

    def test_changes_when_mtime_moves(self):
        before = crc.fingerprint(self.d)
        t = time.time() + 120
        os.utime(self.d / 'SKILL.md', (t, t))
        self.assertNotEqual(before, crc.fingerprint(self.d))


class SelectionTests(unittest.TestCase):
    def test_changed_skills_new_and_moved_only(self):
        cur = {'a': '1', 'b': '2', 'c': '3'}
        prev = {'a': '1', 'b': 'old'}
        self.assertEqual(crc.changed_skills(cur, prev), ['b', 'c'])

    def test_changed_skills_first_run_is_everything(self):
        self.assertEqual(crc.changed_skills({'x': '1', 'y': '2'}, {}), ['x', 'y'])

    def test_files_to_capture_only_never_committed_verdicts(self):
        per = [('SKILL.md', 'CACHE-AHEAD'), ('scripts/a.py', 'IN-SYNC'),
               ('references/new.md', 'REPO-MISSING'), ('b.md', 'DIVERGENT'),
               ('c.md', 'MAIN-BEHIND-ORIGIN'), ('d.md', 'REPO-AHEAD'), ('e.md', 'UNKNOWN')]
        self.assertEqual(crc.files_to_capture(per), ['SKILL.md', 'references/new.md'])

    def test_files_to_capture_empty(self):
        self.assertEqual(crc.files_to_capture([('SKILL.md', 'IN-SYNC')]), [])

    def test_files_to_capture_drops_tool_debris(self):
        per = [('.pytest_cache/v/cache/nodeids', 'REPO-MISSING'),
               ('scripts/__pycache__/x.cpython-313.pyc', 'REPO-MISSING'),
               ('scripts/x.pyc', 'REPO-MISSING'),
               ('runs/summary.csv', 'CACHE-AHEAD')]
        self.assertEqual(crc.files_to_capture(per), ['runs/summary.csv'])


class IgnoreTests(unittest.TestCase):
    def test_parse_ignore_skips_comments_and_blanks(self):
        text = '# header\n\ndocx\n  pdf  # trailing note\n#xlsx\n'
        self.assertEqual(crc.parse_ignore(text), {'docx', 'pdf'})

    def test_shipped_ignore_file_parses_and_excludes_no_repo_skill(self):
        names = crc.load_ignore()
        self.assertIn('docx', names)
        repo = Path(__file__).resolve().parent.parent
        clashes = sorted(n for n in names if (repo / n / 'SKILL.md').is_file())
        self.assertEqual(clashes, [], 'an ORA repo skill must never be ignored')

    def test_installed_skills_honours_ignore(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for name in ('ora-a', 'docx', 'not-a-skill'):
                (root / name).mkdir()
            (root / 'ora-a' / 'SKILL.md').write_text('x', encoding='utf-8')
            (root / 'docx' / 'SKILL.md').write_text('x', encoding='utf-8')
            self.assertEqual(crc.installed_skills(root, {'docx'}), ['ora-a'])


class DedupTests(unittest.TestCase):
    def test_capture_then_identical_key_is_skipped(self):
        state = {}
        key = {'SKILL.md': 'abc'}
        self.assertFalse(crc.already_captured(state, 's', key))
        crc.record_capture(state, 's', key, 'capture/runtime-cache-1', 'now')
        self.assertTrue(crc.already_captured(state, 's', key))

    def test_new_content_is_not_treated_as_captured(self):
        state = {}
        crc.record_capture(state, 's', {'SKILL.md': 'abc'}, 'b1', 'now')
        self.assertFalse(crc.already_captured(state, 's', {'SKILL.md': 'def'}))
        self.assertFalse(crc.already_captured(state, 'other', {'SKILL.md': 'abc'}))


class TextTests(unittest.TestCase):
    def test_commit_message_names_files_verdicts_and_trailer(self):
        m = crc.commit_message('loi-generation', ['templates/T.docx'],
                               {'templates/T.docx': 'CACHE-AHEAD'}, '2026-09-24T18:19:43Z')
        self.assertTrue(m.startswith('capture(loi-generation): '))
        self.assertIn('- templates/T.docx: CACHE-AHEAD', m)
        self.assertIn('NOT\nreconciled', m)
        self.assertTrue(m.rstrip().endswith(crc.TRAILER))

    def test_pr_body_flags_do_not_merge_and_lists_rows(self):
        body = crc.pr_body([('annual-cycle', ['SKILL.md'], '2026-10-16T00:04:57Z'),
                            ('rent-roll-qc', ['SKILL.md', 'scripts/x.py'], 't2')], 'STAMP')
        self.assertIn('DO NOT MERGE AS-IS', body)
        self.assertIn('| annual-cycle | SKILL.md | 2026-10-16T00:04:57Z |', body)
        self.assertIn('| rent-roll-qc | SKILL.md, scripts/x.py | t2 |', body)
        self.assertIn('STAMP', body)


class ConfidentialGateTests(unittest.TestCase):
    def test_prepush_stdin_is_a_new_ref_line(self):
        line = crc.prepush_stdin('capture/runtime-cache-X', 'a' * 40)
        local_ref, local_sha, remote_ref, remote_sha = line.split()
        self.assertEqual(local_ref, 'refs/heads/capture/runtime-cache-X')
        self.assertEqual(remote_ref, local_ref)
        self.assertEqual(local_sha, 'a' * 40)
        self.assertEqual(remote_sha, '0' * 40)
        self.assertTrue(line.endswith('\n'))

    def test_missing_scanner_fails_closed(self):
        ok, detail = crc.confidential_gate('any-branch', scanner=Path('Z:/no/such/scan.py'))
        self.assertFalse(ok)
        self.assertIn('fail-closed', detail)


def _g(cwd, *args):
    r = subprocess.run(['git', '-C', str(cwd), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'git {args}: {r.stderr}')
    return r.stdout


class DenylistGateTests(unittest.TestCase):
    """The capture push must clear the real-identifier denylist (audit 2026-11-23, HIGH):
    captured content goes to the PUBLIC remote, and before this gate only the deal-roster
    scan ran. Missing, malformed or unreadable = blocked (fail closed, Gabriel 2026-11-23)."""

    TERM = 'Zephyrton Widget Holdings'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.repo = t / 'repo'
        self.repo.mkdir()
        for args in (('init', '-q', '-b', 'main'), ('config', 'user.email', 't@example.com'),
                     ('config', 'user.name', 't'), ('config', 'core.autocrlf', 'false')):
            _g(self.repo, *args)
        (self.repo / 'alpha').mkdir()
        (self.repo / 'alpha' / 'SKILL.md').write_text('---\nname: alpha\n---\nv1\n', encoding='utf-8')
        _g(self.repo, 'add', '-A')
        _g(self.repo, 'commit', '-q', '-m', 'init')
        origin = t / 'origin.git'
        _g(t, 'init', '-q', '--bare', str(origin))
        _g(self.repo, 'remote', 'add', 'origin', str(origin))
        _g(self.repo, 'push', '-q', 'origin', 'main')
        _g(self.repo, 'fetch', '-q', 'origin')
        self.deny = t / 'real-identifiers.local.json'
        self.deny.write_text('{"terms": ["%s", "000-999999"]}' % self.TERM, encoding='utf-8')
        self.saved = crc.REPO
        crc.REPO = self.repo

    def tearDown(self):
        crc.REPO = self.saved
        self.tmp.cleanup()

    def _branch(self, files, message='capture: alpha'):
        _g(self.repo, 'checkout', '-q', '-B', 'capture/x', 'origin/main')
        for rel, data in files.items():
            p = self.repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        _g(self.repo, 'add', '-A')
        _g(self.repo, 'commit', '-q', '-m', message)
        _g(self.repo, 'checkout', '-q', 'main')
        return 'capture/x'

    def test_default_denylist_lives_in_the_primary_checkout(self):
        self.assertEqual(crc.denylist_path(), self.repo / 'tools' / 'real-identifiers.local.json')

    def test_absent_denylist_fails_closed(self):
        b = self._branch({'alpha/SKILL.md': b'---\nname: alpha\n---\nclean\n'})
        ok, detail = crc.denylist_gate(b, denylist=self.deny.with_name('nope.json'))
        self.assertFalse(ok)
        self.assertIn('fail-closed', detail)

    def test_malformed_denylist_fails_closed(self):
        self.deny.write_text('{"terms": "not a list"}', encoding='utf-8')
        b = self._branch({'alpha/SKILL.md': b'clean\n'})
        ok, detail = crc.denylist_gate(b, denylist=self.deny)
        self.assertFalse(ok)
        self.assertIn('fail-closed', detail)

    def test_clean_capture_passes(self):
        b = self._branch({'alpha/SKILL.md': b'---\nname: alpha\n---\nv2 nothing real\n'})
        ok, detail = crc.denylist_gate(b, denylist=self.deny)
        self.assertTrue(ok, detail)

    def test_term_in_captured_file_blocks_and_is_not_echoed(self):
        b = self._branch({'beta/references/r.md': ('tenant: %s\n' % self.TERM).encode()})
        ok, detail = crc.denylist_gate(b, denylist=self.deny)
        self.assertFalse(ok)
        self.assertIn('beta/references/r.md', detail)
        self.assertNotIn('zephyrton', detail.casefold())

    def test_glued_term_in_a_slug_blocks(self):
        b = self._branch({'alpha/SKILL.md': b'see x-zephyrton-widget-holdings-tracker\n'})
        self.assertFalse(crc.denylist_gate(b, denylist=self.deny)[0])

    def test_term_in_commit_message_blocks(self):
        b = self._branch({'alpha/SKILL.md': b'clean\n'}, message='capture: %s notes' % self.TERM)
        ok, detail = crc.denylist_gate(b, denylist=self.deny)
        self.assertFalse(ok)
        self.assertIn('commit message', detail)

    def test_term_inside_a_docx_blocks(self):
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('word/document.xml', '<w:t>Zephyrton Widget</w:t><w:t> Holdings</w:t>')
        b = self._branch({'gamma/templates/t.docx': buf.getvalue()})
        self.assertFalse(crc.denylist_gate(b, denylist=self.deny)[0])

    def test_unscannable_binary_fails_closed(self):
        b = self._branch({'alpha/blob.bin': b'\x00\x01 opaque'})
        ok, detail = crc.denylist_gate(b, denylist=self.deny)
        self.assertFalse(ok)
        self.assertIn('fail-closed', detail)

    # --- review round 1 (2026-11-23): skips must block, every fail-closed branch pinned ---
    def _blocks(self, files, **kw):
        ok, detail = crc.denylist_gate(self._branch(files, **kw), denylist=self.deny)
        self.assertFalse(ok, detail)
        self.assertNotIn('zephyrton', detail.casefold())
        return detail

    def test_empty_denylist_fails_closed(self):
        self.deny.write_text('{"terms": []}', encoding='utf-8')
        self.assertIn('fail-closed', self._blocks({'alpha/SKILL.md': b'clean\n'}))

    def test_unknown_base_ref_fails_closed(self):
        b = self._branch({'alpha/SKILL.md': b'clean\n'})
        ok, detail = crc.denylist_gate(b, denylist=self.deny, base_ref='refs/no/such')
        self.assertFalse(ok)
        self.assertIn('fail-closed', detail)

    def test_unreadable_blob_fails_closed(self):
        b = self._branch({'alpha/SKILL.md': b'clean\n'})
        real = crc._git_bytes

        def flaky(*args):
            if args[0] == 'cat-file':
                raise RuntimeError('boom')
            return real(*args)
        crc._git_bytes = flaky
        try:
            ok, detail = crc.denylist_gate(b, denylist=self.deny)
        finally:
            crc._git_bytes = real
        self.assertFalse(ok)
        self.assertIn('fail-closed', detail)

    def test_media_file_cannot_be_cleared(self):
        self.assertIn('fail-closed', self._blocks({'alpha/shot.png': b'\x89PNG plain bytes'}))

    def test_text_named_like_media_cannot_be_cleared(self):
        self._blocks({'alpha/notes.png': ('%s\n' % self.TERM).encode()})

    def test_archive_binary_cannot_be_cleared(self):
        self._blocks({'_archive/x.bin': b'\x00\x01 opaque'})

    def test_utf32_text_is_scanned(self):
        self._blocks({'alpha/u.md': ('﻿%s\n' % self.TERM).encode('utf-32-le')})

    def test_term_in_the_file_name_blocks_and_the_path_is_redacted(self):
        detail = self._blocks({'alpha/zephyrton-widget-holdings.md': b'clean\n'})
        self.assertIn('redacted', detail)

    def test_non_ascii_file_name_is_scanned_not_wedged(self):
        b = self._branch({'alpha/café.md': b'clean\n'})
        ok, detail = crc.denylist_gate(b, denylist=self.deny)
        self.assertTrue(ok, detail)
        self._blocks({'alpha/café.md': ('%s\n' % self.TERM).encode()})

    def test_docx_with_an_embedded_object_cannot_be_cleared(self):
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('word/document.xml', '<w:t>clean</w:t>')
            z.writestr('word/embeddings/sheet.xlsx', b'PK opaque')
        self._blocks({'gamma/t.docx': buf.getvalue()})

    def _pdf(self, page_text='clean', meta_title='', annot=''):
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), page_text)
        if annot:
            a = page.add_text_annot((100, 100), annot)
            a.update()
        if meta_title:
            doc.set_metadata({'title': meta_title})
        data = doc.tobytes()
        doc.close()
        return data

    def test_clean_pdf_passes(self):
        b = self._branch({'alpha/ref.pdf': self._pdf()})
        ok, detail = crc.denylist_gate(b, denylist=self.deny)
        self.assertTrue(ok, detail)

    def test_term_only_in_pdf_metadata_blocks(self):
        self._blocks({'alpha/ref.pdf': self._pdf(meta_title=self.TERM)})

    def test_term_only_in_pdf_annotation_blocks(self):
        self._blocks({'alpha/ref.pdf': self._pdf(annot=self.TERM)})

    def test_archived_pdf_is_scanned_not_skipped(self):
        self._blocks({'_archive/ref.pdf': self._pdf(page_text=self.TERM)})
        # and a CLEAN archived PDF passes, so it is scanned, not blanket-blocked
        b = self._branch({'_archive/ok.pdf': self._pdf()})
        ok, detail = crc.denylist_gate(b, denylist=self.deny)
        self.assertTrue(ok, detail)

    def test_term_only_in_pdf_xmp_blocks(self):
        import fitz
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), 'clean')
        doc.set_xml_metadata('<x:xmpmeta xmlns:x="adobe:ns:meta/"><d>%s</d></x:xmpmeta>' % self.TERM)
        data = doc.tobytes()
        doc.close()
        self._blocks({'alpha/ref.pdf': data})

    def test_pdf_with_an_embedded_file_cannot_be_cleared(self):
        import fitz
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), 'clean')
        doc.embfile_add('a.bin', b'opaque')
        data = doc.tobytes()
        doc.close()
        self.assertIn('fail-closed', self._blocks({'alpha/ref.pdf': data}))

    def test_image_only_pdf_cannot_be_cleared(self):
        import fitz
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 4, 4), False)
        doc = fitz.open()
        doc.new_page().insert_image(fitz.Rect(0, 0, 40, 40), pixmap=pix)
        data = doc.tobytes()
        doc.close()
        self.assertIn('fail-closed', self._blocks({'alpha/scan.pdf': data}))

    def test_term_only_in_pdf_outline_blocks(self):
        import fitz
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), 'clean')
        doc.set_toc([[1, self.TERM, 1]])
        data = doc.tobytes()
        doc.close()
        self._blocks({'alpha/ref.pdf': data})

    def test_inline_data_uri_image_cannot_be_cleared(self):
        self._blocks({'alpha/page.html': b'<img src="data:image/png;base64,iVBORw0KGgo=">\n'})

    # --- review round 3 ---
    def test_parameterised_data_uri_cannot_be_cleared(self):
        self._blocks({'alpha/a.svg': b'<image href="data:image/svg+xml;charset=utf-8;base64,PHN2Zz4="/>\n'})
        self._blocks({'alpha/b.html': b'<img src="data:image/png;name=a.png;base64,iVBORw0KGgo=">\n'})

    def test_utf32_text_with_a_data_uri_cannot_be_cleared(self):
        self._blocks({'alpha/u.html': '﻿<img src="data:image/png;base64,iVBO=">\n'.encode('utf-32-le')})

    def _png(self):
        import fitz
        return fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 4, 4), False).tobytes('png')

    def test_image_stamp_annotation_pdf_cannot_be_cleared(self):
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), 'clean')
        page.add_stamp_annot(fitz.Rect(100, 100, 140, 140), stamp=self._png())
        data = doc.tobytes()
        doc.close()
        self._blocks({'alpha/signed.pdf': data})

    def test_inline_image_pdf_cannot_be_cleared(self):
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        # An inline image (BI ... ID ... EI) in the page content stream: no page image resource.
        stream = b'q 40 0 0 40 72 600 cm BI /W 2 /H 2 /CS /G /BPC 8 ID \x00\xff\xff\x00 EI Q'
        xref = doc.get_new_xref()
        doc.update_object(xref, '<<>>')
        doc.update_stream(xref, stream)
        doc.xref_set_key(page.xref, 'Contents', f'{xref} 0 R')
        data = doc.tobytes()
        doc.close()
        self._blocks({'alpha/scan.pdf': data})

    def test_term_only_in_pdf_link_uri_blocks(self):
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), 'clean')
        page.insert_link({'kind': fitz.LINK_URI, 'from': fitz.Rect(72, 60, 200, 80),
                          'uri': 'https://example.com/zephyrton-widget-holdings'})
        data = doc.tobytes()
        doc.close()
        self._blocks({'alpha/ref.pdf': data})

    def test_term_only_in_pdf_page_label_blocks(self):
        import fitz
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), 'clean')
        doc.set_page_labels([{'startpage': 0, 'prefix': self.TERM + '-', 'style': 'D', 'firstpagenum': 1}])
        data = doc.tobytes()
        doc.close()
        self._blocks({'alpha/ref.pdf': data})

    def test_push_and_pr_never_pushes_when_the_denylist_gate_blocks(self):
        b = self._branch({'alpha/SKILL.md': ('%s\n' % self.TERM).encode()})
        calls = []
        saved = (crc.confidential_gate, crc._git, crc.denylist_path)
        real_git = crc._git
        crc.confidential_gate = lambda branch: (True, 'ok')
        crc.denylist_path = lambda: self.deny
        crc._git = lambda *a, **k: (calls.append(a), real_git(*a, **k))[1]
        try:
            with self.assertRaises(RuntimeError) as cm:
                crc.push_and_pr({'branch': b, 'rows': [], 'stamp': 'x'})
        finally:
            crc.confidential_gate, crc._git, crc.denylist_path = saved
        self.assertFalse([a for a in calls if a and a[0] == 'push'], calls)
        self.assertIn('denylist', str(cm.exception))
        self.assertNotIn('zephyrton', str(cm.exception).casefold())


class EndToEndTests(unittest.TestCase):
    """Real git, synthetic repo + origin + cache: proves a run commits exactly the
    cache-only files to a capture branch, with the repo's hooks disabled, removes its
    worktree, and that an identical second run captures nothing."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.repo, self.cache, self.marker = t / 'repo', t / 'cache', t / 'hook-fired.txt'
        self.repo.mkdir()
        _g(self.repo, 'init', '-q', '-b', 'main')
        _g(self.repo, 'config', 'user.email', 't@example.com')
        _g(self.repo, 'config', 'user.name', 't')
        _g(self.repo, 'config', 'core.autocrlf', 'false')
        hooks = t / 'hooks'
        hooks.mkdir()
        for name in ('pre-commit', 'post-commit'):
            h = hooks / name
            h.write_text(f'#!/bin/sh\necho {name} >> "{self.marker.as_posix()}"\n',
                         encoding='utf-8', newline='\n')
            h.chmod(0o755)
        _g(self.repo, 'config', 'core.hooksPath', hooks.as_posix())
        (self.repo / 'alpha').mkdir()
        (self.repo / 'alpha' / 'SKILL.md').write_text(
            '---\nname: alpha\ndescription: d\n---\nv1\n', encoding='utf-8', newline='\n')
        _g(self.repo, 'add', '-A')
        _g(self.repo, 'commit', '-q', '-m', 'init')
        self.hooks_fire_normally = self.marker.exists()
        if self.marker.exists():
            self.marker.unlink()
        origin = t / 'origin.git'
        _g(t, 'init', '-q', '--bare', str(origin))
        _g(self.repo, 'remote', 'add', 'origin', str(origin))
        _g(self.repo, 'push', '-q', 'origin', 'main')
        _g(self.repo, 'fetch', '-q', 'origin')
        # cache: alpha edited platform-side (CACHE-AHEAD); beta created platform-side
        (self.cache / 'alpha').mkdir(parents=True)
        (self.cache / 'alpha' / 'SKILL.md').write_text(
            '---\nname: alpha\ndescription: d\n---\nv1\nv2 saved from Cowork\n',
            encoding='utf-8', newline='\n')
        (self.cache / 'beta' / 'references').mkdir(parents=True)
        (self.cache / 'beta' / 'SKILL.md').write_text(
            '---\nname: beta\ndescription: new\n---\nbody\n', encoding='utf-8', newline='\n')
        (self.cache / 'beta' / 'references' / 'r.md').write_text('ref\n', encoding='utf-8')
        (self.cache / 'beta' / '.pytest_cache').mkdir()
        (self.cache / 'beta' / '.pytest_cache' / 'README.md').write_text('x', encoding='utf-8')

        self.saved = {k: getattr(crc, k) for k in
                      ('REPO', 'WORKTREE_PARENT', 'STATE_DIR', 'STATE_FILE', 'LOG_FILE',
                       'LOCK_FILE', 'push_and_pr')}
        crc.REPO = self.repo
        crc.WORKTREE_PARENT = t / 'wts'
        crc.STATE_DIR = t / 'state'
        crc.STATE_FILE = crc.STATE_DIR / 'state.json'
        crc.LOG_FILE = crc.STATE_DIR / 'capture.log'
        crc.LOCK_FILE = crc.STATE_DIR / '.lock'
        self.pushed = []
        crc.push_and_pr = lambda entry: (self.pushed.append(entry), 'https://example/pr/1')[1]

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(crc, k, v)
        subprocess.run(['git', '-C', str(self.repo), 'worktree', 'prune'], capture_output=True)
        self.tmp.cleanup()

    def test_capture_run(self):
        self.assertTrue(self.hooks_fire_normally, 'control: repo hooks must fire on a normal commit')
        with redirect_stdout(io.StringIO()):
            rc = crc.run(full=True, dry_run=False, cache_root=self.cache)
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.pushed), 1)
        entry = self.pushed[0]
        self.assertEqual([r[0] for r in entry['rows']], ['alpha', 'beta'])
        self.assertEqual(entry['rows'][1][1], ['SKILL.md', 'references/r.md'])
        branch = entry['branch']
        self.assertTrue(branch.startswith(crc.BRANCH_PREFIX))
        self.assertIn('v2 saved from Cowork', _g(self.repo, 'show', f'{branch}:alpha/SKILL.md'))
        self.assertEqual(_g(self.repo, 'show', f'{branch}:beta/references/r.md'), 'ref\n')
        files = _g(self.repo, 'ls-tree', '-r', '--name-only', branch).split()
        self.assertNotIn('beta/.pytest_cache/README.md', files)
        self.assertEqual(_g(self.repo, 'rev-list', '--count', f'origin/main..{branch}').strip(), '2')
        msg = _g(self.repo, 'log', '-1', '--format=%B', branch)
        self.assertIn(crc.TRAILER, msg)
        self.assertFalse(self.marker.exists(), 'capture commits must run with hooks disabled')
        self.assertNotIn('_runtime-capture-', _g(self.repo, 'worktree', 'list'))
        state = crc.load_state()
        self.assertEqual(state['pending_push'], [])
        self.assertEqual(sorted(state['captured']), ['alpha', 'beta'])
        # identical second run: fingerprints unchanged, nothing new to capture
        with redirect_stdout(io.StringIO()):
            self.assertEqual(crc.run(full=False, dry_run=False, cache_root=self.cache), 0)
            self.assertEqual(crc.run(full=True, dry_run=False, cache_root=self.cache), 0)
        self.assertEqual(len(self.pushed), 1, 'already-captured content must not be re-captured')

    def test_dry_run_writes_nothing(self):
        with redirect_stdout(io.StringIO()):
            rc = crc.run(full=True, dry_run=True, cache_root=self.cache)
        self.assertEqual(rc, 0)
        self.assertEqual(self.pushed, [])
        self.assertFalse(crc.STATE_FILE.exists())
        self.assertNotIn(crc.BRANCH_PREFIX, _g(self.repo, 'branch', '--list'))



class RpmStorePluginCapture(EndToEndTests):
    """R34-6 follow-up: the capture enumerates and reads rpm store-plugin installs too.
    Same fixture as EndToEndTests, but alpha's platform-side edit lives ONLY under the
    rpm root (legacy cache holds beta alone)."""

    def setUp(self):
        super().setUp()
        import shutil
        self.rpm = Path(self.tmp.name) / 'rpm'
        dest = self.rpm / 'plugin_A' / 'skills' / 'alpha'
        dest.parent.mkdir(parents=True)
        shutil.move(str(self.cache / 'alpha'), str(dest))

    def test_capture_run(self):
        with redirect_stdout(io.StringIO()):
            rc = crc.run(full=True, dry_run=False, cache_root=self.cache, rpm_root=self.rpm)
        self.assertEqual(rc, 0)
        self.assertEqual([r[0] for r in self.pushed[0]['rows']], ['alpha', 'beta'])
        branch = self.pushed[0]['branch']
        self.assertIn('v2 saved from Cowork', _g(self.repo, 'show', f'{branch}:alpha/SKILL.md'))

    def test_dry_run_writes_nothing(self):
        with redirect_stdout(io.StringIO()):
            rc = crc.run(full=True, dry_run=True, cache_root=self.cache, rpm_root=self.rpm)
        self.assertEqual(rc, 0)
        self.assertEqual(self.pushed, [])

    def test_installed_skills_spans_both_roots(self):
        self.assertEqual(crc.installed_skills(self.cache, rpm_root=self.rpm), ['alpha', 'beta'])
        self.assertEqual(crc.installed_skills(self.cache, {'alpha'}, rpm_root=self.rpm), ['beta'])

    def test_unreachable_rpm_root_is_an_error_and_captures_nothing(self):
        with redirect_stdout(io.StringIO()):
            rc = crc.run(full=True, dry_run=False, cache_root=self.cache,
                         rpm_root=Path(self.tmp.name) / 'no-rpm')
        self.assertEqual(rc, 1)
        self.assertEqual(self.pushed, [])
        self.assertFalse(crc.STATE_FILE.exists())


if __name__ == '__main__':
    unittest.main()
