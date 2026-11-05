#!/usr/bin/env python3
"""doctrine_consistency.py - catch skill text that has drifted from its source of truth.

WHY (2026-11-05 data-flow review): facts paraphrased across skills drifted in ways no
existing probe sees. buybox-drift-probe covers price statements and governor-drift-probe
covers DSCR/LTV numbers. This covers three semantic restatements:

  cluster-count          "N canonical markets/clusters", "N target-market clusters",
                         "ORA's N clusters" must equal len(target-markets.json clusters);
                         "the other N clusters" must equal that minus one.
  target-geography       a line that talks about targets and lists five or more state codes
                         must include every cluster state in target-markets.json. Holdings
                         statements ("ORA spans OH, MD, ...") do not mention targets and
                         are left alone.
  dscr-at-aggregate-ltv  DSCR tested "at 40% LTV". 40% is the portfolio-aggregate governor;
                         per-property debt is sized at the lesser of 65% LTV and 1.25x DSCR
                         (acquisition-underwriting UNDERWRITING CONVENTIONS).

History is exempt: changelog sections, version bullets and index rows, versions/ and
_archive/ may quote old values. ALLOWED lists known findings that wait on a decision; each
entry carries its reason, and the test suite fails on an entry that no longer matches.

Usage: python tools/doctrine_consistency.py [--repo PATH]
Exit:  0 nothing unexplained · 1 unexplained findings · 2 target-markets.json unreadable
"""
import argparse
import json
import re
import sys
from collections import namedtuple
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKIP_TOP = {'tools', 'docs', 'plugins'}
SKIP_DIRS = {'versions', 'tests', 'fixtures', 'golden_set', '__pycache__', 'node_modules', 'runs'}
SUFFIXES = {'.md', '.js', '.py'}

ALLOWED = {
    ('acquisition-underwriting/references/outcome-feedback-and-backtest.md', 'cluster-count'):
        'Says "all ten canonical markets" and omits Chicago. The fix rides the next '
        'acquisition-underwriting version, so it does not collide with the 2026-11-04 '
        'rulings recorded as "staged as v4.42" (docs/plans/2026-11-05_skill-dataflow-calibration-review.md).',
    ('acquisition-underwriting/references/market-and-cost-calibration-data.md', 'cluster-count'):
        'A dated 2026-08-11 correction note ("the other nine clusters"); nine was right when ten '
        'clusters existed. Rewording rides the next acquisition-underwriting version, as above.',
    ('portfolio-growth/SKILL.md', 'dscr-at-aggregate-ltv'):
        'Changing the DSCR test basis is a financial-model methodology change (Hard Invariant 4) '
        'and waits on Gabriel. deal-comparison v1.2 fixed the same defect with his approval.',
}

US_STATES = set('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO '
                'MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())
STATE_NAMES = {'ohio': 'OH', 'maryland': 'MD', 'indiana': 'IN', 'wisconsin': 'WI', 'missouri': 'MO',
               'kansas': 'KS', 'michigan': 'MI', 'virginia': 'VA', 'iowa': 'IA', 'kentucky': 'KY',
               'illinois': 'IL', 'tennessee': 'TN'}
NUMBER_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
                'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
                'fourteen': 14, 'fifteen': 15}
LOOKBACK = 160
_NUM = r'(\d{1,2}|%s)' % '|'.join(NUMBER_WORDS)
_COUNT_PATTERNS = [
    (re.compile(r'\b%s\s+canonical\s+(?:target[- ]market\s+)?(?:markets|clusters)\b' % _NUM, re.I), 0),
    (re.compile(r'\b%s\s+target[- ]market\s+clusters\b' % _NUM, re.I), 0),
    (re.compile(r'\bother\s+%s\s+(?:canonical\s+)?(?:target[- ]market\s+)?clusters\b' % _NUM, re.I), -1),
    (re.compile(r"\bORA['’]s\s+%s\s+clusters\b" % _NUM, re.I), 0),
]
_TARGET_WORD = re.compile(r'\btarget', re.I)
_STATE_TOKEN = re.compile(r'\b[A-Z]{2}\b')
_STATE_NAME = re.compile(r'\b(%s)\b' % '|'.join(STATE_NAMES), re.I)
_COUNT_TOKEN = re.compile(r'\b(\d{1,2}|%s)\b' % '|'.join(NUMBER_WORDS), re.I)
_DSCR_AT_AGGREGATE = re.compile(r'\bDSCR\b[^\n]{0,40}?\bat\s+40\s*%\s*LTV\b', re.I)
_HISTORY_HEADING = re.compile(
    r'^(#{1,6})\s.*\b(changelog|change log|version history|revision history|release notes)\b', re.I)
