---
name: "add-target-market"
description: "Use when Gabriel ratifies a new ORA acquisition target market or cluster (or promotes entry to established): runs the full parity sweep across target-markets.json, acquisition-underwriting, deal-comparison, market-monitor, daily-brief, scan tasks, Notion selects and memory."
---

# Add Target Market (parity sweep)

A market is ratified in one sentence and implemented in a dozen places. Louisville (2026-08-05) was reported at full parity while three consumer skills stayed stale for 10 days (`target-markets.json` changelog_1_10). Chicago–Greater Cook County (2026-09-29) touched two skill cards, two Notion selects and a multi-block Code patch. This skill makes the sweep one procedure with a closing proof.

## Preconditions (stop if any is missing)

1. **Gabriel's in-turn ratification**, quoted with date. A proposal or a memo recommendation is not ratification.
2. The ratified facts: canonical market name (exact string), tier (entry / established), geographic scope and exclusions, exit cap, and whether a new state enters the footprint.
3. Surface: every repo write happens on **Claude Code** in `ora-skills`. From Cowork, do only the Notion steps and the skill cards, then hand the rest to Code with a base-stamped patch (`acquisition-underwriting` POST-RUN LESSON CAPTURE rule).

## Derived inputs (source every figure; no placeholders in ratified doctrine)

- **Exit cap:** nearest established peer + 25–50 bps for an entry cluster (acquisition-underwriting UNDERWRITING CONVENTIONS), bracketed by live market cap-rate prints. State the peer and the prints.
- **RCT v03 row:** from `acquisition-underwriting/references/cw-2025-construction-costs.json` (fallback `~/.claude/scheduled-tasks/ora-deal-sourcing-scan/skills/cw-2025-construction-costs.json`) using the reference file's own method: `b` from the metro's small/next tiers, premium `(109200/40000)^b`, POINT = hard × premium × 1.30 × 1.0487, LOW = 0.90×, HIGH = 1.10×. Not in the guide → mark [PROXY: nearest metro] and add the market to the always-DENOMINATOR-SENSITIVE list.
- **Reassessment row** if the state is new to the footprint: reset behavior, ratio/cap mechanics, transfer tax, entity-deal note, abatement levers — each sourced.
- **Baseline metrics:** vacancy, YoY change, rent, absorption, pipeline, cap rate — source + date; blended vs shallow-bay stated; unknowns null, never guessed.

## Touch list (all of it, every time)

| # | Target | Change |
|---|---|---|
| 1 | `ora-skills/target-markets.json` (repo root, the ONLY source) | cluster record, `acceptable_states` if a new state, version + `updated`, `changelog_1_N` |
| 2 | Consumer packages (acquisition-underwriting, deal-comparison, market-monitor, daily-brief) | **Do NOT copy the JSON into skill dirs.** `tools/package_skills.py` injects the repo-root file at package time (SHARED_ROOT_DEPS); a copy in the skill dir creates a duplicate zip entry. Repackage all four via `package-and-stage-skill`; Gabriel clicks Save |
| 3 | `Investment Candidates -- 2026/target-markets.json` mirror | byte copy of #1 (OneDrive Business write — ask once) |
| 4 | acquisition-underwriting SKILL.md | Gate 3 cluster list + Nth-cluster sentence; exit-cap line; RCT row (+ DENOMINATOR list if proxy); reassessment row if new state; drift-sweep market count; changelog entry within the 2,000-char cap |
| 5 | acquisition-underwriting references | `doctrine-rationale-and-incidents.md` mirror lines; `state-reassessment-matrix.md` row; `market-and-cost-calibration-data.md` RCT provenance paragraph |
| 6 | deal-comparison SKILL.md | Market Cluster Fit list (entry = 4, established = 6) + changelog |
| 7 | market-monitor SKILL.md | profile block, heading date, cross-market table column + count |
| 8 | daily-brief SKILL.md | Sections 1–2 scope lines + changelog (keep frontmatter version token in step) |
| 9 | Scheduled tasks `ora-entry-market-scan` / `ora-deal-sourcing-scan` | market list in the task SKILL.md only; never re-register, never splice registry JSON; confirm with `fleet-status.py` |
| 10 | `ora-millage-lookup` + `county-parcel-screen` registries | county/assessor endpoints (V with date, or U) |
| 11 | Notion `bcfe4a03` Market select + `caa809b7` Metro select | `ALTER COLUMN ... SET SELECT(...)` listing EVERY existing option with its current color plus the new one; afterwards verify every pre-existing option URL/UUID is unchanged |
| 12 | `ora-skill-text-audit` class (j) | alias mapping for the Outreach Metro label |
| 13 | Memory narrative twin + `event_log.md` | cluster list line; dated history in event_log only |

## Parity proof (the task is not done until this passes)

1. Repo-root `target-markets.json` validates (`python -m json.tool`), carries the new version, and the cluster count matches the count stated in acquisition-underwriting, market-monitor and the drift-sweep line.
2. `git grep -n "<canonical name>"` hits every file in rows 4–10; list any `consumers` entry of `target-markets.json` with no hit.
3. After repackaging, `python tools/reimport_correlate.py precheck` passes for all four consumer packages (the injected JSON byte-matches the repo root, raw or EOL-normalized), and after Gabriel's Save the cache copies do too.
4. Notion selects contain the new option; pre-existing option UUIDs unchanged.
5. `doctrine-integrity-probe` passes (H1 marker matches the new acquisition-underwriting version).
6. Report every row of the touch list as APPLIED / SKIPPED (reason) / PENDING (whose action), with base hashes. "Full parity" may be claimed only when rows 1–13 are APPLIED and checks 1–5 pass.

## Out of scope

Scorecard weights, Stage 1 floors and governor constants never change in this procedure. Promoting a cluster from entry to established also changes Ruling 3 satellite eligibility and deal-comparison's score (4 → 6); run the same touch list with that change.