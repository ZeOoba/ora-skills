#!/usr/bin/env python3
"""script_resource_lint.py -- flag memory-hazard patterns in packaged skill scripts.

Why this exists: on 2026-08-22 a freshly written, freshly reviewed skill script
(model-bulk-edit v1.0 `cached_value_lint.py`) passed every gate ORA has -- frontmatter
validation, packager entry checks, a syntax check, and a live self-test -- and then
consumed 9.1 GB RSS on its first real run, exhausted the machine's paging file, and made
an unrelated PowerShell call fail with 0x800705AF.

None of the existing gates look at resource behaviour, because "it only reads files" is
not a resource argument. This one does. It is deliberately a SMALL set of high-confidence
patterns rather than a general analyzer -- a linter nobody trusts gets ignored.

Findings are ADVISORY. A flagged line with a deliberate justification is fine; add
`# resource-ok: <reason>` on the same line to silence it, which forces the reason to be
written down rather than merely held in someone's head.

Usage:
  python tools/script_resource_lint.py                  # every skill's scripts/
  python tools/script_resource_lint.py <skill> [...]
Exit: 0 = clean, 1 = at least one unsilenced finding.
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (regex, message) -- each must be specific enough to almost never fire spuriously.
RULES = [
    (re.compile(r"load_workbook\s*\((?![^)]*read_only\s*=\s*True)[^)]*\)", re.S),
     "openpyxl.load_workbook() without read_only=True builds the full object tree in "
     "memory. Over a directory sweep this is the 9.1 GB failure (model-bulk-edit v1.0). "
     "Use read_only=True and stream; add wb.close() in a finally."),
    (re.compile(r"\.read\(\)\s*$|\.read\(\)\s*\)"),
     "whole-file .read() -- fine for a config, a memory hazard for a document or data "
     "file of unknown size. Prefer streaming/chunked reads inside a walk."),
    (re.compile(r"\bglob\.glob\([^)]*\*\*[^)]*recursive\s*=\s*True[^)]*\)|os\.walk\([^)]*\)\s*\]"),
     "recursive walk materialised into a list -- hold the generator instead when the "
     "tree is large or of unknown size."),
    (re.compile(r"pd\.read_(excel|csv)\s*\((?![^)]*(chunksize|nrows|usecols))[^)]*\)", re.S),
     "pandas read of an entire file with no chunksize/nrows/usecols bound."),
    (re.compile(r"Start-Process[^\n]*-ArgumentList\s*@\("),
     "PowerShell Start-Process -ArgumentList with an ARRAY splits arguments on spaces. "
     "Every ORA root path contains spaces, so the script silently runs against the wrong "
     "directory and reports a confident, wrong result. Build one quoted string instead."),
]

SILENCE = re.compile(r"#\s*resource-ok\s*:", re.I)
EXTS = (".py", ".ps1")


def _blank_noncode(text, path):
    """Blank out comments and string literals, preserving line numbers.

    Without this the linter matches its OWN docstring: model-bulk-edit's
    cached_value_lint.py explains the load_workbook hazard in prose at line 5 and was
    duly flagged for it (2026-08-22). A linter that cannot tell code from commentary
    trains people to ignore it.
    """
    if path.endswith(".ps1"):
        return re.sub(r"#[^\n]*", "", text)
    try:
        import io, tokenize
        out = list(text)
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type not in (tokenize.STRING, tokenize.COMMENT):
                continue
            (sr, sc), (er, ec) = tok.start, tok.end
            lines = text.splitlines(keepends=True)
            base = sum(len(l) for l in lines[:sr - 1])
            start = base + sc
            end = sum(len(l) for l in lines[:er - 1]) + ec
            for i in range(start, min(end, len(out))):
                if out[i] != "\n":
                    out[i] = " "
        return "".join(out)
    except Exception:
        return text  # tokenize failed (syntax error) -- scan raw rather than skip


def scan(path):
    out = []
    try:
        text = open(path, encoding="utf8", errors="replace").read()
    except Exception as e:
        return [(0, f"UNREADABLE {type(e).__name__}: {e}"[:100])]
    lines = text.splitlines()
    text = _blank_noncode(text, path)
    for rx, msg in RULES:
        for m in rx.finditer(text):
            ln = text[:m.start()].count("\n")
            if ln < len(lines) and SILENCE.search(lines[ln]):
                continue
            out.append((ln + 1, msg))
    return out


def targets(argv):
    if argv:
        return argv
    return [e for e in sorted(os.listdir(ROOT))
            if not e.startswith((".", "_")) and os.path.isdir(os.path.join(ROOT, e, "scripts"))]


def main(argv):
    findings = 0
    for skill in targets(argv[1:]):
        sdir = os.path.join(ROOT, skill, "scripts")
        if not os.path.isdir(sdir):
            continue
        for dirpath, _, files in os.walk(sdir):
            for fn in sorted(files):
                if not fn.endswith(EXTS):
                    continue
                p = os.path.join(dirpath, fn)
                for ln, msg in scan(p):
                    rel = os.path.relpath(p, ROOT).replace("\\", "/")
                    print(f"{rel}:{ln}\n    {msg}\n")
                    findings += 1
    print(f"{findings} finding(s). Advisory -- silence a deliberate one with "
          f"'# resource-ok: <reason>' on the flagged line.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
