"""Lint + fixer: dollar-sign-followed-by-digit in SKILL.md bodies.

Why: when a skill is invoked WITH arguments, the skill loader replaces positional placeholders (a dollar
sign followed by digits) in the skill body with the whitespace-split argument tokens, so a figure such as
"4.00/SF" written with a leading dollar sign is replaced by the 4th argument word ("<street-name>.00/SF",
Pursuit P-08 (Grand Rapids-area) lease-up underwrite, 2026-11-14; the v4.14 Madison incident is the same mechanism). Reference
files are not substituted; only SKILL.md bodies.

Usage:
  python tools/lint_skill_dollar_args.py <skills_root>            # report, exit 1 if any hit
  python tools/lint_skill_dollar_args.py <skills_root> --fix      # rewrite in place, then re-lint
  python tools/lint_skill_dollar_args.py <skills_root> --fix --dry-run   # print the diff only
  python tools/lint_skill_dollar_args.py <skills_root> --fix --include-dirty  # also rewrite uncommitted files

--fix never rewrites a SKILL.md with uncommitted changes (another session's work in progress) unless
--include-dirty is given; it prints every file it rewrites or skips, and it refuses to write a file that
changed while it was being fixed. That re-check narrows but cannot close the window between the final
read and the atomic replace (no lock-free compare-and-swap exists on a plain file), so run --fix only on
files no other session is editing at that moment.

Fix rule: a dollar sign followed by a digit becomes "USD " + the number ("USD 4.00/SF", "USD 2,500,000",
"USD 1.25M"). Fenced code blocks (``` ... ```) and inline code spans are left alone: they are reported
separately as WARN(code-only) because the loader still substitutes inside them, and so are spreadsheet
references such as $B$5.
"""
from __future__ import annotations
import argparse, difflib, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

PAT = re.compile(r"\$(\d)")
# Rewritable: a money figure, i.e. not the row half of a spreadsheet reference and not inside code.
# A cell reference is 1-3 capital letters (not the tail of a longer word) right before the "$" that
# EITHER carry an absolute "$" of their own ($B$5, Inputs!$B$38), OR sit in formula context (=C$3,
# SUM(A$1, :B$9), OR start a range (B$2:B$9). Capitals in prose are money: "US$5M", "TI$4/SF",
# "NNN$8.08"; so is a figure glued to a word ("Amortizing$16,304.46", a collapsed table cell).
MONEY = re.compile(r"(?:(?<![A-Za-z0-9_])(A|C|NZ|HK|S)(?=\$))?\$(\d)")  # optional non-US prefix, group 1
CELL_COL_TAIL = re.compile(r"(?:^|(?P<ctx>[$=(:!,+*/^<>&-])|[^A-Za-z0-9_])[A-Z]{1,3}$")
RANGE_AFTER = re.compile(r"\d*:\$?[A-Z]{1,3}\$?\d")
ROW_RANGE = re.compile(r"\d+:\$\d")               # "$5:$9", an absolute whole-row range
# Non-US dollar prefixes glued to a figure ("A$5M") keep their own currency, never USD, unless the
# letters read as a spreadsheet column ("=SUM(A$1:A$9)").
CURRENCY_CODE = {"A": "AUD", "C": "CAD", "NZ": "NZD", "HK": "HKD", "S": "SGD"}
US_DOLLAR = re.compile(r"(?<![A-Za-z0-9_])US\$(?=\d)")
FENCE = re.compile(r"\s*(```|~~~)")
INLINE = re.compile(r"(?<!`)(`+)(?!`)[^\n]*?(?<!`)\1(?!`)")   # inline code span: a whole backtick run opens it
VENDOR_SKILLS = {"xlsx", "docx", "pdf", "pptx", "skill-creator", "mcp-builder", "frontend-design", "file-reading",
                 "pdf-reading", "product-self-knowledge", "deep-research", "docs", "google-workspace"}


def split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            end = text.index("\n", end + 4) + 1 if "\n" in text[end + 4:] else len(text)
            return text[:end], text[end:]
    return "", text


