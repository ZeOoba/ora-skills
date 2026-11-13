# RCT replacement-cost table: private runtime file

The ratified RCT v03 table (Market · LOW · POINT · HIGH · C&W hard, per market) is governor-level data
(Hard Invariant 4). This repository is public, so the table is **not in source**. Before 2026-11-13 it sat in
`acquisition-underwriting/SKILL.md`, `parcel-data-recovery/SKILL.md`, `target-markets.json`, the walk solver
and several `_archive/` copies; those values remain in git history (no history rewrite was approved).

## Where it lives

| What | Where |
|---|---|
| Authoritative table, shared by every ORA repo (engine schema) | `~/.ora-private/rct/replacement-cost.json` (`$ORA_RCT_TABLE_PATH` overrides). Outside every repo and outside OneDrive. |
| The same figures in this repo's format | `~/.ora-private/rct/rct-table.local.json`, or the gitignored repo-root `rct-table.local.json` in a checkout, or `$ORA_RCT_TABLE` |
| What a skill reads at runtime | `rct-table.local.json` in the installed skill's own folder, beside SKILL.md |

`tools/package_skills.py` (`PRIVATE_LOCAL_DEPS`) copies the file into every skill that reads RCT values:
acquisition-underwriting, parcel-data-recovery, deal-comparison, loi-generation, listing-enrichment-gate,
county-parcel-screen and market-monitor. The same `skill_source_files()` feeds the `.skill` package (Cowork and
claude.ai), the plugin build, and the Code-surface mirror under `~/.claude/skills/`, so every surface gets
the same file. A stray copy inside a skill folder is never shipped (`is_bundled` excludes it).

## Shape

```text
{
  "rctVersion": "RCT v03",
  "ratified": "...", "source": "...",
  "markets": {
    "Columbus OH": { "label": "Columbus OH", "low": <n>, "point": <n>, "high": <n>, "cwHard": <n>, "cwNote": "" },
    ... one entry per market, in this order: Columbus OH, Cincinnati OH, Kansas City MO, Indianapolis IN,
    Madison WI, Mid-Atlantic, Grand Rapids MI, Richmond VA, Des Moines IA, Louisville KY, Chicago-Cook IL
  },
  "markdownTable": "| Market | LOW $/SF | POINT $/SF | HIGH $/SF | C&W hard (source) |\n|---|...|\n| ... |\n",
  "derivation": { "referenceSf": <int>, "softCostMultiplier": <n>, "escalation": <n>,
                  "softCostNote": "...", "escalationNote": "...", "sizePremiumNote": "...", "formula": "..." }
}
```

`markdownTable` is the ratified table exactly as it stood in SKILL.md, so an agent reads what it read before.
`derivation` holds the build parameters that acquisition-underwriting rule 11 needs to derive a PROVISIONAL row for
an off-table market. They are private too, because the public C&W small/medium tiers plus these parameters rebuild
every row to the cent (adversarial review, 2026-11-13).
A complete synthetic example with invented figures: `acquisition-underwriting/scripts/fixtures/rct-table.synthetic.json`.

## Validation and fail-closed behaviour

`acquisition-underwriting/scripts/ora_walk/rct_table.py` refuses a table that is not JSON, has
`rctVersion` other than `RCT v03`, is the synthetic fixture, has a different market list or order, has a
figure outside 50 to 1,000 $/SF, has LOW/HIGH not equal to POINT ∓10% (±$0.02), or whose `markdownTable`
disagrees with its numbers.

- **Packaging** refuses (no partial `.skill`) when the file is missing or invalid, or when any LOW, POINT,
  HIGH or C&W hard figure does not tie to the authoritative `replacement-cost.json`, or when that file
  cannot be read. Error messages name markets and fields, never figures.
- **The walk solver** loads the table on every solve; without a valid file it raises
  `RctTableUnavailable` and the CLI exits 3 with no walk.
- **Every consuming SKILL.md** tells the agent to stop the basis test and report `RCT TABLE UNAVAILABLE`,
  never to substitute a figure.

## Tests and the leak test

- Tests use the synthetic fixture only. `rct_table.use(table)` (code only) is the one way to run the solver
  on it; the loader refuses it from a file or the environment.
- `tools/test_rct_public_leak.py` always runs structural checks (the file is gitignored and untracked, no
  tracked JSON is a non-synthetic RCT table, the solver has no literal table). Its value scan needs the real
  table locally (same resolution as the packager) and then fails if any LOW, POINT or HIGH figure appears in
  any tracked or untracked-not-ignored file. Without the table it skips and says why; CI has no table, so CI
  runs only the structural checks (an allowed skip in `tools/run_suite.sh`).
- Never commit a hash of a value, and never paste a real figure into a fixture, test, doc or changelog.

## Changing a value

The table is a governor constant: change it only on Gabriel's in-turn ratification. Then:

1. Update the authoritative `~/.ora-private/rct/replacement-cost.json` (the oxford-command-center engine
   reads the same file).
2. Update `~/.ora-private/rct/rct-table.local.json` to match, including `markdownTable`; bump `rctVersion`
   only together with `RCT_VERSION` in `rct_table.py` and the version the SKILL.md files cite (a PR).
3. Re-package and re-upload every skill listed above (`package-and-stage-skill`). Packaging refuses until
   step 2 ties to step 1.
