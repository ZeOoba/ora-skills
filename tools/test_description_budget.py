"""Tests for description_budget.extract_description.

Written 2026-09-06 alongside the block-scalar fix (Automation Audit R23-6). The tool
had no tests, which is exactly how a regex that silently reported `description: >`
as 1 character survived long enough to pass a 1,306-char description as `ok` with
1,023 chars of headroom.

Run: python tools/test_description_budget.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from description_budget import extract_description  # noqa: E402

FAILURES = []


def check(label, got, want):
    if got == want:
        print("  ok   %s" % label)
    else:
        print("  FAIL %s\n       got  %r\n       want %r" % (label, got, want))
        FAILURES.append(label)


# --- inline form: the case that always worked, guarded against regression ---
check(
    "inline plain",
    extract_description("name: x\ndescription: Use when a thing happens.\n"),
    "Use when a thing happens.",
)
check(
    "inline double-quoted",
    extract_description('name: x\ndescription: "Use when quoted."\n'),
    "Use when quoted.",
)

# --- folded block: joins with spaces, which is what YAML does and what the
#     importer therefore measures ---
check(
    "folded joins with spaces",
    extract_description("name: x\ndescription: >\n  first line\n  second line\n"),
    "first line second line",
)
check(
    "folded is not reported as 1 char (the actual bug)",
    len(extract_description("name: x\ndescription: >\n  %s\n" % ("a" * 60))),
    60,
)

# --- literal block: preserves newlines, so its length differs from folded ---
check(
    "literal preserves newlines",
    extract_description("name: x\ndescription: |\n  line one\n  line two\n"),
    "line one\nline two",
)

# --- the block must stop at the next top-level key, not swallow it ---
check(
    "block stops at sibling key",
    extract_description("name: x\ndescription: >\n  only this\nversion: 2\n"),
    "only this",
)

# --- chomping indicators (>- , |+ , >2) must not break the match ---
check(
    "folded with chomping indicator",
    extract_description("name: x\ndescription: >-\n  kept\n"),
    "kept",
)

# --- blank line inside a folded block is a paragraph break, not a terminator ---
check(
    "blank line inside folded block",
    extract_description("name: x\ndescription: >\n  para one\n\n  para two\n"),
    "para one para two",
)

# --- absent key ---
check("no description key", extract_description("name: x\nversion: 1\n"), None)

# --- regression guard on the real shape that caused the incident ---
_real = "name: county-parcel-screen\ndescription: >\n" + "".join(
    "  %s\n" % ("word " * 20) for _ in range(8)
)
_got = extract_description(_real)
check("multi-line folded length is summed, not 1", len(_got) > 700, True)

print()
if FAILURES:
    print("FAILED: %d of the checks above" % len(FAILURES))
    sys.exit(1)
print("all checks passed")