def _fix_prose(text: str) -> str:
    text = US_DOLLAR.sub("USD ", text)              # "US$5M" -> "USD 5M"

    def repl(m: re.Match) -> str:
        d = m.start(2) - 1                         # index of the "$"
        before = text[max(0, d - 5):d]
        if before.endswith("\\"):
            return m.group(0)                      # "\$5": an escaped dollar sign, left as written (WARN)
        if ROW_RANGE.match(text, d + 1) or (d >= 2 and text[d - 1] == ":"
                                           and re.search(r"\$\d+$", text[:d - 1])):
            return m.group(0)                      # "$5:$9" row range: a spreadsheet reference (WARN)
        col = CELL_COL_TAIL.search(before)
        ctx = col.group("ctx") if col else None
        # "$ = ! :" always mark a reference; "( , + - / ..." only inside a formula (an "=" earlier on the
        # line), since in prose they wrap money: "(TI$4/SF)", "LC/TI$4", "NNN-CAM$1.25".
        formula = ctx is not None and (ctx in "$=!:" or "=" in text[:d])
        if col and (formula or RANGE_AFTER.match(text, d + 1)):
            return m.group(0)                      # spreadsheet reference: leave it (WARN)
        if m.group(1):
            return f"{CURRENCY_CODE[m.group(1)]} {m.group(2)}"   # "A$5M" -> "AUD 5M"
        sep = " " if before[-1:].isalnum() else ""  # "Only$125" -> "Only USD 125"
        return f"{sep}USD {m.group(2)}"
    return MONEY.sub(repl, text)


def fix_body(body: str) -> str:
    out, fence = [], None                          # fence = the open marker (``` or ~~~), else None
    for line in body.splitlines(keepends=True):
        fm = FENCE.match(line)
        if fm and (fence is None or fm.group(1) == fence):
            fence = None if fence else fm.group(1)
            out.append(line)
            continue
        in_fence = fence is not None
        if in_fence:
            out.append(line)
            continue
        pos, buf = 0, []                           # inline code spans are left alone (WARN)
        for m in INLINE.finditer(line):
            buf += [_fix_prose(line[pos:m.start()]), m.group(0)]
            pos = m.end()
        buf.append(_fix_prose(line[pos:]))
        out.append("".join(buf))
    return "".join(out)


def _read(p: Path) -> str:
    return p.read_bytes().decode("utf-8")  # keep CRLF as-is so --fix never rewrites line endings


def scan(root: Path):
    hits = {}
    for p in sorted(root.glob("*/SKILL.md")):
        if p.parent.name in VENDOR_SKILLS:
            continue
        fm, body = split_frontmatter(_read(p))
        n_body = len(PAT.findall(body))
        n_fm = len(PAT.findall(fm))
        if n_body or n_fm:
            hits[p] = (n_body, n_fm)
    return hits


def _dirty(p: Path) -> bool:
    """True when git reports uncommitted changes to p (another session's work in progress). Outside a git
    checkout nothing is dirty."""
    try:
        # --no-optional-locks: a status here must never hold .git/index.lock and fail a concurrent `git add`.
        r = subprocess.run(["git", "--no-optional-locks", "status", "--porcelain", "--", p.name], cwd=p.parent,
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


def _write_if_unchanged(p: Path, raw: str, new: str) -> bool:
    """Write new only if p still holds raw (no concurrent writer); atomic replace. False when it changed."""
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".lintfix-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(new.encode("utf-8"))
        shutil.copymode(p, tmp)                    # keep the file's mode (mkstemp creates 0600)
        if _read(p) != raw:
            os.unlink(tmp)
            return False
        os.replace(tmp, p)
        return True
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-dirty", action="store_true",
                    help="with --fix, also rewrite SKILL.md files that have uncommitted changes")
    a = ap.parse_args(argv)
    root = Path(a.root)
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    hits = scan(root)
    if a.fix:
        for p in hits:
            raw = _read(p)
            fm, body = split_frontmatter(raw)
            new = fm + fix_body(body)
            if new == raw:
                continue
            if not a.include_dirty and _dirty(p):
                print(f"SKIPPED(uncommitted changes) {p}: commit it, or rerun with --include-dirty")
                continue
            if a.dry_run:
                sys.stdout.writelines(difflib.unified_diff(raw.splitlines(True), new.splitlines(True),
                                                           str(p), str(p), n=0))
            elif _write_if_unchanged(p, raw, new):
                print(f"FIXED {p}")
            else:
                print(f"SKIPPED(changed during fix) {p}: rerun --fix")
        if not a.dry_run:
            hits = scan(root)
    total = sum(b for b, _ in hits.values())
    # What remains after --fix is code (fences, inline spans, $B$5-style references) or frontmatter:
    # WARN, exit 0, unless a rewritable money figure is still present.
    money_left = 0
    for p, (b, f) in hits.items():
        fm, body = split_frontmatter(_read(p))
        rewritable = fix_body(body) != body
        money_left += rewritable
        tag = "FAIL" if rewritable else "WARN(code-only)"
        print(f"{tag} {p}: {b} in body, {f} in frontmatter")
    print(f"{len(hits)} files, {total} body occurrences, {money_left} files with rewritable money figures")
    return 1 if money_left else 0  # a skipped file still holds its rewritable figure, so it FAILs


if __name__ == "__main__":
    sys.exit(main())
