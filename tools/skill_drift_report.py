#!/usr/bin/env python3
"""skill_drift_report.py - deterministic SKILL.md drift verdict for ora-skill-store-drift-check.

WHY THIS EXISTS (2026-08-03): the ora-skill-store-drift-check task's step-2 verdict
was prose the model executed by eye. It read stale VERSION TOKENS -- frontmatter and
index descriptions, changelog dates -- instead of file content. The 2026-08-03 run
reported 12 skills CACHE-NEWER and prescribed a byte-exact cache->repo pull for all
12. Verification against disk invalidated 10:

  * 9 were already EOL-normalized IN-SYNC, and 7 of those were BYTE-IDENTICAL to
    the cache. No content comparison can produce those flags.
  * market-monitor and tenant-email differed only in CRLF line endings.
  * acquisition-underwriting was reported as cache v4.6 / 138,460 B while the cache
    actually held v4.7 / 146,847 B -- the figures were already stale when read.

Worse than nuisance: of the 3 genuinely-drifted skills, NONE could take the
prescribed byte-exact copy. parcel-data-recovery's cache frontmatter description had
collapsed 850 -> 203 chars, losing every trigger phrase; a byte-exact pull would have
silently destroyed that skill's entire routing surface.

WHAT THIS MODULE GUARANTEES
  1. The verdict is sha256(bytes.replace(b'\\r\\n', b'\\n')) on BOTH sides. A
     CRLF-only difference can never surface as drift. Version tokens are reported
     but are NEVER an input to the verdict.
  2. Frontmatter and body are compared SEPARATELY and reported as distinct findings.
     Cache-newer body + repo-newer description is the recurring real-world pattern.
  3. When neither side is a superset, the verdict is MANUAL-MERGE -- never the
     byte-exact-pull remedy.
  4. Every version/byte figure lives under a `point_in_time` dict stamped with the
     read time and rendered "NOT authoritative". The cache is live: it changed
     underneath a single session between two verification passes on 2026-08-03.
     `stability` re-hashes at the end of the run and flags CHANGED-DURING-RUN.

SCOPE: SKILL.md only -- the step-2 verdict. Bundled-file completeness (step 2d) and
shared repo-root dependency content (step 2e) stay with pending_reimport.py's
skill_source_files()/shared_dep_report(), which this module deliberately does not
duplicate.

Usage: python tools/skill_drift_report.py [--json] [skill ...]
       (no skill args = every skill dir in the repo that has a SKILL.md)
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from package_skills import REPO, SKIP  # noqa: E402
from pending_reimport import (  # noqa: E402
    CACHE_ROOT, _git_blob_bytes, _git_text, all_skill_dirs, classify_shared_copy,
)

# --- verdicts -------------------------------------------------------------
IN_SYNC = 'IN-SYNC'
REPO_NEWER = 'REPO-NEWER'
CACHE_NEWER = 'CACHE-NEWER'
MANUAL_MERGE = 'MANUAL-MERGE'
NOT_INSTALLED = 'NOT-INSTALLED'

# --- text relations (containment, not direction) --------------------------
IDENTICAL = 'IDENTICAL'
REPO_SUPERSET = 'REPO-SUPERSET'
CACHE_SUPERSET = 'CACHE-SUPERSET'
DISJOINT = 'DISJOINT'

# --- directions (git-ancestry derived; classify_shared_copy's vocabulary) --
IN_SYNC_DIR = 'IN-SYNC'
REPO_AHEAD = 'REPO-AHEAD'
CACHE_AHEAD = 'CACHE-AHEAD'
DIVERGENT = 'DIVERGENT'
UNKNOWN = 'UNKNOWN'

# --- finding kinds --------------------------------------------------------
PART_DRIFT = 'PART-DRIFT'
DESCRIPTION_REGRESSION = 'DESCRIPTION-REGRESSION'

# --- stability ------------------------------------------------------------
STABLE = 'STABLE'
CHANGED_DURING_RUN = 'CHANGED-DURING-RUN'

PARTS = ('frontmatter', 'body')

# Platform import limit; a merged description must still fit (pre-commit Check 2).
MAX_DESC = 1024

REMEDY = {
    IN_SYNC: 'none',
    REPO_NEWER: (
        're-upload to Cowork/claude.ai needed - stage it with the package-and-stage-skill '
        'skill (runs tools/package_skills.py and surfaces a one-click Save-skill '
        'installer; registration stays a human click)'
    ),
    CACHE_NEWER: (
        'REPO-FIRST VIOLATION - pull cache into repo. Every differing part is a clean '
        'cache-side superset, so the byte-exact copy in the CACHE->REPO RECOVERY '
        'PROCEDURE is safe here; still content-verify and open a PR, never commit to main'
    ),
    MANUAL_MERGE: (
        'MANUAL MERGE required - neither side is a superset, so NO byte-exact copy in '
        'either direction. Reconcile frontmatter and body independently in a supervised '
        f'session (merged description must stay <= {MAX_DESC} chars), then PR'
    ),
    NOT_INSTALLED: 'none - no cache directory; never installed (this is not drift)',
}

_DESC_RE = re.compile(r'^description:\s*(.*)$', re.M)
_VERSION_RE = re.compile(r'\bv(\d+\.\d+)\b')


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def normalized_text(data: bytes) -> str:
    """Decode, strip trailing NUL padding, normalize CRLF->LF.

    Trailing NULs are a platform-upload artifact, not content (drift-check step 2b,
    confirmed disposition-analysis 2026-06-15: 6366 B on disk incl. padding vs 6211 B
    clean text). Stripping them here means a padded-but-identical file reads IN-SYNC.
    """
    return data.rstrip(b'\x00').decode('utf-8', errors='replace').replace('\r\n', '\n')


def norm_hash(data: bytes) -> str:
    """sha256 of the EOL-normalized bytes - the documented verdict formula.

    Equivalent to pending_reimport._normalized_hash_bytes for text; kept local so
    the NUL-padding strip is inside the hashed form too.
    """
    return hashlib.sha256(normalized_text(data).encode('utf-8')).hexdigest()


def split_skill_md(text: str) -> tuple[str, str]:
    """('frontmatter inner text', 'body') for a normalized SKILL.md.

    Only a leading '---' fence opens frontmatter, and only the FIRST subsequent
    '---' line closes it - a horizontal rule later in the body cannot truncate it.
    No frontmatter -> ('', whole text), so a malformed file still gets a body diff
    rather than being skipped.
    """
    if not text.startswith('---\n'):
        return '', text
    rest = text[4:]
    for m in re.finditer(r'^---\s*$', rest, re.M):
        return rest[:m.start()], rest[m.end():].lstrip('\n')
    return '', text


def description_of(frontmatter: str) -> str | None:
    m = _DESC_RE.search(frontmatter)
    return m.group(1).strip() if m else None


def version_token_of(text: str) -> str | None:
    """First vX.Y marker. REPORTED ONLY - never an input to the verdict. This is
    exactly the signal the broken check mistook for evidence."""
    m = _VERSION_RE.search(text)
    return f'v{m.group(1)}' if m else None


def _line_subset(inner: str, outer: str) -> bool:
    """Every non-blank line of `inner` appears in `outer` at least as often."""
    ic = Counter(ln for ln in inner.splitlines() if ln.strip())
    oc = Counter(ln for ln in outer.splitlines() if ln.strip())
    return all(oc[ln] >= n for ln, n in ic.items())


def _contains(outer: str, inner: str) -> bool:
    return inner in outer or _line_subset(inner, outer)


def part_relation(repo_text: str, cache_text: str) -> str:
    """Containment relation between the two sides of ONE part. PURE.

    This is the safety gate: a cache-ahead part that is NOT a cache-side superset
    means the platform edit DROPPED content (the 850->203 char description
    truncation), and a byte-exact pull would destroy it.
    """
    if repo_text == cache_text:
        return IDENTICAL
    repo_has_cache = _contains(repo_text, cache_text)
    cache_has_repo = _contains(cache_text, repo_text)
    if repo_has_cache and not cache_has_repo:
        return REPO_SUPERSET
    if cache_has_repo and not repo_has_cache:
        return CACHE_SUPERSET
    return DISJOINT


def combine_verdict(parts: dict) -> str:
    """Whole-skill verdict from per-part {relation, direction}. PURE.

    Asymmetry is deliberate. REPO-AHEAD is PROVEN by git ancestry (the cache content
    is an older point on HEAD's own history), and the remedy - a reimport from the
    authoritative store - is safe even when the repo rewrote rather than extended the
    text. CACHE-AHEAD is INFERRED FROM ABSENCE (the cache content matches no commit),
    and its remedy overwrites the authoritative store with unreviewed platform-side
    content; that one only ships when every differing part is a clean cache-side
    superset. Anything else - mixed directions, DIVERGENT, UNKNOWN, or a cache-ahead
    part that dropped content - is MANUAL-MERGE.
    """
    rels = {p: info['relation'] for p, info in parts.items()}
    dirs = {p: info['direction'] for p, info in parts.items()}
    differing = [p for p, rel in rels.items() if rel != IDENTICAL]
    if not differing:
        return IN_SYNC

    ds = {dirs[p] for p in differing}
    if ds & {DIVERGENT, UNKNOWN}:
        return MANUAL_MERGE
    if REPO_AHEAD in ds and CACHE_AHEAD in ds:
        return MANUAL_MERGE
    if ds == {REPO_AHEAD}:
        return REPO_NEWER
    if ds == {CACHE_AHEAD}:
        if all(rels[p] in (IDENTICAL, CACHE_SUPERSET) for p in parts):
            return CACHE_NEWER
        return MANUAL_MERGE
    return MANUAL_MERGE


# ---------------------------------------------------------------------------
# git-ancestry direction, per PART
# ---------------------------------------------------------------------------

def _part_history_hashes(repo_root: Path, relpath: str):
    """({part: ancestor_hashes}, {part: all_history_hashes}) for relpath.

    pending_reimport._file_history_hashes hashes WHOLE files; a per-part verdict
    needs each historical revision split the same way the working copy is, so a
    frontmatter that matches an old commit while the body does not is classified
    per part instead of collapsing to one whole-file answer.

    (None, None) when git is unavailable or the file is untracked -> UNKNOWN, which
    combine_verdict refuses to turn into a pull.
    """
    head = _git_text(repo_root, 'rev-list', 'HEAD', '--', relpath)
    if head is None:
        return None, None

    def _hashes(rev_text):
        out = {p: set() for p in PARTS}
        for rev in rev_text.split():
            data = _git_blob_bytes(repo_root, rev, relpath)
            if data is None:
                continue
            fm, body = split_skill_md(normalized_text(data))
            for part, text in (('frontmatter', fm), ('body', body)):
                out[part].add(hashlib.sha256(text.encode('utf-8')).hexdigest())
        return out

    all_text = _git_text(repo_root, 'rev-list', '--all', '--', relpath) or ''
    return _hashes(head), _hashes(all_text)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def skill_md_report(repo_root: Path, cache_root: Path, skill: str, read_at: str) -> dict:
    repo_file = repo_root / skill / 'SKILL.md'
    cache_file = cache_root / skill / 'SKILL.md'

    if not (cache_root / skill).is_dir():
        return {'skill': skill, 'verdict': NOT_INSTALLED, 'remedy': REMEDY[NOT_INSTALLED],
                'parts': {}, 'findings': [], 'stability': STABLE,
                'point_in_time': {'read_at': read_at}}
    if not cache_file.is_file():
        return {'skill': skill, 'verdict': NOT_INSTALLED,
                'remedy': 'cache dir exists but holds no SKILL.md - reinstall via '
                          'package-and-stage-skill (see also step 2d)',
                'parts': {}, 'findings': [], 'stability': STABLE,
                'point_in_time': {'read_at': read_at}}

    repo_raw, cache_raw = repo_file.read_bytes(), cache_file.read_bytes()
    repo_text, cache_text = normalized_text(repo_raw), normalized_text(cache_raw)
    repo_split = dict(zip(PARTS, split_skill_md(repo_text)))
    cache_split = dict(zip(PARTS, split_skill_md(cache_text)))

    ancestors, all_hist = _part_history_hashes(repo_root, f'{skill}/SKILL.md')

    parts, findings = {}, []
    for part in PARTS:
        rel = part_relation(repo_split[part], cache_split[part])
        if rel == IDENTICAL:
            direction = IN_SYNC_DIR
        else:
            direction = classify_shared_copy(
                _text_hash(cache_split[part]),
                _text_hash(repo_split[part]),
                ancestors[part] if ancestors else None,
                all_hist[part] if all_hist else None,
            )
        parts[part] = {'relation': rel, 'direction': direction,
                       'repo_sha256': _text_hash(repo_split[part]),
                       'cache_sha256': _text_hash(cache_split[part])}
        if rel != IDENTICAL:
            findings.append({'kind': PART_DRIFT, 'part': part,
                             'relation': rel, 'direction': direction})

    repo_desc = description_of(repo_split['frontmatter']) or ''
    cache_desc = description_of(cache_split['frontmatter']) or ''
    if repo_desc != cache_desc and len(cache_desc) < len(repo_desc):
        # The routing surface shrank platform-side. This is what a byte-exact pull
        # would have destroyed on parcel-data-recovery (850 -> 203 chars).
        findings.append({
            'kind': DESCRIPTION_REGRESSION, 'part': 'frontmatter',
            'repo_chars': len(repo_desc), 'cache_chars': len(cache_desc),
            'cache_is_substring_of_repo': cache_desc in repo_desc,
            'note': 'cache description is SHORTER than the repo description - the '
                    'skill\'s routing surface. Never overwrite the repo description '
                    'with it; merge, keeping every trigger phrase.',
        })

    verdict = combine_verdict(parts)
    return {
        'skill': skill,
        'verdict': verdict,
        'remedy': REMEDY[verdict],
        'parts': parts,
        'findings': findings,
        'stability': STABLE,
        # Everything below is POINT-IN-TIME and rots fast. Quarantined here so no
        # consumer can mistake it for the verdict's evidence.
        'point_in_time': {
            'read_at': read_at,
            'repo_version_token': version_token_of(repo_split['frontmatter']),
            'cache_version_token': version_token_of(cache_split['frontmatter']),
            'repo_bytes': len(repo_raw),
            'cache_bytes': len(cache_raw),
            'repo_desc_chars': len(repo_desc),
            'cache_desc_chars': len(cache_desc),
        },
        '_cache_hash_at_read': norm_hash(cache_raw),
    }


def report(repo_root: Path = REPO, cache_root: Path = CACHE_ROOT,
           skills=None, _after_read=None) -> dict:
    """Full drift report. Never fabricates: an unreachable cache root yields no
    findings rather than flagging every skill as drifted.

    _after_read is a test seam for the stability re-check (simulates the cache
    moving mid-run, which it demonstrably does).
    """
    read_at = _now()
    out = {'read_at': read_at, 'repo_root': str(repo_root), 'cache_root': str(cache_root),
           'cache_root_unreadable': not cache_root.is_dir(), 'skills': {}}
    if out['cache_root_unreadable']:
        return out

    names = skills if skills is not None else all_skill_dirs(repo_root)
    for skill in names:
        if skill in SKIP or not (repo_root / skill / 'SKILL.md').is_file():
            continue
        out['skills'][skill] = skill_md_report(repo_root, cache_root, skill, read_at)

    if _after_read is not None:
        _after_read()

    # Re-hash every cache SKILL.md we read. The cache is live - it advanced under a
    # single session between two verification passes on 2026-08-03 - so a verdict
    # computed from a file that moved mid-run must say so rather than be reported flat.
    for skill, rec in out['skills'].items():
        before = rec.pop('_cache_hash_at_read', None)
        cache_file = cache_root / skill / 'SKILL.md'
        if before is None:
            continue
        after = norm_hash(cache_file.read_bytes()) if cache_file.is_file() else None
        rec['stability'] = STABLE if after == before else CHANGED_DURING_RUN
    out['verified_at'] = _now()
    return out


ACTIONABLE = (REPO_NEWER, CACHE_NEWER, MANUAL_MERGE)


def render_text(rep: dict) -> str:
    lines = [f"skill-drift-report read_at={rep['read_at']} "
             f"verified_at={rep.get('verified_at', '-')}"]
    if rep['cache_root_unreadable']:
        lines.append(f"  CACHE ROOT UNREADABLE: {rep['cache_root']} - no findings "
                     f"(store unreadable is reported, never inferred as clean)")
        return '\n'.join(lines)

    counts = Counter(r['verdict'] for r in rep['skills'].values())
    lines.append('  ' + ', '.join(f'{v} {k}' for k, v in sorted(counts.items())))
    for skill, r in sorted(rep['skills'].items()):
        if r['verdict'] not in ACTIONABLE and r['stability'] == STABLE:
            continue
        lines.append(f"\n{skill}: {r['verdict']}")
        for part, info in r['parts'].items():
            if info['relation'] != IDENTICAL:
                lines.append(f"  - {part}: {info['relation']} / {info['direction']}")
        for f in r['findings']:
            if f['kind'] == DESCRIPTION_REGRESSION:
                lines.append(
                    f"  - DESCRIPTION-REGRESSION: cache {f['cache_chars']} chars vs "
                    f"repo {f['repo_chars']} chars - routing surface would be LOST by "
                    f"a byte-exact pull")
        if r['stability'] == CHANGED_DURING_RUN:
            lines.append('  - CHANGED-DURING-RUN: the cache SKILL.md moved while this '
                         'report ran; re-run before acting')
        pit = r['point_in_time']
        lines.append(
            f"  point-in-time @{pit['read_at']} (NOT authoritative - the cache is a "
            f"live, moving target): repo {pit.get('repo_version_token')} / "
            f"{pit.get('repo_bytes')} B, cache {pit.get('cache_version_token')} / "
            f"{pit.get('cache_bytes')} B")
        lines.append(f"  action: {r['remedy']}")
    return '\n'.join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('skills', nargs='*', help='skill names (default: all)')
    ap.add_argument('--json', action='store_true', help='emit the full report as JSON')
    args = ap.parse_args()
    rep = report(skills=args.skills or None)
    print(json.dumps(rep, indent=2) if args.json else render_text(rep))


if __name__ == '__main__':
    main()
