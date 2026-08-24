## 2026-08-22 -- Save-skill click confirmed: model-bulk-edit v1.1 (memory-defect fix)

Fourth and final install of the refi-rate-rebase session. Confirmed on the full evidence
chain, the cleanest of the four:

- Cache directory CreationTime moved 20:41:28 (v1.0) -> **2026-08-22 20:55:26**.
- Local `main.log` shows `Sync complete: 1 downloaded, 0 failed` at **exactly 20:55:26** --
  an exact-second match to the CreationTime move. First-hand, skill-specific proof per the
  v1.24 correlation rule; rules out the mirror-sync-hook explanation entirely.
- 2 files in cache, matching the packaged .skill's 2 entries, INCLUDING
  `scripts/cached_value_lint.py` -- the subfolder survived, reconfirming the Cowork install
  path handles multi-file packages correctly.
- Cached script carries 3 occurrences of `read_only=True`; cached SKILL.md carries the v1.1
  changelog entry at line 144.
- SHA256 of the cached script vs the repo copy, CRLF->LF normalized: **MATCH**
  (13870e9333cd84f8...).

PENDING_REIMPORT line cleared.

**What v1.1 fixed, recorded because it was a defect this session shipped and then had to
repair on the same machine it broke.** v1.0's `cached_value_lint.py` opened each workbook
twice in openpyxl's default full-object-tree mode and held both trees. Run across the
Business tree it reached 9.1 GB RSS, exhausted the paging file, and caused an unrelated
PowerShell invocation to fail with `0x800705AF`; the process was killed by PID (40816).
v1.1 passes `read_only=True` on both loads and streams the sheets in lockstep via `zip()`
with a per-file `gc.collect()`: measured peak 48 MB, ~190x reduction. The lesson worth
carrying: a read-only audit script is not automatically a safe script, and "it only reads"
is not a resource argument.

**STILL OPEN after this session, both recorded so nothing reads as finished that isn't:**

1. **The portfolio-wide cached-value sweep has never completed.** v1.1 is verified working
   at small scale but has not been run to completion over `Business`. The only DEAD finding
   on record remains `ORA_UnderwritingModel_125DouglasPike_v2.0.xlsx` (nulls at Returns!B37
   and Sensitivity!B17, since repaired by the Excel COM rebase). Nothing else is audited.
   Run from a plain terminal, not a detached launcher:
   `python "C:\Users\Owner\ora-skills\model-bulk-edit\scripts\cached_value_lint.py" "C:\Users\Owner\OneDrive - Oxford Capital Partners\Business" --quiet`
   Sanity-check the reported workbook count before trusting the verdict -- an argument-
   quoting error silently walks the wrong root and prints a confident tiny number.

2. **Duplicate `acquisition-underwriting` registration is UNRESOLVED and still firing.**
   As of 20:55:52 the desktop app is still logging, on every sync:
   `[warn] [SkillsPlugin] Remote skill "acquisition-underwriting" maps to the same directory
   as an earlier remote skill, skipping`
   Two enabled registrations exist (skill_012DJmjQBkLtQtfu6We1owXx and
   skill_01Ukeyw2g9c99nVdsSpnTiyr); one is skipped every time. Needs manual removal in
   Settings -> Capabilities -- a session cannot delete a registry entry.
