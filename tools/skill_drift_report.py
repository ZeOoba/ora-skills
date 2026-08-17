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
from package_skills import MAX_DESC, REPO, SKIP  # noqa: E402
from pending_reimport import (  # noqa: E402
    CACHE_ROOT, _git_blob_bytes, _git_text, _isdir_long, _isfile_long,
    _read_bytes_long, all_skill_dirs, classify_shared_copy,
)
from skill_md_normalize import (  # noqa: E402
    _normalize_frontmatter, _unquote, split_skill_md,
)

# --- verdicts -------------------------------------------------------------
IN_SYNC = 'IN-SYNC'
REPO_NEWER = 'REPO-NEWER'
CACHE_NEWER = 'CACHE-NEWER'
MANUAL_MERGE = 'MANUAL-MERGE'
NOT_INSTALLED = 'NOT-INSTALLED'
BROKEN_INSTALL = 'BROKEN-INSTALL'
CACHE_ONLY = 'CACHE-ONLY'
UNREADABLE = 'UNREADABLE'

# --- text relations (containment, not direction) --------------------------
IDENTICAL = 'IDENTICAL'
REPO_SUPERSET = 'REPO-SUPERSET'
CACHE_SUPERSET = 'CACHE-SUPERSET'
DISJOINT = 'DISJOINT'
WHITESPACE_ONLY = 'WHITESPACE-ONLY'

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

# Anthropic stock skills ship with the platform and legitimately have no repo
# source, so they are NOT cache-only findings. Same roster the drift-check
# SKILL.md step 3 carries; kept in sync with it by hand (it is doctrine, not code).
STOCK_SKILLS = frozenset({
    'docx', 'xlsx', 'pptx', 'pdf', 'mcp-builder', 'skill-creator',
    'schedule', 'setup-cowork', 'consolidate-memory',
    # 'morning' added 2026-08-03 when the new CACHE-ONLY verdict first surfaced it.
    # It is platform stock, not ORA paper: zero Oxford/ORA mentions (vs 13 in
    # lease-form-qc), first-person personal-productivity voice, and it ships its own
    # Fraunces font assets. Capturing it into this repo would manufacture a bogus
    # "authoritative source" for a skill ORA does not own, which would then read as
    # drift on every platform update forever.
    'morning',
    # 'explain-usage' added 2026-08-17 (drift-check remediation pass, item 6) after
    # confirming CACHE-ONLY on a live run. Same class as 'morning': zero Oxford/ORA
    # mentions, first-person personal-productivity voice ("Explain where this
    # session's tokens went"), platform-shipped token-usage explainer with no ORA
    # doctrine or branding. Same rationale applies -- capturing it would manufacture
    # a bogus authoritative source for a skill ORA does not own.
    'explain-usage',
})

