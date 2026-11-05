#!/usr/bin/env python3
"""backtest_agenda.py - compile the inputs for the December acquisition-underwriting back-test.

WHY (2026-11-05): acquisition-underwriting moves scorecard weights ONLY at the annual
December back-test (OUTCOME FEEDBACK); floors and standing defaults ratified in-turn during
the year are re-confirmed there, and its RULE EVIDENCE admission rule sends every
single-incident rule to that session for review. Nothing put
the session's inputs in one place. They sat in the Rule Evidence ledger, the lessons column
of the deal decision ledger and staged doctrine patches. A hand-written agenda drafted on
2026-10-17 was nine doctrine versions behind by 2026-11-05. This script re-derives the
agenda from those files each time it runs, so it cannot go stale the same way.

READ-ONLY. It prints Markdown, or writes it to --out. It never edits doctrine, never
proposes a weight, floor or constant, and never writes Notion, a ledger or the back-test
dataset. Weights move only by Gabriel's ratification at the session.

Usage:
  python tools/backtest_agenda.py [--session-date YYYY-MM-DD] [--since YYYY-MM-DD]
                                  [--ledger PATH | --no-ledger] [--patches DIR]
                                  [--out PATH] [--repo PATH]

  --session-date  planned session date (default: December 15 of the current year)
  --since         decision-ledger rows dated on or after this (default: session date - 365 days)
  --ledger        deal decision ledger (default: the firm memory copy under ~/.claude/projects)
  --patches       folder of staged doctrine patches; each '# base: vX.Y' stamp is compared
                  with the current doctrine version (depth-bounded, 3 levels)
  --repo          ora-skills checkout (default: the one this script lives in)

Exit: 0 agenda produced · 1 the doctrine file or the Rule Evidence ledger could not be read
      or parsed · 2 bad arguments.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCTRINE = Path('acquisition-underwriting', 'SKILL.md')
EVIDENCE = Path('acquisition-underwriting', 'versions', 'CHANGELOG.md')
TARGET_MARKETS = Path('target-markets.json')
DEFAULT_LEDGER = (Path.home() / '.claude' / 'projects'
                  / 'C--Users-Owner-OneDrive---Oxford-Capital-Partners' / 'memory'
                  / 'deal-decision-ledger.md')
PATCH_SUFFIXES = {'.md', '.patch', '.diff', '.txt'}
PATCH_MAX_DEPTH = 3
RULE_PREVIEW = 240

_LEDGER_HEADING = re.compile(r'^## Rule Evidence ledger\b')
_SUNSET = re.compile(r'\bsunset\b(?: review)?\s*:?\s*(.+?)\s*(?:;|$)', re.IGNORECASE)
_DECEMBER = re.compile(r'\bDecember\s+(\d{4})\b|\b(\d{4})\s+December\b', re.IGNORECASE)
_NEXT_DECEMBER = re.compile(r'\bnext\s+December\b', re.IGNORECASE)
_TWELVE_MONTHS = re.compile(r'\bfollows\s+the\s+next\s+12\s+months\b', re.IGNORECASE)
_EVIDENCE_ID = re.compile(r'^RE-\d+\.\d+-\d+$')
_ISO_DATE = re.compile(r'\b(\d{4})-(\d{2})-(\d{2})\b')
_VERSION_IN_H1 = re.compile(r'\(v(\d+\.\d+)')
_INDEX_ROW = re.compile(r'^\|\s*(v\d+\.\d+)\s*\|')
_INDEX_DATE_ROW = re.compile(r'^\|\s*v(\d+\.\d+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|')
_EVIDENCE_VERSION = re.compile(r'^RE-(\d+\.\d+)-')
_HEADER_FIELDS = {
    'evidence id': 'id', 'entry': 'entry', 'incidents': 'incidents', 'expected loss': 'expected_loss',
    'class': 'evidence_class', 'evidence class': 'evidence_class', 'testable via': 'testable',
    'testable': 'testable', 'sunset': 'sunset_col', 'sunset review': 'sunset_col',
}
_REQUIRED_FIELDS = ('id', 'entry', 'incidents', 'expected_loss', 'evidence_class', 'testable')
_LEDGER_ROW = re.compile(r'^\|\s*(\d{4}-\d{2}-\d{2})\s*\|')
_BASE_STAMP = re.compile(
    r'#\s*base:\s*(?:(?!v\d)(?P<skill>[a-z][a-z0-9-]*)\b\s*)?(?:v(?P<version>\d+\.\d+))?'
    r'(?:[^\n]*?(?:SHA-?256|\bsha\b)\s*[:=]?\s*(?P<sha>[0-9a-f]{6,64}))?', re.IGNORECASE)


class AgendaError(Exception):
    """A required input is missing or no longer has the format this script parses."""


def _cells(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def _unique(items):
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def parse_doctrine_version(text):
    """Version from the first H1 line, e.g. '# Title (v4.41 — Buy Box v1.1)' -> '4.41'."""
    for line in text.splitlines():
        if line.startswith('# '):
            match = _VERSION_IN_H1.search(line)
            return match.group(1) if match else None
    return None


def duplicate_versions(text):
    """Version labels used by more than one row of the index above the first '## ' heading."""
    labels = []
    for line in text.splitlines():
        if line.startswith('## '):
            break
        match = _INDEX_ROW.match(line)
        if match:
            labels.append(match.group(1))
    return _unique([v for v in labels if labels.count(v) > 1])


def _ledger_columns(header_cells):
    """Map the Rule Evidence table header to field names; a missing required column is an error."""
    columns = {}
    for index, name in enumerate(header_cells):
        field = _HEADER_FIELDS.get(' '.join(name.lower().split()))
        if field and field not in columns:
            columns[field] = index
    missing = [f for f in _REQUIRED_FIELDS if f not in columns]
    if missing:
        raise AgendaError('Rule Evidence table header lacks %s (got: %s)' % (', '.join(missing), header_cells))
    return columns


def parse_evidence_ledger(text):
    """Rows of the '## Rule Evidence ledger' table, stopping at the next '## ' heading.

    Columns are found by header name, so a reordered table or a new Sunset column parses
    correctly; a header that lacks a required column raises instead of mis-assigning cells.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if _LEDGER_HEADING.match(line)), None)
    if start is None:
        raise AgendaError("no '## Rule Evidence ledger' heading")
    columns, rows = None, []
    for line in lines[start + 1:]:
        if line.startswith('## '):
            break
        if not line.startswith('|') or line.startswith('|---') or line.replace('|', '').strip(' -:') == '':
            continue
        cells = _cells(line)
        if columns is None:  # the first table row in the section is the header
            columns = _ledger_columns(cells)
            continue
        raw_id = cells[columns['id']] if columns['id'] < len(cells) else ''
        ident = re.sub(r'[*_`\s]', '', raw_id)
        if not _EVIDENCE_ID.match(ident):
            # A row that is not an Evidence ID (bolded, re-spaced or malformed) would otherwise
            # vanish from the agenda without a trace; refuse instead (review finding C1f-b).
            raise AgendaError('unrecognized Rule Evidence row (Evidence ID cell %r)' % raw_id)
        cells[columns['id']] = ident
        width = max(columns.values()) + 1
        if len(cells) < width:
            raise AgendaError('Rule Evidence row has %d cells, header needs %d: %s' % (len(cells), width, cells[0]))
        last = max(columns.values())
        if len(cells) > width:  # a literal '|' inside the last column
            cells = cells[:last] + [' | '.join(cells[last:])]
        get = lambda field: cells[columns[field]] if field in columns else ''  # noqa: E731
        klass, testable = get('evidence_class'), get('testable')
        sunset = None
        column_text = get('sunset_col').strip()
        if column_text and column_text not in ('—', '-', 'n/a', 'none'):
            sunset = column_text.rstrip('. ')
        else:
            for source in (testable, klass):
                match = _SUNSET.search(source)
                if match:
                    sunset = match.group(1).rstrip('. ')
                    break
        rows.append({
            'id': get('id'), 'entry': get('entry'), 'incidents': get('incidents'),
            'expected_loss': get('expected_loss'), 'evidence_class': klass, 'testable': testable,
            'sunset': sunset, 'sunset_basis': 'explicit' if sunset else None, 'sunset_default': False,
            'single_incident': 'SINGLE-INCIDENT' in (klass + ' ' + testable).upper(),
            'incomplete': any('[per archive]' in c for c in cells),
            'unquantified': '[UNQUANTIFIED' in get('expected_loss').upper(),
        })
    if not rows:
        raise AgendaError('the Rule Evidence ledger section has no RE- rows')
    return rows


