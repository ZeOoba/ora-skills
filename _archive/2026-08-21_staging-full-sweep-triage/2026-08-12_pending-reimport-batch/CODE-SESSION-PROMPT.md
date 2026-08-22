# Code-session prompt — 2026-08-12 retired-skill remediation + reimport close-out

Repo: `C:\Users\Owner\ora-skills` (HEAD at handoff: `0f5c23a`). Working tree had one unrelated dirty file at handoff: `exception-detection/SKILL.md` — leave it alone or commit separately; do not fold it into this work.

Context: a Cowork session installed 5 skills via package-and-stage-skill Entry point B (tax-appeal, fleet-advisory-remediation, daily-brief, deal-comparison, market-monitor), verified the runtime cache byte-for-byte, and then swept for stale references left by commit `da80e05` ("Retire 6 skills", 2026-08-05). That sweep is the source of Tasks 3–5 below. All findings were verified against the repo, not inferred.

Run the tasks in order. Task 3 was ruled on by Gabriel on 2026-08-12 and is now an instruction, not a question.

---

## TASK 1 — Kill the phantom PENDING_REIMPORT entry (root fix)

`rent-comp` was retired 2026-08-05 (moved to `_archive/rent-comp_retired-2026-08-05/`), but `tools/package_skills.py` still lists it as a `target-markets.json` consumer. The post-commit hook therefore records it as pending on every commit touching that file. It can never be cleared by an install, because there is no skill to install.

Edit `tools/package_skills.py` — delete line 355 from the `SHARED_ROOT_DEPS` dict:

```python
    'rent-comp': ['target-markets.json'],
```

Verified: no test in `tools/` asserts on `rent-comp` (`git grep -n rent-comp -- tools/` returns only this line), so this is a one-line deletion with no test fallout. Run the suite anyway.

Then clear the ledger entry:

```
python tools\pending_reimport.py clear rent-comp
```

Note the other 3 ledger entries (`acquisition-underwriting`, `deal-execution`, `loi-generation`, all from `0f5c23a`) are genuine and stay pending — they need a real package-and-stage pass. Do NOT clear them here.

---

## TASK 2 — Write the reimport event_log entry

The entry is already drafted and reviewed. Use `--entry-file`, never stdin (cp1252 encoding gotcha; the entry contains em-dashes):

```
python C:\Users\Owner\.claude\maintenance\append-event-log.py --entry-file "C:\Users\Owner\ora-skills\_staging\2026-08-12_pending-reimport-batch\event-log-entry.md"
```

Read it before writing it — it records that the handoff's stated commit (`b66b708`) was two commits stale, and that the ledger was deliberately left alone. Amend if you disagree with either characterization.

---

## TASK 3 — RULED 2026-08-12: fold the comp-grid discipline into `acquisition-underwriting`

**Gabriel's ruling (2026-08-12): option (b) — lift the comp-grid discipline out of the archived `rent-comp` and inline it into `acquisition-underwriting`. Do NOT un-retire `rent-comp`; it stays in `_archive`.**

Background (why this was needed): `_archive/rent-comp_retired-2026-08-05/RETIRED.md` justifies the retirement with *"market-monitor v1.2 absorbed comp-sourcing discipline (confirmed real, KEEP)."* That claim does not survive inspection. market-monitor v1.2's `SOURCING DISCIPLINE` section is about **vendor/operator-published report credibility** — a different thing that happens to share the word "sourcing." Nothing in market-monitor reproduces rent-comp's comp-grid workflow. Meanwhile `acquisition-underwriting` — the single deal-evaluation funnel — cites it in four live places (L166 Phase step, L257 valuation mechanics, L408 COMPS mode definition, L436 data-flow chain). The capability was dropped while its only consumer kept depending on it.

### Lift ONLY sections 1 and 2. Read this before touching anything.

The archived `_archive/rent-comp_retired-2026-08-05/SKILL.md` is 181 lines in 7 sections. **Three of them must not be lifted** — inlining them would reintroduce superseded doctrine:

