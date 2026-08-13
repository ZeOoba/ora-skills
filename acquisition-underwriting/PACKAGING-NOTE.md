# PACKAGING NOTE -- target-markets.json (do not delete; never bundled)

`target-markets.json` is NOT tracked in this directory, by design. `tools/package_skills.py`
injects it at package time from the single REPO-ROOT copy (`../target-markets.json`) via
SHARED_ROOT_DEPS (2026-07-09). Four consumer skills share it: acquisition-underwriting,
daily-brief, deal-comparison, market-monitor. (rent-comp was a fifth until it was retired
2026-08-05; its SHARED_ROOT_DEPS entry was removed 2026-08-12 in 171dc8a.)

Rules:
1. Do NOT copy target-markets.json into this directory -- it creates a duplicate zip entry
   at package time (2026-07-16 incident: false-missing-file alarm led to exactly that).
2. Edit ONLY the repo-root copy; the runtime-cache copy is a read-only mirror. Any edit to the root copy MUST bump its `version` and `updated` fields (enforced by the repo pre-commit hook, tools/hooks/pre-commit, 2026-07-16).
3. This note file is excluded from packaging by package_skills.py and must stay named
   PACKAGING-NOTE.md for that exclusion to hold.