def parse_version_dates(text):
    """Earliest date per version in the index above the first '## ' heading ('| v4.41 | 2026-10-30 |')."""
    dates = {}
    for line in text.splitlines():
        if line.startswith('## '):
            break
        match = _INDEX_DATE_ROW.match(line)
        if match:
            try:
                day = dt.date.fromisoformat(match.group(2))
            except ValueError:
                continue
            version = match.group(1)
            dates[version] = min(day, dates.get(version, day))
    return dates


def _december_on_or_after(day):
    """The December back-test held on or after `day` (sessions convene after December 15)."""
    year = day.year if day <= dt.date(day.year, 12, 15) else day.year + 1
    return 'December %d back-test' % year


def apply_default_sunsets(rows, version_dates):
    """Fill in sunsets the ledger leaves blank or states without a year.

    sunset_basis becomes 'default' when a blank sunset takes the RULE EVIDENCE default:
    single-incident rules get the next December back-test after their version date (the
    admission rule); every other rule gets the December back-test that follows the next
    12 months of data (the Sunset review field default). It becomes 'resolved' when the
    text names a December without a year ("next December back-test"), anchored on the
    version date. A version with no index date leaves the sunset as it was.
    """
    out = []
    for row in rows:
        row = dict(row)
        match = _EVIDENCE_VERSION.match(row['id'])
        day = version_dates.get(match.group(1)) if match else None
        if day and not row['sunset']:
            anchor = day if row['single_incident'] else day + dt.timedelta(days=365)
            row['sunset'], row['sunset_basis'] = _december_on_or_after(anchor), 'default'
        elif day and row['sunset'] and not _DECEMBER.search(row['sunset']):
            # Only the two year-less forms the doctrine itself uses are resolved; any other
            # year-less text stays as written and is reported as unparsed, never guessed.
            if _TWELVE_MONTHS.search(row['sunset']):
                row['sunset'], row['sunset_basis'] = _december_on_or_after(day + dt.timedelta(days=365)), 'resolved'
            elif _NEXT_DECEMBER.search(row['sunset']):
                row['sunset'], row['sunset_basis'] = _december_on_or_after(day), 'resolved'
        row['sunset_default'] = row.get('sunset_basis') == 'default'
        out.append(row)
    return out


