#!/usr/bin/env python3
"""land_gate.py - readiness verdict for /land. Stdlib only.

Reads `gh pr view --json state,mergeable,reviewDecision,files` and
`gh pr checks --json name,bucket,state,link` from files, plus
known-external-failures.json, and prints one JSON verdict.

Exit: 0 GO (merge allowed, subject to the flags) | 1 STOP | 2 WAIT (checks pending).
Flags in the verdict: confirm_required (deploy-on-merge repo, needs in-turn yes),
adversarial_review_required (blast-radius path touched).
"""
import argparse
import fnmatch
import json
import sys
from pathlib import Path

DEFAULT_ALLOWLIST = Path(__file__).resolve().parent.parent / 'known-external-failures.json'
RED = {'fail', 'cancel'}


def glob_match(path, pattern):
    if fnmatch.fnmatch(path, pattern):
        return True
    # '**/x' also matches a root-level 'x'.
    return pattern.startswith('**/') and fnmatch.fnmatch(path, pattern[3:])


def evaluate(repo, pr, checks, allow):
    stops, waits, info = [], [], []
    if pr.get('state') != 'OPEN':
        stops.append(f"PR state is {pr.get('state')}, not OPEN")
    mergeable = pr.get('mergeable')
    if mergeable == 'CONFLICTING':
        stops.append('merge conflicts: update the branch first')
    elif mergeable != 'MERGEABLE':
        stops.append(f'mergeable={mergeable}: re-query once, GitHub may still be computing')
    decision = pr.get('reviewDecision') or ''
    if decision in ('CHANGES_REQUESTED', 'REVIEW_REQUIRED'):
        stops.append(f'reviewDecision={decision}')

    informational = {e['check'] for e in allow.get('informational', []) if e['repo'] == repo}
    for c in checks:
        name, bucket = c['name'], c.get('bucket')
        if name in informational and bucket != 'pass':
            info.append(f'{name}: {bucket} (allowlisted informational, not blocking)')
        elif bucket in RED:
            stops.append(f'check red: {name} ({bucket}) {c.get("link", "")}'.strip())
        elif bucket == 'pending':
            waits.append(f'check pending: {name}')

    files = [f['path'] if isinstance(f, dict) else f for f in pr.get('files', [])]
    blast = sorted(f for f in files if any(glob_match(f, g) for g in allow.get('blast_radius_globs', [])))
    deploy = [e['why'] for e in allow.get('deploy_on_merge', []) if e['repo'] == repo]

    verdict = 'STOP' if stops else ('WAIT' if waits else 'GO')
    return {
        'verdict': verdict, 'stops': stops, 'waits': waits, 'informational': info,
        'confirm_required': bool(deploy), 'confirm_reason': deploy[0] if deploy else None,
        'adversarial_review_required': bool(blast), 'blast_radius_files': blast,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True, help='OWNER/REPO')
    ap.add_argument('--pr-json', required=True)
    ap.add_argument('--checks-json', required=True)
    ap.add_argument('--allowlist', default=str(DEFAULT_ALLOWLIST))
    a = ap.parse_args(argv)
    out = evaluate(a.repo, json.loads(Path(a.pr_json).read_text(encoding='utf-8')),
                   json.loads(Path(a.checks_json).read_text(encoding='utf-8')),
                   json.loads(Path(a.allowlist).read_text(encoding='utf-8')))
    print(json.dumps(out, indent=2))
    return {'GO': 0, 'STOP': 1, 'WAIT': 2}[out['verdict']]


if __name__ == '__main__':
    sys.exit(main())
