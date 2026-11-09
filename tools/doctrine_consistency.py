#!/usr/bin/env python3
"""doctrine_consistency.py - catch skill text that has drifted from its source of truth.

WHY (2026-11-05 data-flow review): facts paraphrased across skills drifted in ways no
existing probe sees. buybox-drift-probe covers price statements and governor-drift-probe
covers DSCR/LTV numbers. This covers three semantic restatements:

  cluster-count          A count of ORA's clusters or target markets that signals the whole set
                         ("all eleven", "ORA's 11", "N canonical markets", "N target-market
                         clusters") must equal len(target-markets.json clusters). "the other N
                         clusters/markets" must equal that total, minus one, minus any subset
                         count named earlier in the same line ("Tier A covers three clusters;
                         the other eight").
  target-geography       A line that presents ORA's target geography (target markets, states or
                         clusters; "ORA targets ...") and lists five or more states, at least four
                         of them established-cluster states, must name every cluster state, must
                         not list a state outside the clusters (TN is a watch market), and, if it
                         names four or more clusters by city, must name them all. Holdings
                         statements ("ORA spans/holds ...") and counted subsets ("five of ten
                         target clusters") are left alone.
  dscr-at-aggregate-ltv  DSCR tested, or debt sized, "at 40% LTV". 40% is the portfolio-aggregate
                         governor; per-property debt is sized at the lesser of 65% LTV and 1.25x
                         DSCR (acquisition-underwriting UNDERWRITING CONVENTIONS).
  dscr-floor-at-lesser-of
                         The per-property 1.25x DSCR floor stated against the lesser-of loan
                         ("DSCR <1.25x at refi sizing", "DSCR must be >=1.25x ... (LESSER of 65% LTV
                         and 1.25x DSCR)"). That loan clears 1.25x by construction, so the floor could
                         never flag. Gabriel in-turn ratification 2026-11-08: the floor is DSCR at a
                         loan sized to 65% LTV at the market refi terms; lesser-of sizing still sets
                         refi proceeds. A clause is read when it names DSCR as the tested metric (not
                         the "1.25x DSCR" sizing constraint) and mentions 1.25, a floor or
                         FLOOR-FLAGGED; the nearest basis after that DSCR (else the nearest before it)
                         decides: "lesser/lower/smaller of", "min(", "refi(nance) sizing/sized",
                         "as-sized" and "modeled refi" are wrong, any other "65% LTV" is right. A
                         "never/not/instead of/rather than" directly before the basis excuses it, and
                         so does a DSCR followed by "binds"/"binding constraint" (the ratified
                         equivalence: DSCR binding under lesser-of sizing IS the flag).
  dscr-floor-year1-noi   The 1.25x DSCR floor stated on Year-1 NOI ("DSCR = Year 1 NOI / debt service
                         ... >= 1.25x", "Year-1 DSCR must be >=1.25x"). Gabriel in-turn ruling
                         2026-11-08 (acquisition-underwriting v4.45): the floor DSCR uses STABILIZED
                         NOI, the NOI the refi is sized on; Year-1 DSCR is reported as its own coverage
                         line and is not the floor. "Year 1/Year-1/Year one/Y1/first-year/going-in"
                         before NOI, net operating income or DSCR(s) flags when a DSCR and 1.25, a
                         floor or FLOOR-FLAG sit within 300 characters of it on the same physical line
                         (the whole line, not one clause), unless a "not/never/rather than/instead
                         of" sits directly before the phrase, or "not/never the (DSCR) floor" (not
                         "... floor basis") or "separate(ly)" follows within 120 characters in the
                         same sentence (it may cross a ';', so an unrelated "...; X is not the floor"
                         later in the sentence also excuses it). Fails closed: a line that reports
                         Year-1 NOI next to an unrelated floor sentence is flagged.

History is exempt: changelog sections, version bullets and index rows, versions/ and _archive/
may quote old values.

ALLOWED holds reviewed findings: history that was right when written, or a fix waiting on a decision.
Each key is (path, check, phrase, line key) with an exact count; the line key hashes the whole
normalized line, so a new, repeated or moved phrase is still unexplained, and an entry whose line
changed or vanished fails the test suite.

LIMITS, stated plainly: these are pattern checks. They catch the phrasings above and the variants
pinned in tools/test_doctrine_consistency.py, not every possible wording. Known gaps:
  * A subset count is trusted only for arithmetic; every subset-excused "other N" is reported as
    cluster-count-subset and must be allowlisted after a human confirms the subset is current. A
    subset stated on another line ("Tier A: five clusters" twenty lines up) cannot be seen at all.
  * A holdings word inside a target clause ("ORA targets markets where it already holds scale: ...")
    reads as a holdings statement and is skipped, and a state annotated as a watch market
    ("TN (watch ...)") is not treated as a target claim.
  * Geography is checked only where 'target' sits within 160 characters before the list or 40 after.
  * The floor check reads one clause (split at '.' and ';'; "e.g./i.e./cf./vs." do not split) at a
    time, on one physical line, so a floor and its lesser-of basis stated in separate sentences, on
    hard-wrapped lines, or more than 200 characters apart, is not seen. Wordings outside the basis
    vocabulary above are not seen either, and a clause that also names a 65%-LTV loan (outside
    "lesser of 65% LTV") is trusted as stating the ratified basis.
A new phrasing that drifts needs a new pattern and a test.

Usage: python tools/doctrine_consistency.py [--repo PATH]
Exit:  0 nothing unexplained · 1 unexplained findings · 2 target-markets.json unreadable
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter, namedtuple
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKIP_TOP = {'tools', 'docs', 'plugins'}
SKIP_DIRS = {'versions', 'tests', 'fixtures', 'golden_set', '__pycache__', 'node_modules', 'runs'}
SUFFIXES = {'.md', '.js', '.py'}

# (path, check, normalized matched phrase, line_key(line)) -> (exact count, reason)
ALLOWED = {
    ('acquisition-underwriting/references/outcome-feedback-and-backtest.md', 'cluster-count',
     'all ten canonical markets', '49ebebbfbd'):
        (1, 'Omits Chicago. The fix rides the next acquisition-underwriting version, so it does '
            'not collide with the rulings recorded as "staged as v4.42" '
            '(docs/plans/2026-11-05_skill-dataflow-calibration-review.md L5, S7).'),
    ('acquisition-underwriting/references/market-and-cost-calibration-data.md', 'cluster-count',
     'other nine clusters', 'f92a6a7e48'):
        (1, 'A dated 2026-08-11 correction note; nine was right when ten clusters existed. '
            'Rewording rides the next acquisition-underwriting version, as above.'),
    ('owner-outreach/SKILL.md', 'cluster-count', "ora's 9 target clusters", 'b3c4356aa1'):
        (1, 'A dated 2026-06-22 fix narrative ("covered 4 of ORA\'s 9 target clusters"); nine was right '
            'when written. History, not a live claim.'),
}

US_STATES = set('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO '
                'MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())
STATE_NAMES = {'ohio': 'OH', 'maryland': 'MD', 'indiana': 'IN', 'wisconsin': 'WI', 'missouri': 'MO',
               'kansas': 'KS', 'michigan': 'MI', 'virginia': 'VA', 'iowa': 'IA', 'kentucky': 'KY',
               'illinois': 'IL', 'tennessee': 'TN'}
NUMBER_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
                'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
                'fourteen': 14, 'fifteen': 15}
LOOKBACK = 160   # 'target' may come this far before the first state named
LOOKAHEAD = 40   # or this close after the last one ("... TN are ORA's target states")

_NUM = r'(\d{1,2}|%s)' % '|'.join(NUMBER_WORDS)
_QUALIFIERS = r'(?:(?:canonical|ORA|target(?:[- ]market)?)\s+)*'
_FULL_SET_PATTERNS = [
    re.compile(r"\b(?:all|ORA['’]s|our|its)\s+%s\s+%s(?:markets|clusters)\b" % (_NUM, _QUALIFIERS), re.I),
    re.compile(r'\b%s\s+(?:canonical|ratified)\s+(?:target[- ]market\s+)?(?:markets|clusters)\b' % _NUM, re.I),
    re.compile(r'\b%s\s+target[- ]market\s+clusters\b' % _NUM, re.I),
    re.compile(r'\btargets?\s+%s\s+%sclusters\b' % (_NUM, _QUALIFIERS), re.I),
]
_OTHER_PATTERN = re.compile(r'\bother\s+%s\s+%s(?:markets|clusters)\b' % (_NUM, _QUALIFIERS), re.I)
_SUBSET_COUNT = re.compile(r'\b%s\s+(?:[\w-]+\s+){0,2}(?:markets|clusters)\b' % _NUM, re.I)
_TARGET_GEO = re.compile(
    r"\btarget[- ](?:markets?|states?|clusters?|geograph\w*)\b|\b(?:ORA|we|the firm|it)\s+targets?\b", re.I)
_HOLDINGS = re.compile(r'\b(?:holds?|holdings|owns?|spans)\b', re.I)
_STATE_TOKEN = re.compile(r'\b[A-Z]{2}\b')
_STATE_NAME = re.compile(r'\b(%s)\b' % '|'.join(STATE_NAMES), re.I)
_COUNT_TOKEN = re.compile(r'\b(\d{1,2}|%s)\b' % '|'.join(NUMBER_WORDS), re.I)
_LTV_40 = r'(?:at|to)\s+(?:an?\s+)?40\s*%\s*(?:LTV|loan[- ]to[- ]value)\b'
_DSCR_WORD = r'(?:DSCR|debt[- ]service[- ]coverage)'
_DSCR_PATTERNS = [
    re.compile(r'\b%s\b[^\n]{0,60}?\b%s' % (_DSCR_WORD, _LTV_40), re.I),
    re.compile(r'\b(?:size[sd]?|sizing|lever(?:ed|age)?|loan)\b[^\n]{0,40}?\b%s[^\n]{0,80}\b%s\b'
               % (_LTV_40, _DSCR_WORD), re.I),
]
# A correct governor summary ("leverage capped at 40% LTV aggregate") is not a DSCR test basis.
_AGGREGATE_CONTEXT = re.compile(r'^\s*(?:portfolio[- ])?aggregate\b', re.I)
_CAP_CONTEXT = re.compile(r'\b(?:cap(?:ped)?|ceiling|limit(?:ed)?)\s*$', re.I)
# dscr-floor-at-lesser-of (Gabriel in-turn ratification 2026-11-08)
_CLAUSE_SPLIT = re.compile(r'(?<=[.;])\s+')
_ABBREV = re.compile(r'\b(e\.g|i\.e|cf|vs)\.', re.I)
_DSCR_METRIC = re.compile(r'\b%ss?\b' % _DSCR_WORD, re.I)
_BINDING = re.compile(r'^[^.;]{0,30}?\b(?:binds|is the binding|binding constraint)\b', re.I)
# "1.25x DSCR", "1.25 DSCR", "1.25x minimum DSCR" are the sizing cap; a bare integer
# ("Stage 1 DSCR", "Year 1 DSCR", "Module 2 DSCR Check") is a label, not a cap.
_SIZING_CONSTRAINT = re.compile(
    r'(?:\d+\s*x|\d+\.\d+\s*x?|\d+(?:\.\d+)?\s*x?\s*minimum)\s*(?:minimum\s+)?[*_]*\s*$', re.I)
_DSCR_CAP_AFTER = re.compile(r'^[^.;]{0,40}?\b1\.25\s*x?\s*(?:minimum\s+)?%s' % _DSCR_WORD, re.I)
_FLOOR_CONTEXT = re.compile(r'1\.25|\bfloor|FLOOR-FLAG', re.I)
_WRONG_BASIS = re.compile(r'\blesser\b|\b(?:lower|smaller)\s+of\b|\bmin\s*\(|'
                          r'\brefi(?:nance)?[- ]siz(?:ing|ed)\b|\bas[- ]sized\b|\bmodeled refi\b', re.I)
_RIGHT_BASIS = re.compile(r'\b65\s*%[- ]?(?:LTV|loan[- ]to[- ]value)\b', re.I)
_NEGATION = re.compile(r'\b(?:never|not|no longer|instead of|rather than)\b[^,;()]{0,15}$', re.I)
_BASIS_REACH = 200
# dscr-floor-year1-noi (Gabriel in-turn ruling 2026-11-08, acquisition-underwriting v4.45)
_Y1 = r'(?:Year[- ]?(?:1|one)|Y1|first[- ]year|going[- ]in)'
_Y1_NOI = re.compile(r'\b%s\s+(?:NOI|net operating income)\b' % _Y1, re.I)
_Y1_DSCR = re.compile(r'\b%s\s+%ss?\b' % (_Y1, _DSCR_WORD), re.I)
# Read in the text right AFTER the Year-1 phrase, within one sentence: "Year-1 DSCR ... is not the
# floor", "...; it is never the floor", "(going-in NOI is reported separately)". "never the floor
# BASIS" is the v4.44 wording about the lesser-of loan, so it excuses nothing.
_NOT_THE_FLOOR_AFTER = re.compile(
    r"^[^.]{0,120}?(?:\b(?:not|never|no longer|isn['’]t)\s+(?:the|a)\s+(?:DSCR\s+)?floor\b(?!\s+basis)"
    r"|\bseparate(?:ly)?\b)", re.I)
_Y1_REACH = 300  # the floor wording and a DSCR must sit this close to the Year-1 phrase
_HISTORY_HEADING = re.compile(
    r'^(#{1,6})\s.*\b(changelog|change log|version history|revision history|release notes)\b', re.I)
_HEADING = re.compile(r'^(#{1,6})\s')
_VERSION_LINE = re.compile(r'^\s*(?:[-*]\s+|\|\s*)?\*{0,2}v\d+\.\d+\b')

Clusters = namedtuple('Clusters', 'count states established allowed_states names')


def line_key(line):
    """Short hash of the whole line, whitespace-normalized: part of every ALLOWED key."""
    return hashlib.sha1(' '.join(line.split()).encode('utf-8')).hexdigest()[:10]


class Finding(namedtuple('Finding', 'path line check message phrase linekey allowed')):
    def __str__(self):
        tag = ' (allowlisted; reason in ALLOWED)' if self.allowed else ''
        return '%s:%d: [%s] %s%s' % (self.path, self.line, self.check, self.message, tag)


def _as_int(token):
    token = token.lower()
    return NUMBER_WORDS[token] if token in NUMBER_WORDS else int(token)


def _phrase(text):
    return ' '.join(text.lower().split())


def count_claims(line, n_clusters):
    """[(check, message, phrase)] for count claims about the cluster set.

    Every claim is collected with its span first; where patterns overlap ("ORA's 10
    target-market clusters" matches two of them) the longest match wins. An "other N" whose
    expectation depends on a subset count stated earlier in the line ("Tier A covers three
    clusters; the other eight") is reported as cluster-count-subset even when the arithmetic
    holds: the subset itself is unverifiable here and was the stale part of the defect this
    check exists for (county-sales-monitor, 2026-11-05), so each one needs a reviewed allowlist
    entry. A count equal to the cluster total is never treated as a subset.
    """
    claims = []
    for match in _OTHER_PATTERN.finditer(line):
        before = line[:match.start()]
        subsets = [_as_int(m.group(1)) for m in _SUBSET_COUNT.finditer(before)]
        subset = sum(c for c in subsets if c != n_clusters)
        claims.append((match, n_clusters - (subset if subset else 1), bool(subset)))
    for pattern in _FULL_SET_PATTERNS:
        claims += [(match, n_clusters, False) for match in pattern.finditer(line)]
    claims.sort(key=lambda c: (c[0].start(), -(c[0].end() - c[0].start())))
    found, taken = [], []
    for match, expected, via_subset in claims:
        if any(match.start() < end and start < match.end() for start, end in taken):
            continue
        taken.append((match.start(), match.end()))
        if _as_int(match.group(1)) != expected:
            found.append(('cluster-count', '"%s" but target-markets.json gives %d' % (match.group(0), expected),
                          _phrase(match.group(0))))
        elif via_subset:
            found.append(('cluster-count-subset',
                          '"%s" holds only if the subset count earlier in the line is current; confirm it '
                          'and allowlist the line' % match.group(0), _phrase(match.group(0))))
    return found


def _state_positions(line):
    hits = [(m.start(), m.group(0)) for m in _STATE_TOKEN.finditer(line) if m.group(0) in US_STATES]
    hits += [(m.start(), STATE_NAMES[m.group(0).lower()]) for m in _STATE_NAME.finditer(line)]
    return sorted(hits)


def _labeled_watch(line, code):
    return bool(re.search(r'\b%s\b\s*[(:-]?\s*watch' % code, line, re.I)
                or re.search(r'\bwatch\w*\b[^.;]{0,25}\b%s\b' % code, line, re.I))


def target_geography(line, clusters):
    """[(message, phrase)] when a line presents an incomplete or padded list as ORA's target set."""
    hits = _state_positions(line)
    named = {code for _, code in hits}
    if len(named) < 5 or len(named & set(clusters.established)) < 4:
        return []
    first, last = hits[0][0], hits[-1][0]
    before = [m for m in _TARGET_GEO.finditer(line) if first - LOOKBACK <= m.start() < first]
    after = [m for m in _TARGET_GEO.finditer(line) if last < m.start() <= last + LOOKAHEAD]
    if before:
        if _HOLDINGS.search(line[before[-1].end():first]):
            return []
        anchor = before[-1]
    elif after:
        if _HOLDINGS.search(line[last:after[0].start()]):
            return []
        anchor = after[0]
    else:
        return []
    window = line[max(0, anchor.start() - 30):anchor.start()]
    counts = [_as_int(t) for t in _COUNT_TOKEN.findall(window)]
    if counts and counts[0] < clusters.count:
        return []
    problems = []
    missing = sorted(set(clusters.states) - named)
    if missing:
        problems.append('target geography omits cluster states %s (target-markets.json)' % ', '.join(missing))
    extra = sorted(code for code in named - set(clusters.allowed_states)
                   if not _labeled_watch(line, code))  # "...; TN watch" names a watch market, not a target
    if extra:
        problems.append('target geography lists %s, which no cluster in target-markets.json covers'
                        % ', '.join(extra))
    named_clusters = [name for name, tokens in clusters.names
                      if any(re.search(r'\b%s\b' % re.escape(t), line, re.I) for t in tokens)]
    if len(named_clusters) >= 4 and len(named_clusters) < len(clusters.names):
        absent = [name for name, _ in clusters.names if name not in named_clusters]
        problems.append('target geography names %d of %d clusters; missing %s'
                        % (len(named_clusters), len(clusters.names), ', '.join(absent)))
    return [(p, _phrase(p)) for p in problems]


def dscr_at_aggregate(line):
    for pattern in _DSCR_PATTERNS:
        match = pattern.search(line)
        if not match:
            continue
        ltv = re.search(_LTV_40, match.group(0), re.I)
        ltv_start = match.start() + ltv.start()
        ltv_end = match.start() + ltv.end()
        if _AGGREGATE_CONTEXT.match(line[ltv_end:ltv_end + 25]) or _CAP_CONTEXT.search(line[max(0, ltv_start - 15):ltv_start]):
            continue
        return [('"%s": 40%% is the portfolio-aggregate governor; size per-property debt at the lesser '
                 'of 65%% LTV and 1.25x DSCR' % match.group(0), _phrase(match.group(0)))]
    return []


def _bases(clause):
    hits = [(m.start(), m.end(), 'wrong') for m in _WRONG_BASIS.finditer(clause)]
    for m in _RIGHT_BASIS.finditer(clause):
        # "LESSER of 65% LTV" is the lesser-of loan, not a 65%-LTV loan; so is "65% LTV / 1.25x
        # DSCR" (the sizing pair), so a 65% LTV followed within 40 characters by 1.25x DSCR is untrusted
        if (not _WRONG_BASIS.search(clause[max(0, m.start() - 20):m.start()])
                and not _DSCR_CAP_AFTER.search(clause[m.end():])):
            hits.append((m.start(), m.end(), 'right'))
    return sorted(hits)


def dscr_floor_at_lesser_of(line):
    """[(message, phrase)] when a clause tests the 1.25x DSCR floor on the lesser-of loan."""
    found = []
    for clause in _CLAUSE_SPLIT.split(_ABBREV.sub(r'\1', line)):
        if not _FLOOR_CONTEXT.search(clause):
            continue
        bases = _bases(clause)
        if not bases or any(kind == 'right' for _, _, kind in bases):
            continue  # a clause that names the 65%-LTV loan states the ratified basis
        for metric in _DSCR_METRIC.finditer(clause):
            if _SIZING_CONSTRAINT.search(clause[max(0, metric.start() - 20):metric.start()]):
                continue
            if _BINDING.search(clause[metric.end():]):
                continue
            after = [b for b in bases if metric.end() <= b[0] <= metric.end() + _BASIS_REACH]
            before = [b for b in bases if metric.start() - _BASIS_REACH <= b[1] <= metric.start()]
            if after:
                start, end, kind = after[0]
            elif before:
                start, end, kind = before[-1]
            else:
                continue
            if kind != 'wrong' or _NEGATION.search(clause[max(0, start - 40):start]):
                continue
            phrase = clause[min(metric.start(), start):max(metric.end(), end)]
            found.append(('"%s": the 1.25x floor is DSCR at a loan sized to 65%% LTV (Gabriel in-turn '
                          'ratification 2026-11-08); the lesser-of loan clears 1.25x by construction'
                          % ' '.join(phrase.split()), _phrase(phrase)))
            break
    return found


def dscr_floor_year1_noi(line):
    """[(message, phrase)] when a line states the 1.25x DSCR floor on Year-1 (going-in) NOI.

    Unlike the lesser-of check this reads the whole physical line, not one clause: live floor
    statements put the floor wording and the NOI basis on either side of a ';' or an "incl."
    (2026-11-08 review). A Year-1 phrase counts when a DSCR and the floor wording (1.25, floor,
    FLOOR-FLAG) both sit within _Y1_REACH characters of it; it is excused by a negation directly
    before it ("not Year-1 NOI") or a "not/never ... floor" / "separate(ly)" right after it.
    """
    found = []
    for match in list(_Y1_NOI.finditer(line)) + list(_Y1_DSCR.finditer(line)):
        window = line[max(0, match.start() - _Y1_REACH):match.end() + _Y1_REACH]
        if not _FLOOR_CONTEXT.search(window) or not _DSCR_METRIC.search(window):
            continue
        if _NEGATION.search(line[max(0, match.start() - 40):match.start()]):
            continue  # "stabilized NOI, not Year-1 NOI"
        if _NOT_THE_FLOOR_AFTER.search(line[match.end():]):
            continue  # "Year-1 DSCR is reported as its own coverage line and is not the floor"
        found.append(('"%s": the 1.25x floor DSCR uses stabilized NOI, the NOI the refi is sized on '
                      '(Gabriel in-turn ruling 2026-11-08); Year-1 DSCR is a reported coverage line, '
                      'not the floor' % ' '.join(match.group(0).split()), _phrase(match.group(0))))
        break
    return found


def live_lines(text):
    """(line number, line) for lines outside changelog sections, version bullets and index rows."""
    history_level = None
    for number, line in enumerate(text.splitlines(), 1):
        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            if history_level is not None and level <= history_level:
                history_level = None
            if _HISTORY_HEADING.match(line):
                history_level = level
                continue
        if history_level is not None or _VERSION_LINE.match(line):
            continue
        yield number, line


def _files(repo):
    for top in sorted(repo.iterdir()):
        if not top.is_dir() or top.name.startswith(('_', '.')) or top.name in SKIP_TOP:
            continue
        if not (top / 'SKILL.md').is_file():
            continue
        for path in sorted(top.rglob('*')):
            rel = path.relative_to(repo)
            if not path.is_file() or path.suffix not in SUFFIXES or path.name.startswith('test_'):
                continue
            if any(part in SKIP_DIRS or part.startswith('_') for part in rel.parts[1:-1]):
                continue
            yield path, rel.as_posix()


def _cluster_tokens(market):
    primary = re.split(r'\s*[–—(-]\s*|\s+[A-Z]{2}(?:/[A-Z]{2})*\s*$', market)[0].strip()
    extra = re.findall(r'\(([^)]*)\)', market)
    tokens = [primary] + [t.strip() for part in extra for t in part.split('/')]
    return [t for t in tokens if len(t) >= 4]


def load_clusters(repo):
    data = json.loads((repo / 'target-markets.json').read_text(encoding='utf-8'))
    clusters = data['clusters']
    states = sorted({c['state'] for c in clusters if c.get('state')})
    established = sorted({c['state'] for c in clusters if c.get('state') and c.get('status') == 'established'})
    allowed = set(states)
    names = []
    for c in clusters:
        market = c.get('market') or ''
        allowed.update(code for code in re.findall(r'\b[A-Z]{2}\b', market) if code in US_STATES)
        if market:
            names.append((market, _cluster_tokens(market)))
    return Clusters(len(clusters), states, established or states, sorted(allowed), names)


def scan(repo):
    clusters = load_clusters(repo)
    raw = []
    for path, rel in _files(repo):
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in live_lines(text):
            items = list(count_claims(line, clusters.count))
            items += [('target-geography', m, p) for m, p in target_geography(line, clusters)]
            items += [('dscr-at-aggregate-ltv', m, p) for m, p in dscr_at_aggregate(line)]
            items += [('dscr-floor-at-lesser-of', m, p) for m, p in dscr_floor_at_lesser_of(line)]
            items += [('dscr-floor-year1-noi', m, p) for m, p in dscr_floor_year1_noi(line)]
            for check, message, phrase in items:
                raw.append((rel, number, check, message, phrase, line_key(line)))
    seen = Counter()
    findings = []
    for rel, number, check, message, phrase, key_of_line in raw:
        key = (rel, check, phrase, key_of_line)
        seen[key] += 1
        allowed = key in ALLOWED and seen[key] <= ALLOWED[key][0]
        findings.append(Finding(rel, number, check, message, phrase, key_of_line, allowed))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--repo', default=str(REPO))
    args = parser.parse_args(argv)
    try:
        findings = scan(Path(args.repo))
    except (OSError, ValueError, KeyError) as exc:
        print('doctrine_consistency: cannot read target-markets.json: %s' % exc, file=sys.stderr)
        return 2
    for finding in findings:
        print(finding)
    unexplained = [f for f in findings if not f.allowed]
    print('doctrine_consistency: %d finding(s), %d unexplained' % (len(findings), len(unexplained)))
    return 1 if unexplained else 0


if __name__ == '__main__':
    sys.exit(main())
