#!/usr/bin/env python3
"""Per-skill reimport claims: one session owns a Save-skill reimport from pre-check to log.

WHY (2026-11-13): the 13-skill RCT re-upload was verified and logged by TWO sessions -- the
installing session wrote a combined event-log entry while the session that built the
packages ran per-skill `postclick` on the same installs, so event_log.md recorded 13
installs twice, and a third session separately took on parcel-data-recovery. Nothing told
either session the other was mid-reimport.

HOW: the session that starts a reimport claims `reimport-<skill>` through the shared
cross-session primitive (~/.claude/hooks/lib/claim_work.py, the same claims every
shared-checkout guard reads), at `reimport_correlate.py precheck` (Entry point B) or
`reimport_cycle.py prep` (Entry point A). Before LOGGING an install (`postclick` append,
`reimport_cycle.py close`), a session checks the claim and STOPS when another session holds
it -- that session verifies and logs. After its own append the session releases its claim.

Ownership is claim_work's: a live claim whose session id differs from this session's.
A Desktop Commander bridge session carries no CLAUDE_CODE_SESSION_ID and is "unknown";
claim_work treats "unknown" as a real owner, so a bridge session's claim does block a Code
session and the reverse (today's exact collision). Two bridge sessions both read as
"unknown" and cannot see each other -- claim_work's own documented blind spot.

FAIL-OPEN: when claim_work.py is not importable (CI, a cloud sandbox with no ~/.claude) every
call is a no-op returning "no blocker". A claim is a coordination signal, never a gate on a
correct install. Override for an abandoned claim:
    python ~/.claude/hooks/lib/claim_work.py release reimport-<skill> --force
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

CLAIM_LIB = Path.home() / '.claude' / 'hooks' / 'lib'
SLUG_PREFIX = 'reimport-'
REPO = Path(__file__).resolve().parent.parent


def load_lib():
    """claim_work, or None when it is not available on this machine."""
    try:
        if str(CLAIM_LIB) not in sys.path:
            sys.path.insert(0, str(CLAIM_LIB))
        return importlib.import_module('claim_work')
    except Exception:
        return None


def slug(skill: str) -> str:
    return f'{SLUG_PREFIX}{skill}'


def _foreign(lib, c) -> bool:
    sid = lib.attributable_session(c)
    return sid is not None and sid != lib.own_session_id()


def foreign_holder(skill: str, lib=None):
    """The live claim on this skill's reimport held by ANOTHER session, or None."""
    lib = lib if lib is not None else load_lib()
    if lib is None:
        return None
    try:
        c = lib.find_claim(slug(skill))
    except Exception:
        return None
    return c if c and _foreign(lib, c) else None


def describe(skill: str, c) -> str:
    age = c.get('age_minutes')
    age_txt = f'{age:.0f} min ago' if isinstance(age, (int, float)) else 'at an unknown time'
    host = f', host {c["host_session_id"]}' if c.get('host_session_id') else ''
    return (f'{skill}: reimport CLAIMED by session {c.get("session_id")}{host} {age_txt} '
            f'({c.get("description", "")}). That session verifies and logs this install. '
            f'Coordinate with it; if it is finished or abandoned: python '
            f'"{CLAIM_LIB / "claim_work.py"}" release {slug(skill)} --force')


def claim(skill: str, purpose: str, lib=None) -> str | None:
    """Claim (or renew our own claim on) this skill's reimport. Returns a blocker message
    when another session holds it, else None. Fail-open when claim_work is unavailable."""
    lib = lib if lib is not None else load_lib()
    if lib is None:
        return None
    try:
        c = lib.find_claim(slug(skill))
        if c and _foreign(lib, c):
            return describe(skill, c)
        lib.write_claim(slug(skill), lib.own_session_id(), purpose,
                        title=f'reimport {skill}', cwd=os.getcwd(),
                        paths=[str(REPO / skill)], host_session_id=lib.own_host_session_id())
    except Exception as exc:  # a claim hiccup must not block a correct install
        print(f'NOTE: reimport claim for {skill} not written ({type(exc).__name__}: {exc})')
    return None


def release(skill: str, lib=None) -> bool:
    """Release this session's claim on the skill's reimport; never another session's."""
    lib = lib if lib is not None else load_lib()
    if lib is None:
        return False
    try:
        c = lib.find_claim(slug(skill))
        if not c or _foreign(lib, c):
            return False
        return bool(lib.release_claim(slug(skill)))
    except Exception:
        return False
