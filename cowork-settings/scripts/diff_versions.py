#!/usr/bin/env python3
"""
diff_versions.py — emit a sectioned changelog between two ORA Cowork Global
Settings versions.

Usage:
    python diff_versions.py <old_version.md> <new_version.md> [--out OUT.md]

Design:
    The settings block is organized by '# SECTION' headers. The diff operates
    at section granularity, then line granularity within each section, so the
    output reads like a governance changelog rather than a raw unified diff.
"""

import argparse
import difflib
import re
import sys
from datetime import date
from pathlib import Path

TIER_0_INVARIANTS = [
    r'"Ze"|"Ze Ooba"',
    r'ggoldberg@oxfordra\.net',
    r'egoldberg@oxfordra\.net',
    r'extractable text layer',
    r'Microsoft Print to PDF',
    r'netlify deploy --prod',
    r'YYYYMMDD_\[',
]


def extract_settings_block(md_text: str) -> str:
    """Pull the fenced settings code block out of the governance markdown."""
    m = re.search(r"```\n(# IDENTITY.*?)```", md_text, re.DOTALL)
    return m.group(1) if m else md_text


def split_by_section(block: str) -> dict[str, list[str]]:
    """Split the settings block into {section_name: [lines]}."""
    sections: dict[str, list[str]] = {}
    current = "PREAMBLE"
    sections[current] = []
    for line in block.splitlines():
        if line.startswith("# "):
            current = line.lstrip("# ").strip()
            sections[current] = []
        else:
            sections[current].append(line)
    return sections


def diff_sections(old: dict, new: dict) -> list[dict]:
    """Per-section categorized diff."""
    all_sections = list(dict.fromkeys(list(old) + list(new)))
    out = []
    for s in all_sections:
        if s not in old:
            out.append({"section": s, "kind": "ADDED",
                        "added": new[s], "removed": [], "unified": ""})
            continue
        if s not in new:
            out.append({"section": s, "kind": "REMOVED",
                        "added": [], "removed": old[s], "unified": ""})
            continue
        if old[s] == new[s]:
            continue
        matcher = difflib.SequenceMatcher(a=old[s], b=new[s])
        added, removed = [], []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ("replace", "delete"):
                removed += [ln for ln in old[s][i1:i2] if ln.strip()]
            if tag in ("replace", "insert"):
                added += [ln for ln in new[s][j1:j2] if ln.strip()]
        unified = "\n".join(difflib.unified_diff(
            old[s], new[s], fromfile=f"{s} (old)", tofile=f"{s} (new)",
            lineterm=""))
        out.append({"section": s, "kind": "MODIFIED",
                    "added": added, "removed": removed, "unified": unified})
    return out


def tier0_violations(new_block: str) -> list[str]:
    """Detect any Tier-0 invariant that has disappeared from the new version.

    A concept is considered preserved if its pattern appears ANYWHERE in the
    new settings block (even reworded). A concept is violated only if it has
    genuinely disappeared.
    """
    missing = []
    for pat in TIER_0_INVARIANTS:
        if not re.search(pat, new_block):
            missing.append(pat)
    return missing


def format_changelog(old_path: Path, new_path: Path,
                     diffs: list[dict], new_block: str) -> str:
    header = f"""# ORA Cowork Global Settings — Changelog

**From:** `{old_path.name}`
**To:** `{new_path.name}`
**Generated:** {date.today().isoformat()}
**Scope:** Section-level diff with Tier-0 invariant audit.

---

"""
    if not diffs:
        return header + "*No substantive changes.*\n"

    body_parts = []

    for d in diffs:
        if d["kind"] == "ADDED":
            body_parts.append(f"## ➕ Section added — `{d['section']}`\n")
            body_parts.append("```\n" + "\n".join(d["added"]).strip() + "\n```\n")
        elif d["kind"] == "REMOVED":
            body_parts.append(f"## ❌ Section removed — `{d['section']}`\n")
            body_parts.append("```\n" + "\n".join(d["removed"]).strip() + "\n```\n")
        else:  # MODIFIED
            body_parts.append(f"## ✎ Section modified — `{d['section']}`\n")
            if d["added"]:
                body_parts.append("**Added lines:**\n")
                body_parts.append("```\n" + "\n".join(d["added"]).strip() + "\n```\n")
            if d["removed"]:
                body_parts.append("**Removed lines:**\n")
                body_parts.append("```\n" + "\n".join(d["removed"]).strip() + "\n```\n")
            body_parts.append("<details><summary>Unified diff</summary>\n\n```diff\n"
                              + d["unified"] + "\n```\n</details>\n")

    missing = tier0_violations(new_block)
    audit = "\n## Tier-0 Invariant Audit\n\n"
    if missing:
        audit += ("**⚠ BREAKING:** the following Tier-0 invariants no longer "
                  "appear in the new version (in any form):\n\n")
        for v in sorted(set(missing)):
            audit += f"- `{v}`\n"
        audit += ("\n**Action required:** confirm major-version bump and "
                  "document rationale. Do not publish until confirmed.\n")
    else:
        audit += "✓ All Tier-0 invariants preserved in the new version.\n"

    footer = ("\n---\n\n"
              "*Generated by `cowork-settings` skill · "
              "`scripts/diff_versions.py`*\n")
    return header + "\n".join(body_parts) + audit + footer


def main():
    p = argparse.ArgumentParser()
    p.add_argument("old")
    p.add_argument("new")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    old_path = Path(args.old)
    new_path = Path(args.new)
    old_block = extract_settings_block(old_path.read_text(encoding="utf-8"))
    new_block = extract_settings_block(new_path.read_text(encoding="utf-8"))

    diffs = diff_sections(
        split_by_section(old_block),
        split_by_section(new_block),
    )

    changelog = format_changelog(old_path, new_path, diffs, new_block)

    if args.out:
        Path(args.out).write_text(changelog, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        sys.stdout.write(changelog)


if __name__ == "__main__":
    main()