def sunset_parseable(sunset):
    return bool(sunset) and bool(_DECEMBER.search(sunset) or _ISO_DATE.search(sunset))


def sunset_due(sunset, session_date):
    """True when the sunset names this session's December (or earlier), or a date on or before it."""
    if not sunset:
        return False
    match = _DECEMBER.search(sunset)
    if match:
        return int(match.group(1) or match.group(2)) <= session_date.year
    match = _ISO_DATE.search(sunset)
    if match:
        try:
            return dt.date(*map(int, match.groups())) <= session_date
        except ValueError:
            return False
    return False


def evidence_integrity(rows):
    ids = [r['id'] for r in rows]
    return {
        'duplicate_ids': _unique([i for i in ids if ids.count(i) > 1]),
        'single_incident_without_sunset': _unique(
            [r['id'] for r in rows if r['single_incident'] and (not r['sunset'] or r.get('sunset_default'))]),
        'sunset_unknown': _unique([r['id'] for r in rows if not r['sunset']]),
        'sunset_unparsed': _unique([r['id'] for r in rows if r['sunset'] and not sunset_parseable(r['sunset'])]),
        'incomplete': _unique([r['id'] for r in rows if r['incomplete']]),
        'unquantified': _unique([r['id'] for r in rows if r['unquantified']]),
    }


def _lesson_kind(rule):
    text = rule.strip()
    upper = text.upper()
    if upper.startswith(('REFINE', 'ESTABLISH')):
        return 'refined'
    if upper.startswith(('VALIDAT', 'REINFORC', 'CONFIRM')):
        return 'validated'
    if text in ('', '—', '–', '-', 'n/a', 'N/A'):
        return 'none'
    return 'other'


