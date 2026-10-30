#!/usr/bin/env python3
"""skill_md_normalize.py - shared SKILL.md text-normalization primitives.

WHY THIS EXISTS (2026-08-03): skill_drift_report.py's _normalize_frontmatter
(PR #35, commit 3d15526, "YAML scalar quoting is serialization, not drift")
strips top-level YAML scalar quoting before comparing frontmatter, because the
Cowork platform re-serializes SKILL.md frontmatter on install and its quoting
style varies over time. pending_reimport.py has its OWN separate comparator
(_normalized_hash/_normalized_hash_bytes, feeding skill_drifted() ->
sweep_drift() -> candidates()) and was NOT updated alongside PR #35: a
confirmed-correct Save-skill install of masterlease-jurisdiction-rebase that
differs from the repo only in that same quoting-class delta (plus a trailing
blank line) still reported as a live-sweep candidate.

split_skill_md/_normalize_frontmatter/_unquote are PR #35's logic, extracted
verbatim (not reimplemented) so skill_drift_report.py and pending_reimport.py
can never disagree about what "same frontmatter" means. skill_drift_report.py
imports them back from here instead of defining its own copy.

normalize_skill_md_text() is new: a HASH-INPUT view (never a file
reconstruction) that applies the same quoting normalization plus a trailing
end-of-file blank-line collapse, for pending_reimport's single-hash-per-file
comparator. It is a no-op for any text that doesn't open with a '---'
frontmatter fence, so it only ever touches SKILL.md-shaped content -- a
bundled script, fixture, or shared repo-root JSON dependency passes through
byte-for-byte.
"""
import re

_TOP_KEY_RE = re.compile(r'^([A-Za-z0-9_-]+):[ \t]*(.*)$')


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


def _unquote(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in '"\'':
        inner = s[1:-1]
        # A double-quoted YAML scalar escapes its inner quotes and backslashes; the
        # plain/block form of the same value does not. Unescape only those two, so
        # `"say \"x\""` and `say "x"` compare equal (2026-10-30: the platform
        # stores merge-ready's description double-quoted with escaped inner quotes).
        if s[0] == '"':
            inner = (inner.replace('\\\\', '\x00').replace('\\"', '"')
                     .replace('\\n', '\n').replace('\x00', '\\'))
        return inner
    return s


# FOLDED blocks only: `|` (literal) keeps line breaks that carry meaning, so it is
# never folded. Chomping (`-`/`+`) only changes trailing newlines of prose.
_FOLDED_INDICATORS = {'>', '>-', '>+'}
# Only `description` is ever flattened by the platform (2026-10-30); every other
# key keeps exact-value comparison.
_FLATTENED_KEYS = {'description'}


def _collapse_ws(s: str) -> str:
    return ' '.join(s.split())


def _normalize_frontmatter(fm: str) -> str:
    """A COMPARE-ONLY view of frontmatter with YAML scalar quoting stripped from
    top-level keys. Never used to write a file - only to decide whether two
    frontmatters mean the same thing.

    WHY: the platform re-serializes frontmatter on install and its quoting style
    VARIES over time. acquisition-underwriting's `name` was pulled from the cache
    QUOTED on 2026-07-27 (the REPO-FIRST recovery in commit 20a936e byte-copied it
    that way), and the same cache served it UNQUOTED on 2026-08-03 - producing a
    permanent MANUAL-MERGE on a delta with identical YAML meaning. Treating
    serialization as content is the same false-positive family as the CRLF flags
    this tool exists to kill.

    Deliberately narrow: no YAML parser. A top-level `key: value` line has its
    value unquoted (inside double quotes the escapes \\" \\\\ and \\n are decoded).
    For `description` only, a folded (`>`) block is joined onto its key line and
    internal whitespace is collapsed (2026-10-30); `|` blocks are never folded.
    Both sides get the identical treatment. Outside `description` this collapses
    only quoting and escape differences; for `description` it also collapses
    whitespace, line wrapping and folded-block chomping (see the comment in the
    loop below). A changed word never compares equal.
    """
    # Folded description (2026-10-30): the platform FLATTENS a `description: >`
    # block into one double-quoted line on install (county-parcel-screen read
    # DIVERGENT for exactly this). For the `description` key ONLY, a folded block
    # is joined onto its key line and internal whitespace is collapsed, on BOTH
    # sides. Accepted cost: for that one key, a change that is purely whitespace,
    # line breaks or chomping compares equal. Any changed word still differs, and
    # literal `|` blocks and every other key are compared exactly as before.
    out = []
    lines = fm.split('\n')
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = _TOP_KEY_RE.match(ln)
        if m and m.group(1) in _FLATTENED_KEYS and m.group(2).strip() in _FOLDED_INDICATORS:
            body = []
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i][:1] in ' \t'):
                body.append(lines[i])
                i += 1
            out.append(f'{m.group(1)}: {_collapse_ws(" ".join(body))}')
            continue
        if m and m.group(2).strip():
            val = _unquote(m.group(2).strip())
            out.append(f'{m.group(1)}: {_collapse_ws(val) if m.group(1) in _FLATTENED_KEYS else val}')
        else:
            out.append(ln)
        i += 1
    return '\n'.join(out).rstrip('\n')


def _collapse_trailing_blank_lines(text: str) -> str:
    """Collapse a run of trailing newlines to exactly one.

    A Save-skill install round-trip can add or drop a single blank line at
    end-of-file (confirmed live 2026-08-03: masterlease-jurisdiction-rebase
    installed byte-identical to the repo except for this plus frontmatter
    quoting) -- that is EOF whitespace, not content. Only the TRAILING run is
    touched: a file with no final newline at all is untouched, and no interior
    blank line (including any between the frontmatter fence and the body) is
    ever removed.
    """
    return re.sub(r'\n+\Z', '\n', text) if text.endswith('\n') else text


def normalize_skill_md_text(text: str) -> str:
    """A SKILL.md HASH INPUT with frontmatter-quoting and a trailing EOF blank
    line normalized away. NEVER a valid file reconstruction -- the join point
    between the normalized frontmatter and body does not attempt to reproduce
    the original fence-to-body spacing, which split_skill_md already discards
    on both sides of every comparison in this codebase. Only for feeding a
    hash function.

    No-op for text that doesn't open with a '---' frontmatter fence (including
    text that opens with '---\\n' but has no closing fence, i.e. not real
    frontmatter) -- unchanged text hashes exactly as it did before this
    normalization existed.
    """
    if not text.startswith('---\n'):
        return text
    fm, body = split_skill_md(text)
    if not fm and body == text:
        return text  # no closing fence found; not real frontmatter
    return _normalize_frontmatter(fm) + '\n---\n' + _collapse_trailing_blank_lines(body)
