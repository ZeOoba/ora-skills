"""Lint + fixer: dollar-sign-followed-by-digit in SKILL.md bodies.

Why: when a skill is invoked WITH arguments, the skill loader replaces positional placeholders (a dollar
sign followed by digits) in the skill body with the whitespace-split argument tokens, so a figure such as
"4.00/SF" written with a leading dollar sign is replaced by the 4th argument word ("<street-name>.00/SF",
a Grand Rapids-area underwrite, 2026-11-14). Reference files are not substituted; only SKILL.md bodies.

Usage:
  python tools/lint_skill_dollar_args.py <skills_root>            # report, exit 1 if any hit
  python tools/lint_skill_dollar_args.py <skills_root> --fix      # rewrite in place, then re-lint
  python tools/lint_skill_dollar_args.py <skills_root> --fix --dry-run   # print the diff only

Fix rule: a dollar sign followed by a digit becomes "USD " + the number ("USD 4.00/SF", "USD 2,450,000",
"USD 1.25M"). Fenced code blocks (``` ... ```) and inline code spans are left alone in report mode too:
they are flagged separately as WARN because the loader still substitutes inside them.
"""
from __future__ import annotations
import argparse, difflib, re, sys
from pathlib import Path

PAT = re.compile(r"\$(\d)")
# Rewritable: a money figure, i.e. not part of a spreadsheet reference like $B$5 or a code span.
MONEY = re.compile(r"(?<![A-Za-z$])\$(\d)")
INLINE = re.compile(r"(`[^`\n]*`)")
VENDOR_SKILLS: set = set()  # every top-level skill in this repo is ORA-owned; _archive/ is not scanned


def split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            end = text.index("\n", end + 4) + 1 if "\n" in text[end + 4:] else len(text)
            return text[:end], text[end:]
    return "", text


def fix_body(body: str) -> str:
    out, in_fence = [], False
    for line in body.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        parts = INLINE.split(line)  # odd indexes are inline code spans: left alone (WARN)
        out.append("".join(pt if i % 2 else MONEY.sub(r"USD \1", pt) for i, pt in enumerate(parts)))
    return "".join(out)


def scan(root: Path):
    hits = {}
    for p in sorted(root.glob("*/SKILL.md")):
        if p.parent.name in VENDOR_SKILLS:
            continue
        fm, body = split_frontmatter(p.read_text(encoding="utf-8"))
        n_body = len(PAT.findall(body))
        n_fm = len(PAT.findall(fm))
        if n_body or n_fm:
            hits[p] = (n_body, n_fm)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    root = Path(a.root)
    hits = scan(root)
    if a.fix:
        for p in hits:
            raw = p.read_bytes().decode("utf-8")
            fm, body = split_frontmatter(raw)
            new = fm + fix_body(body)
            if new == raw:
                continue
            if a.dry_run:
                sys.stdout.writelines(difflib.unified_diff(raw.splitlines(True), new.splitlines(True),
                                                           str(p), str(p), n=0))
            else:
                p.write_bytes(new.encode("utf-8"))
        if not a.dry_run:
            hits = scan(root)
    total = sum(b for b, _ in hits.values())
    # After --fix, what remains is code (fences, inline spans, $B$5-style references): report as WARN, exit 0
    # unless a rewritable money figure is still present.
    money_left = 0
    for p in hits:
        fm, body = split_frontmatter(p.read_text(encoding="utf-8"))
        if fix_body(body) != body:
            money_left += 1
    for p, (b, f) in hits.items():
        fm, body = split_frontmatter(p.read_text(encoding="utf-8"))
        tag = "FAIL" if fix_body(body) != body else "WARN(code-only)"
        print(f"{tag} {p}: {b} in body, {f} in frontmatter")
    print(f"{len(hits)} files, {total} body occurrences, {money_left} files with rewritable money figures")
    return 1 if money_left else 0


if __name__ == "__main__":
    sys.exit(main())