| Section | Lines | Action |
|---|---|---|
| **§1 RENT COMP RESEARCH WORKFLOW** (Steps 1–5: multi-source search → data extraction → comp table assembly → statistical analysis → normalization) | 12–62 | **LIFT** — this is the "comp-grid discipline" L257 cites by name |
| **§2 SALE COMP RESEARCH WORKFLOW** (Steps 1–3) | 63–88 | **LIFT** — this is the "sale comp grids" half of L408's COMPS mode |
| **§3 REPLACEMENT COST ANALYSIS** | 89–115 | **DO NOT LIFT — CONFLICT.** Uses a superseded component build-up ($85–120/SF hard costs, soft costs 15–20%, dev profit 10–15%). `acquisition-underwriting` already owns replacement cost via **RCT v03** (`config/replacement-cost.v3.json`, Iron rule 11: pull live, never hand-edit). Inlining §3 reintroduces a competing second method — precisely the failure mode of the 2026-07-27 incident logged as *"Off-market master: $150/SF benchmark caught and reverted against the 2026-07-14 RCT v03 ratification."* |
| **§4 MARKET CONTEXT OVERLAY** | 116–126 | Do not lift — market-level context is `market-monitor`'s scope |
| **§5 OUTPUT FORMATS** | 127–146 | Do not lift — formats for a standalone skill that no longer exists; `acquisition-underwriting` has its own mode outputs |
| **§6 OXFORD MARKET BENCHMARKS** | 147–171 | **DO NOT LIFT — DUPLICATE.** A hand-maintained rent/cap/price-PSF table whose own header admits it must be *"kept in parity with"* `target-markets.json`. That file is already bundled into `acquisition-underwriting` as a `SHARED_ROOT_DEPS` consumer. Lifting §6 creates a second drifting copy of canonical market data. Cite `target-markets.json` instead. |
| **§7 CROSS-SKILL INTEGRATION** | 172–178 | Do not lift — plumbing for a retired skill |

Net lift: roughly 75 lines, not 181.

### Then rewire the four references

Once §1–§2 are inlined (suggested home: a `COMP GRID DISCIPLINE` subsection under UNDERWRITING CONVENTIONS, adjacent to the existing RCT material so the boundary between comp-based and cost-based valuation stays visible):

- **L166** — *"refresh the rent-comp grid (`rent-comp` skill)"* → point at the new in-skill section.
- **L257** — *"per the `rent-comp` skill's comp-grid discipline"* → point at the new in-skill section.
- **L408** — *"rent + sale comp grids per rent-comp skill"* → point at the new in-skill section.
- **L436** — the cross-skill data-flow chain opens with `rent-comp` as its first node. Remove that node and re-anchor the chain on `market-monitor`, which is what actually feeds it now.

Also update `_archive/rent-comp_retired-2026-08-05/RETIRED.md` with a correction note: the original "market-monitor absorbed it" rationale was wrong, the comp-grid discipline was inlined into `acquisition-underwriting` on 2026-08-12, and §3/§6 were deliberately left behind as superseded. A wrong retirement record is how this stayed invisible for a week.

### Version + reimport

`acquisition-underwriting` is already pending reimport from `0f5c23a`, so this folds into a package-and-stage pass you owe regardless. Bump the version, note the inlining in the changelog, and run Entry point A. Its ledger entry clears only on a confirmed Save-skill click plus verified cache re-sync.

### One thing to raise with Gabriel afterward, not now

`rent-comp` was retired on a "zero-use" finding, but it was invoked *by* `acquisition-underwriting` rather than by name — which is exactly what zero direct use looks like for a skill-invoked skill. The same audit retired five others the same day (`census-acs-extract`, `code-debugging-optimizations`, `maintenance-analytics`, `oxford-cc-strategic-audit`, `re-operations`). `census-acs-extract` shows the same signature: `submarket-spatial-analysis` names it as the source for Location Score component 4. Worth a re-audit pass that counts skill-to-skill references, not just direct invocations.

---

## TASK 4 — Tombstone the four unambiguous dead references

These need no ruling — the capability is gone and the retirement record names no successor. Match the existing house pattern already used correctly in `tax-appeal/SKILL.md:79,205`, `deal-execution/SKILL.md:442` and `loi-generation/SKILL.md:483` (those three are already correct — do not touch them).

Make these edits surgical; do not rewrite surrounding prose.

**`capex-budgeting/SKILL.md`** — the worst of the four; its Annual Capex Budget workflow opens with an unexecutable step.

- L21 — replace `- maintenance-analytics skill output (predictive failure horizons by system)` with:
  `- **(no successor):** \`maintenance-analytics\` retired 2026-08-05 (zero-use) — predictive failure horizons by system need a manual source (vendor service records, warranty schedules, building-system age from the Notion property database)`
- L31 — replace `1. Pull predictive maintenance forecast for next 12 months from maintenance-analytics.` with:
  `1. Assemble the next-12-month predictive maintenance forecast manually — \`maintenance-analytics\` retired 2026-08-05 with no successor named; source from vendor service records, warranty schedules, and building-system age.`
- L70 — replace `- maintenance-analytics skill (failure horizons)` with:
  `- **(no successor):** \`maintenance-analytics\` retired 2026-08-05 — failure horizons need a manual source until one exists`

**`submarket-spatial-analysis/SKILL.md`**