def parse_decision_ledger(text, since):
    rows = []
    for line in text.splitlines():
        match = _LEDGER_ROW.match(line)
        if not match:
            continue
        try:
            day = dt.date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if day < since:
            continue
        cells = _cells(line)
        cells += [''] * (6 - len(cells))
        reason = cells[3]
        rows.append({
            'date': match.group(1), 'deal': cells[1], 'verdict': cells[2], 'reason': reason,
            'rule': cells[4], 'kind': _lesson_kind(cells[4]),
            'reason_missing': 'reason not logged' in reason.lower() or reason in ('', '—', '-'),
        })
    return rows


def scan_patch_bases(folder):
    """One dict per patch-like file at most PATCH_MAX_DEPTH levels down: path, skill, version, sha.

    Stamp forms accepted (first 10 lines): the v4.8 rule's '# base: v4.41 · SKILL.md SHA256 ...'
    (skill = acquisition-underwriting), '# base: <skill> v4.32 · ...', and the SHA-only
    '# base: <skill> · SKILL.md SHA256 <hex>' used for consumer-skill patches.
    """
    found = []
    for path in sorted(folder.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in PATCH_SUFFIXES:
            continue
        if len(path.relative_to(folder).parts) - 1 > PATCH_MAX_DEPTH:
            continue
        try:
            head = path.read_text(encoding='utf-8', errors='replace').splitlines()[:10]
        except OSError:
            continue
        stamp = next((m for m in map(_BASE_STAMP.search, head)
                      if m and (m.group('version') or m.group('sha'))), None)
        entry = {'path': str(path), 'skill': None, 'version': None, 'sha': None}
        if stamp:
            entry['skill'] = stamp.group('skill') or DOCTRINE.parts[0]
            entry['version'] = stamp.group('version')
            entry['sha'] = stamp.group('sha')
        found.append(entry)
    return found


def file_shas(path):
    """SHA256 hex digests of a file in its CRLF and LF forms (stamps cite either)."""
    raw = path.read_bytes()
    lf = raw.replace(b'\r\n', b'\n')
    return {hashlib.sha256(form).hexdigest() for form in (raw, lf, lf.replace(b'\n', b'\r\n'))}


def patch_status(patch, current_versions, current_shas=None):
    if not patch['skill']:
        return 'NO STAMP: base unknown, verify every anchor before applying'
    shas = (current_shas or {}).get(patch['skill'])
    if patch['version']:
        current = current_versions.get(patch['skill'])
        if current is None:
            return 'STAMPED v%s: current %s version not readable' % (patch['version'], patch['skill'])
        if patch['version'] != current:
            return 'STALE BASE (v%s vs current v%s): re-base before merge' % (patch['version'], current)
        if not patch['sha']:
            return 'UNVERIFIED (version v%s matches; the stamp carries no SHA): verify every anchor' % patch['version']
        if not shas:
            return 'UNVERIFIED (version v%s matches; SHA not checked): verify every anchor' % patch['version']
        if any(h.startswith(patch['sha'].lower()) for h in shas):
            return 'CURRENT'
        # Two changes have shared one version label (acquisition-underwriting v4.40, loi-generation
        # v1.16), so a matching label with a different file is a different base.
        return ('STALE BASE (same label v%s, but %s SKILL.md changed since the stamp): re-base before merge'
                % (patch['version'], patch['skill']))
    if not shas:
        return 'SHA STAMP (%s): compare with the current %s SKILL.md before applying' % (
            patch['sha'] or '?', patch['skill'])
    if any(h.startswith((patch['sha'] or '').lower()) for h in shas):
        return 'CURRENT (SHA match)'
    return 'STALE BASE (%s SKILL.md changed since the stamp): re-base before merge' % patch['skill']


def cluster_summary(repo):
    try:
        data = json.loads((repo / TARGET_MARKETS).read_text(encoding='utf-8'))
        return '%d at v%s' % (len(data['clusters']), data.get('version', '?'))
    except (OSError, ValueError, KeyError, TypeError):
        return 'file not readable'


def _md(text, limit=None):
    text = ' '.join(str(text).split()).replace('|', '\\|')
    if limit and len(text) > limit:
        text = text[:limit - 1].rstrip() + '…'
    return text


def _sunset_cell(row):
    label = {'default': ' (default)', 'resolved': ' (resolved from the version date)'}.get(row.get('sunset_basis'), '')
    return _md(row['sunset'] or '—') + label


def _render_lessons(add, since, lessons):
    refined = [r for r in lessons if r['kind'] == 'refined']
    validated = [r for r in lessons if r['kind'] == 'validated']
    other = [r for r in lessons if r['kind'] == 'other']
    missing = [r for r in lessons if r['reason_missing']]
    add('## 3. Decision-ledger lessons since %s (%d)' % (since.isoformat(), len(refined) + len(validated) + len(other)))
    add('')
    add('### Rule refinements, candidate amendments (%d)' % len(refined))
    add('')
    add('Each needs a Rule Evidence line before it can land. A refinement that already landed in the '
        'sourcing scan or another skill still needs checking against the scorecard.')
    add('')
    if refined:
        add('| Date | Deal | Verdict | Refinement |')
        add('|---|---|---|---|')
        for r in refined:
            add('| %s | %s | %s | %s |' % (r['date'], _md(r['deal'], 120), _md(r['verdict'], 60), _md(r['rule'], 400)))
    else:
        add('None.')
    add('')
    add('### Validated rules (%d)' % len(validated))
    add('')
    if validated:
        add('| Date | Deal | Rule |')
        add('|---|---|---|')
        for r in validated:
            add('| %s | %s | %s |' % (r['date'], _md(r['deal'], 120), _md(r['rule'], 300)))
    else:
        add('None.')
    add('')
    add('### Other lessons, unlabeled (%d)' % len(other))
    add('')
    add('Rule-column text without a REFINED / VALIDATED label. Read each: some are rules, some are pointers.')
    add('')
    if other:
        add('| Date | Deal | Verdict | Text |')
        add('|---|---|---|---|')
        for r in other:
            add('| %s | %s | %s | %s |' % (r['date'], _md(r['deal'], 120), _md(r['verdict'], 60), _md(r['rule'], 300)))
    else:
        add('None.')
    add('')
    add('### Decisions with no logged reason (%d)' % len(missing))
    add('')
    if missing:
        add('| Date | Deal | Verdict |')
        add('|---|---|---|')
        for r in missing:
            add('| %s | %s | %s |' % (r['date'], _md(r['deal'], 120), _md(r['verdict'], 80)))
    else:
        add('None.')
    add('')


def render(session_date, since, version, evidence, dup_versions, lessons, ledger_note,
           patches, patch_note, clusters, skill_versions=None, skill_shas=None):
    out = []
    add = out.append
    due = [r for r in evidence if sunset_due(r['sunset'], session_date)]
    due_single = [r for r in due if r['single_incident']]
    due_other = [r for r in due if not r['single_incident']]
    integrity = evidence_integrity(evidence)

    add('# Acquisition-underwriting back-test agenda — session %s' % session_date.isoformat())
    add('')
    add('- **Doctrine:** `acquisition-underwriting` v%s (SKILL.md H1).' % (version or '?'))
    add('- **Sources:** `%s` (Rule Evidence ledger, %d entries) · %s · %s.'
        % (EVIDENCE.as_posix(), len(evidence), ledger_note, patch_note))
    add('- **Lessons window:** decision-ledger rows dated %s to %s.' % (since.isoformat(), session_date.isoformat()))
    add('')
    add('> **This agenda proposes nothing.** Scorecard weights move only at this session, by Gabriel\'s '
        'ratification (acquisition-underwriting OUTCOME FEEDBACK); floors and standing defaults change only '
        'by his ratification, in-turn during the year or here. Governor constants are outside this '
        'session\'s scope. Every item below is an input to the session, not a recommendation.')
    add('')

    add('## 1. Rule Evidence up for review (%d)' % len(due))
    add('')
    add('Entries whose sunset falls at or before this session. "(default)" marks a sunset the ledger '
        'leaves blank and the RULE EVIDENCE defaults fill in.')
    add('')
    add('### Single-incident rules (%d)' % len(due_single))
    add('')
    add('Under the RULE EVIDENCE admission rule each needs a second independent incident, or a review for retirement.')
    add('')
    if due_single:
        add('| Evidence ID | Rule | Incidents | Testable via | Sunset |')
        add('|---|---|---|---|---|')
        for r in due_single:
            add('| %s | %s | %s | %s | %s |' % (r['id'], _md(r['entry'], RULE_PREVIEW), _md(r['incidents']),
                                             _md(r['testable']), _sunset_cell(r)))
    else:
        add('None.')
    add('')
    add('### Other rules at their sunset (%d)' % len(due_other))
    add('')
    if due_other:
        add('| Evidence ID | Rule | Class | Testable via | Sunset |')
        add('|---|---|---|---|---|')
        for r in due_other:
            add('| %s | %s | %s | %s | %s |' % (r['id'], _md(r['entry'], RULE_PREVIEW), _md(r['evidence_class'], 160),
                                             _md(r['testable']), _sunset_cell(r)))
    else:
        add('None.')
    add('')

    problems = []
    if integrity['duplicate_ids']:
        problems.append('Duplicate Evidence IDs: %s. A CONFIRMED / REFUTED verdict cannot be attributed to one '
                        'rule. Re-key one entry before recording verdicts.' % ', '.join(integrity['duplicate_ids']))
    if dup_versions:
        problems.append('Version labels used twice in the SKILL.md index: %s. Two changes share one version, '
                        'so an installed copy cannot be identified by its version alone.' % ', '.join(dup_versions))
    if integrity['single_incident_without_sunset']:
        problems.append('Single-incident rules with no explicit sunset: %s. The admission rule gives each a sunset at '
                        'the next December back-test; this agenda applies that default.'
                        % ', '.join(integrity['single_incident_without_sunset']))
    if integrity['sunset_unparsed']:
        problems.append('Sunsets that are conditional or not a date: %s. They never come due on their own; '
                        'review each by hand.' % ', '.join(
                            '%s ("%s")' % (r['id'], _md(r['sunset'], 80)) for r in evidence
                            if r['id'] in integrity['sunset_unparsed']))
    if integrity['sunset_unknown']:
        problems.append('Entries whose sunset cannot be resolved (no explicit sunset, and the version is not in the '
                        'SKILL.md index): %s. Review them by hand.' % ', '.join(integrity['sunset_unknown']))
    if integrity['incomplete']:
        problems.append('Entries with fields still marked `[per archive]`: %s.' % ', '.join(integrity['incomplete']))
    if integrity['unquantified']:
        problems.append('Entries whose expected loss is `[UNQUANTIFIED]` (%d): %s. Each names the data that would '
                        'quantify it; check whether that data now exists.'
                        % (len(integrity['unquantified']), ', '.join(integrity['unquantified'])))
    add('## 2. Evidence ledger integrity (%d)' % len(problems))
    add('')
    out.extend(['- ' + p for p in problems] or ['None found.'])
    add('')

    if lessons is None:
        add('## 3. Decision-ledger lessons since %s (not read)' % since.isoformat())
        add('')
        add(ledger_note[0].upper() + ledger_note[1:] + '. Pass `--ledger PATH` to include it.')
        add('')
    else:
        _render_lessons(add, since, lessons)

    add('## 4. Staged patches')
    add('')
    if patches is None:
        add('No patch folder given (`--patches`).')
    elif not patches:
        add('No patch files found.')
    else:
        add('From the %s. Each stamp is compared with the named skill\'s current H1 version.' % patch_note)
        add('')
        add('| File | Skill | Base | Status |')
        add('|---|---|---|---|')
        for patch in patches:
            base = ('v' + patch['version']) if patch['version'] else (patch['sha'] or '—')
            add('| `%s` | %s | %s | %s |' % (_md(Path(patch['path']).name), patch['skill'] or '—',
                                            base, patch_status(patch, skill_versions or {}, skill_shas)))
    add('')

    add('## 5. Inputs to confirm by hand')
    add('')
    add('These cannot be checked from files. The list gives pointers, not values.')
    add('')
    add('- The Pre-December checklist in `acquisition-underwriting/references/outcome-feedback-and-backtest.md` '
        '(Retro-underwrite calibration dataset section).')
    add('- Drift sweep: `market-monitor` DOCTRINE-DRIFT for every cluster in `target-markets.json` (%s).' % clusters)
    add('- Lost-deal ledger: classified `Loss Class` rows on the Notion Deal Sourcing Log against the sample threshold in the same reference. '
        'Count only rows with `LOI Outcome` not `WON` and `Exclude from Calibration` unchecked: a `WON` row is a deal ORA bought, never a loss.')
    add('- Passed and lost deals: `Winning Price` and `Winning Price Confidence` against `Walk Price` and `ORA Max Defensible Price` on the Deal Sourcing Log.')
    add('- Exception Register tripwire (acquisition-underwriting EXCEPTION REGISTER + TRIPWIRE).')
    add("- After ratification: one supervised `acquisition-underwriting-eval-harness` replay. Goldens are re-baselined only on Gabriel's sign-off.")
    add('')
    return '\n'.join(out)


def _parse_date(value, flag):
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise AgendaError('%s must be YYYY-MM-DD, got %r' % (flag, value))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--repo', default=str(REPO))
    parser.add_argument('--session-date')
    parser.add_argument('--since')
    parser.add_argument('--ledger', default=str(DEFAULT_LEDGER))
    parser.add_argument('--no-ledger', action='store_true')
    parser.add_argument('--patches')
    parser.add_argument('--out')
    args = parser.parse_args(argv)

    try:
        session = (_parse_date(args.session_date, '--session-date') if args.session_date
                   else dt.date(dt.date.today().year, 12, 15))
        since = (_parse_date(args.since, '--since') if args.since
                 else session - dt.timedelta(days=365))
    except AgendaError as exc:
        print('backtest_agenda: %s' % exc, file=sys.stderr)
        return 2

    repo = Path(args.repo)
    try:
        doctrine = (repo / DOCTRINE).read_text(encoding='utf-8')
        evidence = apply_default_sunsets(parse_evidence_ledger((repo / EVIDENCE).read_text(encoding='utf-8')),
                                         parse_version_dates(doctrine))
    except (OSError, AgendaError) as exc:
        print('backtest_agenda: cannot build the agenda: %s' % exc, file=sys.stderr)
        return 1

    lessons = []
    if args.no_ledger:
        lessons, ledger_note = None, 'deal decision ledger not read (--no-ledger)'
    else:
        ledger_path = Path(args.ledger)
        try:
            lessons = parse_decision_ledger(ledger_path.read_text(encoding='utf-8'), since)
            ledger_note = 'deal decision ledger `%s`' % ledger_path
        except OSError:
            lessons, ledger_note = None, 'deal decision ledger not found at `%s`' % ledger_path

    patches, patch_note = None, 'no patch folder given'
    if args.patches:
        folder = Path(args.patches)
        patches = scan_patch_bases(folder) if folder.is_dir() else []
        patch_note = 'patch folder `%s`%s' % (folder, '' if folder.is_dir() else ' (not found)')

    version = parse_doctrine_version(doctrine)
    skill_versions, skill_shas = {DOCTRINE.parts[0]: version}, {}
    for patch in patches or []:
        skill = patch['skill']
        if skill and skill not in skill_shas:
            skill_file = repo / skill / 'SKILL.md'
            try:
                skill_shas[skill] = file_shas(skill_file)
                skill_versions.setdefault(skill, parse_doctrine_version(skill_file.read_text(encoding='utf-8')))
            except OSError:
                skill_shas[skill] = set()
                skill_versions.setdefault(skill, None)
    text = render(session, since, version, evidence, duplicate_versions(doctrine), lessons,
                  ledger_note, patches, patch_note, cluster_summary(repo), skill_versions, skill_shas)
    if args.out:
        Path(args.out).write_text(text + '\n', encoding='utf-8')
        print('backtest_agenda: wrote %s' % args.out)
    else:
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
            except (OSError, ValueError):
                pass
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