_HEADING = re.compile(r'^(#{1,6})\s')
_VERSION_LINE = re.compile(r'^\s*(?:[-*]\s+|\|\s*)?\*{0,2}v\d+\.\d+\b')


class Finding(namedtuple('Finding', 'path line check message allowed')):
    def __str__(self):
        tag = ' (allowed: waits on a decision)' if self.allowed else ''
        return '%s:%d: [%s] %s%s' % (self.path, self.line, self.check, self.message, tag)


def _as_int(token):
    token = token.lower()
    return NUMBER_WORDS[token] if token in NUMBER_WORDS else int(token)


def count_claims(line, n_clusters):
    found = []
    for pattern, offset in _COUNT_PATTERNS:
        for match in pattern.finditer(line):
            expected = n_clusters + offset
            if _as_int(match.group(1)) != expected:
                found.append('"%s" but target-markets.json gives %d' % (match.group(0), expected))
    return found


def _state_positions(line):
    hits = [(m.start(), m.group(0)) for m in _STATE_TOKEN.finditer(line) if m.group(0) in US_STATES]
    hits += [(m.start(), STATE_NAMES[m.group(0).lower()]) for m in _STATE_NAME.finditer(line)]
    return sorted(hits)


def target_geography(line, cluster_states, established_states, n_clusters):
    """Flag a line that presents an incomplete state list as ORA's whole target set.

    It fires only when every condition holds:
      * at least five states are named, and at least four of them are established-cluster states
        (a list of entry-phase clusters alone is a deliberate subset);
      * the word 'target' comes within LOOKBACK characters BEFORE the first state named (a tax
        line that mentions targets after its own state list is about something else);
      * no count smaller than the cluster total sits just before that 'target'
        ("five of ten target clusters" is a counted subset, not the target set);
      * some cluster state from target-markets.json is missing.
    """
    hits = _state_positions(line)
    named = {code for _, code in hits}
    if len(named) < 5 or len(named & set(established_states)) < 4:
        return []
    first = hits[0][0]
    targets = [m for m in _TARGET_WORD.finditer(line) if first - LOOKBACK <= m.start() < first]
    if not targets:
        return []
    window = line[max(0, targets[-1].start() - 30):targets[-1].start()]
    counts = [_as_int(t) for t in _COUNT_TOKEN.findall(window)]
    if counts and counts[0] < n_clusters:
        return []
    missing = sorted(set(cluster_states) - named)
    if not missing:
        return []
    return ['target geography omits cluster states %s (target-markets.json)' % ', '.join(missing)]


def dscr_at_aggregate(line):
    match = _DSCR_AT_AGGREGATE.search(line)
    if not match:
        return []
    return ['"%s": 40%% is the portfolio-aggregate governor; size per-property debt at the lesser '
            'of 65%% LTV and 1.25x DSCR' % match.group(0)]


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


def load_clusters(repo):
    """(cluster count, cluster states, established-cluster states) from target-markets.json."""
    data = json.loads((repo / 'target-markets.json').read_text(encoding='utf-8'))
    clusters = data['clusters']
    states = sorted({c['state'] for c in clusters if c.get('state')})
    established = sorted({c['state'] for c in clusters if c.get('state') and c.get('status') == 'established'})
    return len(clusters), states, established or states


def scan(repo):
    n_clusters, cluster_states, established = load_clusters(repo)
    findings = []
    for path, rel in _files(repo):
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in live_lines(text):
            checks = (('cluster-count', count_claims(line, n_clusters)),
                      ('target-geography', target_geography(line, cluster_states, established, n_clusters)),
                      ('dscr-at-aggregate-ltv', dscr_at_aggregate(line)))
            for check, messages in checks:
                for message in messages:
                    findings.append(Finding(rel, number, check, message, (rel, check) in ALLOWED))
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