- L84 — insert a tombstone clause at the start of the bullet, preserving the rest of the sentence verbatim (it draws a distinction that is still correct and worth keeping). Prepend: `\`census-acs-extract\` retired 2026-08-05 (zero-use), no successor named — the archived script survives at \`_archive/census-acs-extract_retired-2026-08-05/census_acs_extract.py\` and can still be run manually. When run, it ` … then continue with the existing `closes the labor-quality/attainment sub-gap at the metro level…` text unchanged.
- L92 — replace `- census-acs-extract skill (metro-level labor-quality/attainment confirmation, Location Score component 4)` with:
  `- **(no successor):** \`census-acs-extract\` retired 2026-08-05 — Location Score component 4 (metro labor-quality/attainment) now needs a manual ACS pull; archived script at \`_archive/census-acs-extract_retired-2026-08-05/census_acs_extract.py\``
- L98 is a **changelog** line — leave it alone. Changelogs are frozen history; tombstoning them rewrites the record.

**`lease-abstraction-pipeline/SKILL.md`**

- L152 — replace `- **rent-comp:** Compare extracted rent PSF against current market comps for below/above-market flags.` with:
  `- **(pending ruling):** \`rent-comp\` retired 2026-08-05 — below/above-market rent PSF flags need a manual comp pull until the comp-grid gap (see 2026-08-12 event_log) is resolved.`

**`parcel-data-recovery/SKILL.md`**

- L32 — replace the trailing parenthetical `(placeholder rent grid until rent-comp P2)` with:
  `(placeholder rent grid; \`rent-comp\` retired 2026-08-05 — its "P2" successor never shipped)`

---

## TASK 5 — Fix the broken test

`tools/test_skill_drift_report_realdata.py` lines 45 and 47 pin a real-data fixture to a skill that no longer exists in the repo:

```python
#   census-acs-extract    -> folded block scalar (`description: >`)
BLOCK_SCALAR_SKILL = 'census-acs-extract'
```

This is a real-data test, so it is currently either failing or silently skipping — determine which before changing anything, because a silent skip means the folded-block-scalar parse path has been untested since 2026-08-05. Repoint `BLOCK_SCALAR_SKILL` at a live skill that still uses `description: >`, or pin the fixture to the archived copy explicitly. Do not delete the test.

Also note `tools/skill_drift_report.py:209` mentions `census-acs-extract` and `oxford-cc-strategic-audit` in a comment. Verify it is only a comment; if so, refresh the wording, no behavior change.

---

## TASK 6 — Inventory hygiene (cosmetic, lowest priority)

- `README.md` lists `census-acs-extract` (L102), `rent-comp` (L105, L165), `maintenance-analytics` (L115), `oxford-cc-strategic-audit` (L157) and `code-debugging-optimizations` (L156) as live skills. Only `re-operations` (L114) got the strikethrough treatment. Apply the same `~~name~~ — retired 2026-08-05 (reason)` pattern to the other five.
- `acquisition-underwriting/PACKAGING-NOTE.md`, `daily-brief/…`, `deal-comparison/…`, `market-monitor/…` each name `rent-comp` in the shared-dep consumer list (line 6). Drop it — it must match `SHARED_ROOT_DEPS` after Task 1, or the next drift check reads a false inconsistency.
- `target-markets.json:447` carries the provenance string `"skill: rent-comp (Oxford Market Benchmarks)"`. **Careful:** this file is version-gated by a pre-commit hook that blocks edits without a version bump, and it is the shared dep for 4 consumer skills — changing it forces a reimport of all of them. Probably not worth it for a provenance string; if you leave it, note why.
- `cowork-settings/versions/**` hits are frozen historical version documents. Leave them alone.

---

## Done =

Task 1 committed with the suite green · Task 2 log entry written and visible in `event_log.md` · Task 3 implemented per the 2026-08-12 ruling — §1–§2 inlined, §3/§6 verifiably NOT carried over, all four references rewired, RETIRED.md corrected · Task 4 edits applied surgically with no collateral prose changes · Task 5 test verified genuinely passing, not skipping · repo gate + independent local review before any "done" claim · every skill whose `SKILL.md` changed gets a version bump and goes through package-and-stage-skill Entry point A (its ledger entry clears only on a confirmed Save-skill click + verified cache re-sync).

## Do NOT

- Do not clear `acquisition-underwriting`, `deal-execution` or `loi-generation` from the ledger without a real reimport — they are genuinely pending from `0f5c23a`.
- Do not edit the runtime cache under `AppData\...\skills-plugin\` directly (2026-06-11 Roaming-alias clobber incident). Repo leads, platform follows.
- Do not delete anything — move to `_archive/` per the never-delete invariant.
