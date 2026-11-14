#!/usr/bin/env python3
"""Per-skill reimport claims: ONE session logs a Save-skill reimport.

WHY (2026-11-13): the 13-skill RCT re-upload was verified and logged by TWO sessions -- the
installing session wrote a combined event-log entry while the session that built the
packages ran per-skill `postclick` on the same installs, so event_log.md recorded 13
installs twice. Nothing told either session the other was mid-reimport.

HOW: the INSTALLING session claims `reimport-<skill>` when it runs
`reimport_correlate.py precheck` -- precheck is, by definition, run by whoever is about to
put the package in front of Gabriel's Save-skill click. Before LOGGING an install
(`postclick` append, `reimport_cycle.py close`) a session checks the claim and STOPS when
another session holds it; after its own append it releases its claim.

`precheck` TAKES OVER a claim another session holds, recording the displaced claim in
claim_work's own `prior_claim` / `prior_claim_reason="force"` fields, and warns. It never
fails: the documented handoff (one session builds, another installs; 2026-11-13 exactly) must
not be blocked, and a builder holding the claim would otherwise wedge the installer
(merge-gate review of PR #260, finding 1). `reimport_cycle.py prep` does not claim, for the
same reason. Net effect either way: whichever session ran precheck last owns the log, and the
other session's postclick / close refuses to write a second entry.

Ownership is claim_work's: a live claim whose session id differs from this session's. A
Desktop Commander bridge session carries no CLAUDE_CODE_SESSION_ID and is "unknown";
claim_work treats "unknown" as a real owner, so a bridge session's claim blocks a Code
session's log and the reverse. Two bridge sessions both read as "unknown" and cannot see
each other -- claim_work's own documented blind spot. Claims carry no `paths`, so they never
make shared-checkout-guard warn other sessions editing the skill.

FAIL-OPEN: when claim_work.py is not available (CI, a cloud sandbox with no ~/.claude) every
call is a no-op. A claim is a coordination signal, never a gate on a correct install.
Abandoned claim: python ~/.claude/hooks/lib/claim_work.py release reimport-<skill> --force
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

CLAIM_LIB = Path.home() / '.claude' / 'hooks' / 'lib'
SLUG_PREFIX = 'reimport-'
_UNLOADED = object()
_lib_cache = _UNLOADED


def load_lib():
    """claim_work, or None when it is not available. Loaded from its FILE, never by putting
    ~/.claude/hooks/lib on sys.path, so it cannot shadow a same-named module anywhere else in
    the process (PR #260 review finding 8). Cached per process."""
    global _lib_cache
    if _lib_cache is _UNLOADED:
        try:
            path = CLAIM_LIB / 'claim_work.py'
            spec = importlib.util.spec_from_file_location('_ora_claim_work', path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _lib_cache = mod
        except Exception:
            _lib_cache = None
    return _lib_cache


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
    # Never advise re-running precheck here: this message is printed by postclick/close,
    # i.e. AFTER the Save-skill click, and precheck would recapture the baseline at the new
    # install's CreationTime, so the next postclick could never CONFIRM it (PR #260
    # re-review finding A). Take the claim over WITHOUT touching the baseline instead.
    cw = CLAIM_LIB / 'claim_work.py'
    return (f'{skill}: reimport CLAIMED by session {c.get("session_id")}{host} {age_txt} '
            f'({c.get("description", "")}). That session ran precheck for this install and '
            f'logs it -- check with it before logging here. If it stopped and this session '
            f'should log the install, take the claim over (claim only; do NOT re-run precheck '
            f'after the click, it would reset the baseline) and re-run this command: python '
            f'"{cw}" claim {slug(skill)} "logging the install" --force')


def claim(skill: str, purpose: str, lib=None) -> str | None:
    """Claim this skill's reimport for this session, TAKING OVER another session's claim
    (recorded as prior_claim, reason "force"). Returns a takeover notice to print as a
    warning, or None. Never blocks; fail-open when claim_work is unavailable."""
    lib = lib if lib is not None else load_lib()
    if lib is None:
        return None
    try:
        c = lib.find_claim(slug(skill))
        foreign = bool(c) and _foreign(lib, c)
        lib.write_claim(slug(skill), lib.own_session_id(), purpose,
                        title=f'reimport {skill}', cwd=os.getcwd(), paths=[],
                        host_session_id=lib.own_host_session_id(),
                        prior_claim=c if foreign else None,
                        prior_claim_reason='force' if foreign else None)
        if foreign:
            return (f'reimport claim TAKEN OVER from session {c.get("session_id")} '
                    f'({c.get("description", "")}); this session now logs {skill}, and that '
                    f'session\'s postclick/close will refuse to log it')
    except Exception as exc:  # a claim hiccup must not block a correct install
        return f'reimport claim for {skill} not written ({type(exc).__name__}: {exc})'
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