REMEDY = {
    IN_SYNC: 'none',
    REPO_NEWER: (
        're-upload to Cowork/claude.ai needed - stage it with the package-and-stage-skill '
        'skill (runs tools/package_skills.py and surfaces a one-click Save-skill '
        'installer; registration stays a human click)'
    ),
    CACHE_NEWER: (
        'REPO-FIRST VIOLATION - pull cache into repo. Every differing part is a clean '
        'cache-side superset: no non-blank line is lost and existing line ORDER is '
        'preserved, so the byte-exact copy in the CACHE->REPO RECOVERY PROCEDURE is '
        'safe for content. NOT verified: blank-line/whitespace structure - diff the '
        'file before committing. Still content-verify and open a PR, never commit to main'
    ),
    MANUAL_MERGE: (
        'MANUAL MERGE required - neither side is a superset, so NO byte-exact copy in '
        'either direction. Reconcile frontmatter and body independently in a supervised '
        f'session (merged description must stay <= {MAX_DESC} chars), then PR'
    ),
    NOT_INSTALLED: 'none - no cache directory; never installed (this is not drift)',
    BROKEN_INSTALL: (
        'BROKEN INSTALL - the cache directory exists but holds no SKILL.md, so the '
        'skill is half-installed, not un-installed. Reinstall via package-and-stage-skill '
        'and install the staged .skill with the Cowork Save-skill button'
    ),
    CACHE_ONLY: (
        'CACHE-ONLY - installed platform-side with NO authoritative repo source. '
        'Capture it into the repo (REPO-FIRST RULE) or retire it; until then its text '
        'enters session context with nothing to review it against'
    ),
    UNREADABLE: (
        'UNREADABLE - a store file could not be read this run (lock, permissions). '
        'No verdict was computed; re-run. This is a reporting gap, never a clean result'
    ),
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
    text = data.rstrip(b'\x00').decode('utf-8', errors='replace').replace('\r\n', '\n')
    # A UTF-8 BOM defeats the '---' fence test in split_skill_md, which would dump
    # the whole file into `body` and manufacture a spurious DESCRIPTION-REGRESSION.
    return text.lstrip('﻿')


def _read_bytes(path: Path) -> bytes:
    """Single funnel for every store read, so one locked file is contained to a
    single UNREADABLE finding instead of raising out of the whole run (on Windows
    the Claude app can hold a cache file open). Also the test seam for that path.

    Long-path-safe (pending_reimport._read_bytes_long) -- a deep cache path past
    MAX_PATH must raise the same as a genuinely locked/missing file, not silently
    misbehave, since callers here already handle OSError."""
    return _read_bytes_long(path)


def norm_hash(data: bytes) -> str:
    """sha256 of the EOL-normalized bytes - the documented verdict formula.

    Equivalent to pending_reimport._normalized_hash_bytes for text; kept local so
    the NUL-padding strip is inside the hashed form too.
    """
    return hashlib.sha256(normalized_text(data).encode('utf-8')).hexdigest()


def _split_parts(text: str) -> dict:
    """The ONE place a SKILL.md becomes comparable parts. Used for both working-tree
    files and historical git blobs so ancestry hashes live in the same space."""
    fm, body = split_skill_md(text)
    return {'frontmatter': _normalize_frontmatter(fm), 'body': body}


def description_of(frontmatter: str) -> str | None:
    """The skill's routing surface, as a plain string.

    Handles the three shapes that actually occur on disk (2026-08-03 sweep of all
    55 skills), because a parser that understands only one of them silently
    disables the DESCRIPTION-REGRESSION detector on the rest:

      description: plain text
      description: "quoted text"     -> quotes stripped, so the count is the
                                        DESCRIPTION's length, not the YAML
                                        literal's (parcel-data-recovery reads 850,
                                        matching the incident record, not 852)
      description: >                 -> folded block scalar, joined with spaces;
        continuation lines...           `|` joins with newlines.

    ratify-hurdle-rate uses the block form (as did census-acs-extract and
    oxford-cc-strategic-audit, both retired 2026-08-05), and the original
    `^description:\\s*(.*)$` regex returned literally '>' for each — so
    len(cache_desc) < len(repo_desc) could never fire and the regression detector
    was dead on those. ratify-hurdle-rate is now the live block-form fixture that
    tools/test_skill_drift_report_realdata.py pins to. Only a TOP-LEVEL
    `description:` matches; a nested one under `metadata:` is indented and skipped.
    """
    lines = frontmatter.split('\n')
    for i, ln in enumerate(lines):
        if not ln.startswith('description:'):
            continue
        head = ln[len('description:'):].strip()
        if re.fullmatch(r'[>|][+-]?\d*', head):  # block scalar + optional indicators
            collected = []
            for cont in lines[i + 1:]:
                if not cont.strip():
                    collected.append('')
                    continue
                if not cont[:1].isspace():
                    break  # dedented to a sibling key: the block is over
                collected.append(cont.strip())
            return ('\n' if head.startswith('|') else ' ').join(collected).strip()
        return _unquote(head)
    return None


def version_token_of(text: str) -> str | None:
    """First vX.Y marker. REPORTED ONLY - never an input to the verdict. This is
    exactly the signal the broken check mistook for evidence."""
    m = _VERSION_RE.search(text)
    return f'v{m.group(1)}' if m else None


def _line_subset(inner: str, outer: str) -> bool:
    """True if `inner`'s non-blank lines appear in `outer` IN THE SAME ORDER.

    ORDER MATTERS (fixed 2026-08-03, found by the real-data reorder tests). The
    first cut used a Counter, which is order-blind: a cache that reordered the
    document AND appended a section read as a clean cache-side superset, so
    combine_verdict returned CACHE-NEWER and prescribed the byte-exact pull —
    which would then have silently imposed the platform's section ordering on the
    authoritative repo copy. A subsequence test makes "superset" mean what the
    remedy assumes: everything the other side had is still there, still in order,
    with new material only inserted between existing lines.

    Blank lines are still ignored, so trivial whitespace churn does not manufacture
    a MANUAL-MERGE. That is a deliberate, disclosed limit: a byte-exact pull can
    therefore still alter blank-line structure, which is why the CACHE-NEWER remedy
    says ordering and content are verified but whitespace structure is not.
    """
    outer_iter = iter([ln for ln in outer.splitlines() if ln.strip()])
    return all(line in outer_iter
               for line in (ln for ln in inner.splitlines() if ln.strip()))


def _contains(outer: str, inner: str) -> bool:
    return inner in outer or _line_subset(inner, outer)


def _ws_key(text: str) -> str:
    """Content with blank lines dropped and trailing whitespace stripped. Two texts
    with the same key differ only in whitespace LAYOUT - every non-blank line, and
    its order, is identical."""
    return '\n'.join(ln.rstrip() for ln in text.splitlines() if ln.strip())


def part_relation(repo_text: str, cache_text: str) -> str:
    """Containment relation between the two sides of ONE part. PURE.

    This is the safety gate: a cache-ahead part that is NOT a cache-side superset
    means the platform edit DROPPED content (the 850->203 char description
    truncation), and a byte-exact pull would destroy it.
    """
    if repo_text == cache_text:
        return IDENTICAL
    if _ws_key(repo_text) == _ws_key(cache_text):
        # A trailing-newline or blank-line-only delta is not stale skill text. Left
        # to the containment tests it lands in DISJOINT -> MANUAL-MERGE, i.e. a
        # supervised-merge ticket for a zero-content difference: the same nuisance
        # class as the CRLF flags this tool exists to kill.
        return WHITESPACE_ONLY
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
    agreed = (IDENTICAL, WHITESPACE_ONLY)
    differing = [p for p, rel in rels.items() if rel not in agreed]
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
        if all(rels[p] in (IDENTICAL, WHITESPACE_ONLY, CACHE_SUPERSET) for p in parts):
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

    Returns (None, None) -> direction UNKNOWN -> combine_verdict refuses to turn it
    into a pull, whenever we CANNOT LOOK rather than looked-and-found-nothing:

      * git unavailable / not a repo             (rev-list errors)
      * the path has NO history                  (rev-list exits 0, EMPTY stdout)
      * the repository is SHALLOW                (history deliberately truncated)

    The middle two are the code-review finding of 2026-08-03. CACHE-AHEAD is
    inferred from ABSENCE - "this content matches no commit anywhere" - and its
    remedy overwrites the authoritative store. That inference is only sound if the
    search was capable of finding a match. An untracked path and a shallow clone
    both return an empty-or-truncated ancestry, which the first cut accepted as
    proof; an untracked SKILL.md therefore reported CACHE-NEWER, and in a shallow
    clone a section the repo had deliberately DELETED read as cache-side-new, so
    the prescribed byte-exact pull would have re-introduced it.

    KNOWN RESIDUAL: if the cache content was committed only on a branch that is
    later deleted or gc'd, ancestry genuinely no longer contains it and the verdict
    decays DIVERGENT -> CACHE-AHEAD. That is not detectable from here - git has
    forgotten. The MANUAL-MERGE superset gate remains the backstop.
    """
    head = _git_text(repo_root, 'rev-list', 'HEAD', '--', relpath)
    if head is None or not head.strip():
        return None, None
    if (_git_text(repo_root, 'rev-parse', '--is-shallow-repository') or '').strip() == 'true':
        return None, None

    head_revs = head.split()
    all_revs = (_git_text(repo_root, 'rev-list', '--all', '--', relpath) or '').split()

    # Hash each UNIQUE revision once. HEAD's list is a subset of --all's, so the
    # first cut ran `git show` twice per shared revision and threw one result away.
    by_rev = {}
    for rev in set(head_revs) | set(all_revs):
        data = _git_blob_bytes(repo_root, rev, relpath)
        if data is None:
            continue
        parts = _split_parts(normalized_text(data))
        by_rev[rev] = {p: _text_hash(parts[p]) for p in PARTS}

    def _collect(revs):
        out = {p: set() for p in PARTS}
        for rev in revs:
            h = by_rev.get(rev)
            if h:
                for part in PARTS:
                    out[part].add(h[part])
        return out

    return _collect(head_revs), _collect(all_revs)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _terminal(skill, verdict, read_at, remedy=None):
    return {'skill': skill, 'verdict': verdict, 'remedy': remedy or REMEDY[verdict],
            'parts': {}, 'findings': [], 'stability': STABLE,
            'point_in_time': {'read_at': read_at}}


def skill_md_report(repo_root: Path, cache_root: Path, skill: str, read_at=None) -> dict:
    """One skill's verdict. `read_at` is stamped when THIS skill's files are read,
    not when the run began - a full run takes tens of seconds against a live cache,
    so a single run-start stamp would misdate every figure after the first."""
    read_at = read_at or _now()
    repo_file = repo_root / skill / 'SKILL.md'
    cache_file = cache_root / skill / 'SKILL.md'

    if not (repo_root / skill / 'SKILL.md').is_file():
        # Installed with no authoritative source, or the repo dir was deleted while
        # the skill stayed installed. Either way its text still enters session
        # context with nothing to review it against.
        return _terminal(skill, CACHE_ONLY, read_at)
    if not _isdir_long(cache_root / skill):
        return _terminal(skill, NOT_INSTALLED, read_at)
    if not _isfile_long(cache_file):
        # HALF-installed, not un-installed - a distinct, actionable state that the
        # NOT-INSTALLED label used to hide from the rendered report entirely.
        return _terminal(skill, BROKEN_INSTALL, read_at)

    try:
        repo_raw, cache_raw = _read_bytes(repo_file), _read_bytes(cache_file)
    except OSError as exc:
        return _terminal(skill, UNREADABLE, read_at,
                         f'{REMEDY[UNREADABLE]} ({type(exc).__name__}: {exc})')

    repo_text, cache_text = normalized_text(repo_raw), normalized_text(cache_raw)
    repo_split = _split_parts(repo_text)
    cache_split = _split_parts(cache_text)
    # Descriptions are read from the RAW frontmatter, never the normalized view.
    # _normalize_frontmatter is COMPARE-ONLY: unquoting a scalar discards the
    # leading/trailing whitespace that YAML quotes exist to protect, which would
    # silently shave characters off a REPORTED description length (caught by the
    # replayed parcel-data-recovery fixture: 203 -> 202).
    repo_fm_raw, _ = split_skill_md(repo_text)
    cache_fm_raw, _ = split_skill_md(cache_text)

    # Walk git history ONLY if something actually differs. Direction is irrelevant
    # to an agreeing part, and the walk spawns a subprocess per revision - on a
    # clean run that was the entire cost of the report.
    agreed = (IDENTICAL, WHITESPACE_ONLY)
    relations = {p: part_relation(repo_split[p], cache_split[p]) for p in PARTS}
    if all(rel in agreed for rel in relations.values()):
        ancestors = all_hist = None
    else:
        ancestors, all_hist = _part_history_hashes(repo_root, f'{skill}/SKILL.md')

    parts, findings = {}, []
    for part in PARTS:
        rel = relations[part]
        if rel in agreed:
            direction = IN_SYNC_DIR
        else:
            # Belt-and-braces companion to the guards in _part_history_hashes: an
            # EMPTY per-part ancestor set means every blob read failed, which is
            # again "could not look", not "searched and found nothing". Passing it
            # through as a real (empty) set would let classify_shared_copy skip its
            # UNKNOWN branch and return CACHE-AHEAD on no evidence at all.
            direction = classify_shared_copy(
                _text_hash(cache_split[part]),
                _text_hash(repo_split[part]),
                ancestors[part] if ancestors and ancestors[part] else None,
                all_hist[part] if all_hist and all_hist[part] else None,
            )
        parts[part] = {'relation': rel, 'direction': direction,
                       'repo_sha256': _text_hash(repo_split[part]),
                       'cache_sha256': _text_hash(cache_split[part])}
        if rel not in agreed:
            findings.append({'kind': PART_DRIFT, 'part': part,
                             'relation': rel, 'direction': direction})

    repo_desc = description_of(repo_fm_raw) or ''
    cache_desc = description_of(cache_fm_raw) or ''
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
            'repo_version_token': version_token_of(repo_text),
            'cache_version_token': version_token_of(cache_text),
            'repo_bytes': len(repo_raw),
            'cache_bytes': len(cache_raw),
            'repo_desc_chars': len(repo_desc),
            'cache_desc_chars': len(cache_desc),
        },
    }


def _cache_skill_dirs(cache_root: Path) -> set:
    try:
        return {d.name for d in cache_root.iterdir() if d.is_dir()}
    except OSError:
        return set()


def report(repo_root: Path = REPO, cache_root: Path = CACHE_ROOT,
           skills=None, _after_read=None) -> dict:
    """Full drift report. Never fabricates: an unreachable cache root yields no
    findings rather than flagging every skill as drifted.

    Enumeration is the UNION of both stores, not just the repo working tree. A
    repo-only enumeration silently dropped every cache-only skill - installed
    platform-side with no authoritative source, which is the direction that most
    warrants review - plus any skill deleted from the repo while still installed.

    _after_read is a test seam for the stability re-check (simulates the cache
    moving mid-run, which it demonstrably does).
    """
    out = {'read_at': _now(), 'repo_root': str(repo_root), 'cache_root': str(cache_root),
           'cache_root_unreadable': not cache_root.is_dir(),
           'unknown_skills': [], 'skills': {}}
    if out['cache_root_unreadable']:
        return out

    repo_skills = {s for s in all_skill_dirs(repo_root) if s not in SKIP}
    cache_skills = _cache_skill_dirs(cache_root)
    if skills is not None:
        # An unknown name used to yield an empty, reassuring report - the worst
        # possible answer to "is this one skill in sync?".
        out['unknown_skills'] = sorted(s for s in skills
                                       if s not in repo_skills | cache_skills)
        names = [s for s in skills if s not in out['unknown_skills']]
    else:
        names = sorted(repo_skills | (cache_skills - STOCK_SKILLS))

    baseline = {}
    for skill in names:
        out['skills'][skill] = skill_md_report(repo_root, cache_root, skill)
        cache_file = cache_root / skill / 'SKILL.md'
        if _isfile_long(cache_file):
            try:
                baseline[skill] = norm_hash(_read_bytes(cache_file))
            except OSError:
                pass

    if _after_read is not None:
        _after_read()

    # Re-hash every cache SKILL.md we read. The cache is live - it advanced under a
    # single session between two verification passes on 2026-08-03 - so a verdict
    # computed from a file that moved mid-run must say so rather than be reported flat.
    for skill, before in baseline.items():
        cache_file = cache_root / skill / 'SKILL.md'
        try:
            after = norm_hash(_read_bytes(cache_file)) if _isfile_long(cache_file) else None
        except OSError:
            after = None
        if after != before:
            out['skills'][skill]['stability'] = CHANGED_DURING_RUN
    out['verified_at'] = _now()
    return out


ACTIONABLE = (REPO_NEWER, CACHE_NEWER, MANUAL_MERGE,
              BROKEN_INSTALL, CACHE_ONLY, UNREADABLE)


def render_text(rep: dict) -> str:
    lines = [f"skill-drift-report read_at={rep['read_at']} "
             f"verified_at={rep.get('verified_at', '-')}"]
    if rep['cache_root_unreadable']:
        lines.append(f"  CACHE ROOT UNREADABLE: {rep['cache_root']} - no findings "
                     f"(store unreadable is reported, never inferred as clean)")
        return '\n'.join(lines)

    counts = Counter(r['verdict'] for r in rep['skills'].values())
    lines.append('  ' + ', '.join(f'{v} {k}' for k, v in sorted(counts.items())))
    if rep.get('unknown_skills'):
        lines.append(f"  UNKNOWN SKILL(S) - not in either store, nothing was checked: "
                     f"{', '.join(rep['unknown_skills'])}")
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


INSTALLED_VERDICTS = {IN_SYNC, REPO_NEWER, CACHE_NEWER, MANUAL_MERGE, CACHE_ONLY, UNREADABLE}


def render_publish_status(rep: dict) -> str:
    """One line per named skill, citation-ready for a Rev-log/advisory entry: whether
    the skill is CURRENTLY installed in the runtime cache, sourced from a live read of
    CACHE_ROOT at read_at — never from memory or a prior Rev-log's own claim.

    Added 2026-08-15 (Rev 10 remediation): a Rev 5 log had recorded capex-budgeting as
    Gabriel-confirmed UNPUBLISHED as of 2026-08-09, while the Code catalog separately
    carried a 2026-08-12 update — nothing re-checked live state between the two records,
    so they silently diverged with no way to tell which was current short of a manual
    ListSkills/cache walk. This mode exists so any future Rev-log entry making a
    publish/unpublished claim can cite a fresh, timestamped run of this flag instead of
    carrying a prior claim forward unverified.

    NOTE: this reads the LOCAL Windows runtime-cache mirror (CACHE_ROOT) — the same
    store install/uninstall drives — not the account's live claude.ai/Cowork ListSkills
    API directly. The two are expected to agree (the cache IS how a Save-skill install
    reaches this machine) but a Cowork-side ListSkills call remains the independent
    cross-check if the two were ever suspected to disagree.
    """
    if rep['cache_root_unreadable']:
        return (f"CACHE ROOT UNREADABLE: {rep['cache_root']} — no publish-status could "
                 f"be read; do not report a publish/unpublished claim from this run")
    lines = []
    for skill, r in sorted(rep['skills'].items()):
        pit = r['point_in_time']
        if r['verdict'] == NOT_INSTALLED:
            status = 'NOT INSTALLED'
        elif r['verdict'] == BROKEN_INSTALL:
            status = 'BROKEN INSTALL — cache dir exists, no SKILL.md'
        else:
            status = 'INSTALLED'
        lines.append(
            f"{skill}: {status} (verdict={r['verdict']}, "
            f"cache_version={pit.get('cache_version_token', '-')}, "
            f"checked_at={pit['read_at']})"
        )
    if rep.get('unknown_skills'):
        lines.append(
            f"UNKNOWN (name matched neither store, nothing was read): "
            f"{', '.join(rep['unknown_skills'])}"
        )
    return '\n'.join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('skills', nargs='*', help='skill names (default: all)')
    ap.add_argument('--json', action='store_true', help='emit the full report as JSON')
    ap.add_argument(
        '--publish-status', action='store_true',
        help='print one citation-ready INSTALLED/NOT-INSTALLED line per named skill, '
             'sourced live from the runtime cache — run this before recording any '
             'publish/unpublished claim in a Rev-log rather than carrying one forward '
             '(added 2026-08-15, Rev 10 remediation)',
    )
    args = ap.parse_args()
    rep = report(skills=args.skills or None)
    if args.publish_status:
        print(render_publish_status(rep))
    elif args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(render_text(rep))
    # Exit non-zero when nothing could be checked, so a typo'd skill name or an
    # unreachable cache can never be mistaken for a clean result by a caller that
    # only reads the exit code.
    if rep['cache_root_unreadable'] or rep['unknown_skills']:
        sys.exit(2)


if __name__ == '__main__':
    main()
