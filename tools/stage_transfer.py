#!/usr/bin/env python3
"""stage_transfer.py - one-call hash gate for pre-built .skill handoffs.

WHY THIS EXISTS (2026-09-28, census-v19 install): the expected-hash verify in
package-and-stage-skill v1.34 (host hash -> staged hash -> outputs hash) cost
5-6 separate tool calls. `device_stage_files` can only be called by the
session, so the chain cannot be one script -- but everything either side of it
can. Two modes, one per side of that call:

  emit    HOST side (device_bash / Code shell), in the handoff folder:
              python tools/stage_transfer.py emit <handoff-dir>
          Hashes every *.skill in the folder, checks each zip (forward-slash
          entries, no directory records, <skill>/SKILL.md present) and writes
          HANDOFF.sha256.json beside them. The prefixes a receiving session
          checks come from this manifest, not from anyone re-typing digests.

  receive CLOUD side (Bash), after ONE device_stage_files call:
              python tools/stage_transfer.py receive --staged-dir DIR \
                  [--manifest FILE | --expect name=prefix ...] [--outputs DIR]
          Re-hashes the staged copies against the manifest/prefixes, checks
          the zip entries again, and ONLY IF EVERY FILE PASSES copies them to
          the outputs dir and re-hashes the copies. All-or-nothing: any
          mismatch or invisible file copies nothing, exits 1, and reports the
          exact path searched plus stated-vs-actual digests. It never
          substitutes another file; .skill files in the staged dir that were
          not named are listed as UNUSED, never picked up.

A hash proves the package is the one the sender built. It does NOT prove the
package still matches the repo -- run tools/entry_b_precheck.py /
reimport_correlate.py precheck for that. Neither substitutes for the other.

Stdlib only. Exit 0 = all PASS, 1 = any FAIL, 2 = usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_NAME = "HANDOFF.sha256.json"
DEFAULT_OUTPUTS = "/mnt/user-data/outputs"
MIN_PREFIX = 12  # hex chars; the census-v19 handoff used 16


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _raw_names(path: Path) -> list[str]:
    """Entry names exactly as stored in the central directory.

    zipfile rewrites os.sep to '/' on Windows (on write AND read), so
    ZipFile.namelist() can never show a backslash entry there -- the very
    platform emit runs on and where Compress-Archive writes them. Reading the
    central directory directly keeps the backslash check honest on every OS.
    Zip64 is not handled (a skill package is far below 4 GiB); [] = unparsed.
    """
    data = path.read_bytes()
    eocd = data.rfind(b"PK\x05\x06")
    if eocd < 0:
        return []
    total, _size, offset = struct.unpack("<HII", data[eocd + 10:eocd + 20])
    names, p = [], offset
    for _ in range(total):
        if data[p:p + 4] != b"PK\x01\x02":
            return []
        n, m, k = struct.unpack("<HHH", data[p + 28:p + 34])
        names.append(data[p + 46:p + 46 + n].decode("utf-8", "replace"))
        p += 46 + n + m + k
    return names


def zip_problems(path: Path) -> list[str]:
    """Structural checks the importer enforces silently. Empty list = OK."""
    problems: list[str] = []
    try:
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
            if bad:
                problems.append(f"corrupt entry: {bad}")
            names = zf.namelist()
    except zipfile.BadZipFile as exc:
        return [f"not a valid zip: {exc}"]
    except Exception as exc:  # zlib.error, encrypted, unsupported method ...
        return [f"unreadable archive: {type(exc).__name__}: {exc}"]
    raw = _raw_names(path)
    if len(raw) == len(names):
        names = raw
    if not names:
        return ["empty archive"]
    for n in names:
        segs = n.replace("\\", "/").split("/")
        if n.startswith(("/", "\\")) or ":" in segs[0] or ".." in segs or "." in segs:
            problems.append(f"unsafe entry path: {n}")
            break
    if any("\\" in n for n in names):
        problems.append("backslash in entry path (importer rejects)")
    if any(n.endswith("/") for n in names):
        problems.append("directory record present")
    tops = {n.split("/", 1)[0] for n in names}
    if len(tops) != 1:
        problems.append(f"expected one top-level dir, found {sorted(tops)}")
    else:
        top = next(iter(tops))
        if f"{top}/SKILL.md" not in names:
            problems.append(f"{top}/SKILL.md missing")
    return problems


def _normalise_prefix(prefix: str) -> str | None:
    p = prefix.strip().lower()
    if len(p) < MIN_PREFIX or any(c not in "0123456789abcdef" for c in p):
        return None
    return p


# ---------------------------------------------------------------- emit ----
def cmd_emit(args: argparse.Namespace) -> int:
    d = Path(args.dir)
    if not d.is_dir():
        print(f"FAIL  not a directory: {d}")
        return 1
    files = sorted(d.glob("*.skill"))
    if not files:
        print(f"FAIL  no .skill files in {d}")
        return 1
    entries, failed = [], False
    for f in files:
        digest = sha256_file(f)
        probs = zip_problems(f)
        failed |= bool(probs)
        entries.append({
            "name": f.name,
            "sha256": digest,
            "prefix16": digest[:16],
            "bytes": f.stat().st_size,
            "zip_ok": not probs,
        })
        status = "OK  " if not probs else "FAIL"
        print(f"{status}  {f.name}  {digest[:16]}  {f.stat().st_size} B"
              + ("" if not probs else "  -> " + "; ".join(probs)))
    manifest = {
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "folder": str(d),
        "files": entries,
    }
    out = Path(args.out) if args.out else d / MANIFEST_NAME
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 1 if failed else 0


# ------------------------------------------------------------- receive ----
def _expected(args: argparse.Namespace) -> dict[str, str] | None:
    exp: dict[str, str] = {}
    if args.manifest:
        try:
            data = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
            pairs = [(e["name"], e["sha256"]) for e in data["files"]]
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            print(f"FAIL  cannot read manifest {args.manifest}: {type(exc).__name__}: {exc}")
            return None
        for name, digest in pairs:
            if not isinstance(name, str):
                print(f"FAIL  name must be a bare file name, got {name!r}")
                return None
            exp[name] = digest if isinstance(digest, str) else ""
    for item in args.expect or []:
        name, sep, prefix = item.partition("=")
        if not sep or not name:
            print(f"FAIL  --expect wants name=prefix, got {item!r}")
            return None
        exp[name] = prefix
    for name, prefix in list(exp.items()):
        if not isinstance(name, str) or not name or Path(name).name != name \
                or "/" in name or "\\" in name or name in (".", ".."):
            print(f"FAIL  name must be a bare file name, got {name!r}")
            return None
        norm = _normalise_prefix(prefix)
        if norm is None:
            print(f"FAIL  digest for {name} must be >= {MIN_PREFIX} hex chars: {prefix!r}")
            return None
        exp[name] = norm
    if not exp:
        print("FAIL  nothing to verify: give --manifest and/or --expect name=prefix")
        return None
    if args.only:
        unknown = sorted(set(args.only) - set(exp))
        if unknown:
            print(f"FAIL  --only names not in the expected set: {unknown}")
            return None
        exp = {k: v for k, v in exp.items() if k in set(args.only)}
    return exp


def _drop(parts: list[Path]) -> None:
    for p in parts:
        try:
            p.unlink()
        except OSError:
            pass


def cmd_receive(args: argparse.Namespace) -> int:
    staged = Path(args.staged_dir)
    outputs = Path(args.outputs)
    exp = _expected(args)
    if exp is None:
        return 2
    print(f"searched: {staged}")

    results, ok = [], True
    for name, want in sorted(exp.items()):
        p = staged / name
        if not p.is_file():
            print(f"FAIL  {name}  not visible at {p}")
            results.append((name, None))
            ok = False
            continue
        got = sha256_file(p)
        if not got.startswith(want):
            print(f"FAIL  {name}  hash mismatch\n        stated {want}\n        actual {got}")
            ok = False
            results.append((name, None))
            continue
        probs = zip_problems(p)
        if probs:
            print(f"FAIL  {name}  hash OK but zip check failed: {'; '.join(probs)}")
            ok = False
            results.append((name, None))
            continue
        print(f"PASS  {name}  staged {got[:16]}  {p.stat().st_size} B  zip OK")
        results.append((name, got))

    unused = sorted(f.name for f in staged.glob("*.skill") if f.name not in exp) \
        if staged.is_dir() else []
    for u in unused:
        print(f"UNUSED  {u}  (in staged dir but not named -- ignored, never substituted)")

    if not ok:
        print("STOP  nothing copied to outputs. Do not substitute another file, "
              "repackage or install.")
        return 1

    # Two-phase so a failure never leaves a partial set in outputs: copy every
    # file to .part and hash each, and only then rename them into place.
    parts: list[Path] = []
    try:
        outputs.mkdir(parents=True, exist_ok=True)
        for name, want_full in results:
            tmp = outputs / (name + ".part")
            parts.append(tmp)
            shutil.copyfile(staged / name, tmp)
            got = sha256_file(tmp)
            if got != want_full:
                print(f"FAIL  {name}  outputs copy {got[:16]} != staged {want_full[:16]}")
                _drop(parts)
                return 1
        blocked = [n for n, _ in results if (outputs / n).is_dir()]
        if blocked:  # a rename that fails midway would strand a partial set
            print(f"FAIL  destination is a directory: {blocked}")
            _drop(parts)
            return 1
        for tmp, (name, want_full) in zip(parts, results):
            tmp.replace(outputs / name)
            print(f"PASS  {name}  outputs {want_full[:16]}  -> {outputs / name}")
    except OSError as exc:
        print(f"FAIL  copy to {outputs} failed: {exc}")
        _drop(parts)
        return 1
    print(f"ALL PASS  {len(results)} file(s) verified at staged + outputs. "
          "Next: repo-currency precheck, then present for Save skill.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("emit", help="host side: hash + zip-check a handoff folder")
    e.add_argument("dir")
    e.add_argument("--out", help=f"manifest path (default <dir>/{MANIFEST_NAME})")
    e.set_defaults(fn=cmd_emit)

    r = sub.add_parser("receive", help="cloud side: verify staged copies, copy to outputs")
    r.add_argument("--staged-dir", required=True)
    r.add_argument("--manifest")
    r.add_argument("--expect", action="append", metavar="NAME=PREFIX")
    r.add_argument("--only", action="append", metavar="NAME",
                   help="restrict to these names from the manifest")
    r.add_argument("--outputs", default=DEFAULT_OUTPUTS)
    r.set_defaults(fn=cmd_receive)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
