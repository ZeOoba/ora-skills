---
name: verified-deal-recon
description: "Use whenever ONE named acquisition target — a street address, a property name, or a single offering memorandum — needs a real pursue/pass decision before underwriting: Oxford Realty Advisors' adversarially-verified SINGLE-TARGET PRE-SCREEN DEFAULT. Trigger on: pre-screen this, screen this property, is this worth underwriting, first look, recon this deal, verified deal recon, should we pursue, worth a look. NOT for batch-triaging a broker inbox and NOT for off-market owner lead-lists. Does NOT underwrite — hands off to acquisition-underwriting."
---

# Verified Deal Recon — ORA single-target pre-screen (v1.5)

Runs the `verified-deal-recon` workflow: one recon pass, three adversarial verifiers working independently, one synthesized brief. The verifiers do their own research and are instructed to refute the recon — that adversarial step is the whole point, and it is what separates this from the bare `deal-recon` agent (instant first-look only).

## Why this is a skill and not a bare workflow

Workflows live in `.claude/workflows/` and custom subagents in `.claude/agents/`. **Neither directory syncs to Cowork — only `.claude/skills/` does.** From 2026-07-09 until 2026-08-22 this pre-screen was a Code-surface workflow calling a Code-surface agent, which meant the User Preferences named it "the single-target pre-screen default" while on Cowork it silently resolved to nothing. Packaging it as a skill that carries its own script is what makes one canonical copy work on both surfaces.

## How to run it

Invoke the Workflow tool against this skill's own bundled script — do **not** rely on `{name:"verified-deal-recon"}`, which only resolves where `.claude/workflows/` happens to hold a copy:

```
Workflow({
  scriptPath: "<this skill's directory>/references/verified-deal-recon.js",
  args: { property: "<full property brief as a string>", today: "<YYYY-MM-DD>" }
})
```

`args` also accepts a plain string (the property brief), in which case the ledger date is emitted as the literal token `<STAMP-DATE>` for the calling session to fill in.

**Workflow opt-in:** invoking this skill IS the opt-in. The Workflow tool requires explicit user authorisation before fanning out agents; a skill whose instructions direct a Workflow call satisfies that. Do not additionally ask for permission.

**Cost:** five agents (1 recon + 3 verifiers + 1 synthesis). The recon runs on opus; the verifiers run as `Explore`. Budget accordingly on a batch.

## Writing the property brief

The brief is the only input. Put everything known into it — address, SF, acreage, asking price, tenancy, vintage, broker, and anything from the OM. The recon agent cannot ask questions mid-run; gaps become `[UNVERIFIED]` tags rather than clarifications. First line of the brief becomes the deal name in the ledger row, so lead with the address.

## What comes back

A `brief` object: verdict, one-line thesis, snapshot, verified rent and sale comps, basis read, submarket demand, kill risks, pre-mortem, open items, confidence. Plus `reconSoloVerdict` (what the recon said before verification), `verifierCount`, and `anyFlip` — **`anyFlip: true` means at least one verifier flipped the recommendation, which is the single most informative field in the return.** Read it first.

## After the run — three standing rules

1. **Hand off, do not underwrite.** A PURSUE or NEEDS_MORE goes to `acquisition-underwriting` (SCREEN or FULL). This skill deliberately computes no DSCR, LTV or IRR.
2. **Ledger row is a DRAFT.** `ledgerRowDraft` is never written by the workflow and must never be appended on a provisional result. Append it to `memory/deal-decision-ledger.md` only after Gabriel ratifies the verdict in-turn, and stamp the real date if it reads `<STAMP-DATE>`. The 6-column schema is `Date | Deal | Verdict | one-line reason | buy-box rule validated/refined | FORT`; write `—` for FORT unless Stage 2.8 actually ran.
3. **Dedupe before logging.** Check both the Notion Deal Sourcing Log (`9a6ae219`) and the Acquisition Pipeline Tracker (`bcfe4a03`) for an existing row on this parcel; update in place rather than creating a duplicate, and stamp `Last Activity` = today on any row you touch. **Re-query immediately before any create (v1.5).** A dedupe done earlier in the run can be stale: a sourcing scan may have created the row since. Right before creating a Deal Sourcing Log row, query the data source again by the natural key (normalized street address, then `Listing URL`) across rows of EVERY `Status`, `Dead` and `Passed` included, and update a match instead of creating a row. Query the data source, not search alone (search lags, so a miss there proves nothing). If a create returns no page ID or a quota notice, follow the scans' STEP 5 CREATE-VERIFY rule: look the row up by the same key and never blind-retry the create. A duplicate that appears anyway is flagged to Gabriel. Any row this skill marks as a duplicate gets both flags, as `deal-retirement` step 3a requires: **Both duplicate flags are required together:** every row flagged as a duplicate gets `Exclude from Calibration` ticked AND `Duplicate Of` set to `app.notion.com/<canonical page id, 32 hex> (deduped YYYY-MM-DD)`, the form the log already uses; one without the other is incomplete. The back-test (`maintenance/funnel-backtest.py` in `~/.claude`) recovers the scan's first-sighting prediction across a duplicate set by parsing that 32-hex id, which is why `Verdict at First Sighting` and `Score at First Sighting` are never copied, moved or cleared on any row of the set. **Never write `Verdict at First Sighting` or `Score at First Sighting` (v1.5)** — leave both blank on a row you create and exactly as found on a row you update. They are the sourcing scans' write-once original prediction, which the monthly back-test (`maintenance/funnel-backtest.py` in `~/.claude`) grades; a recon verdict changes `Verdict`, `Status` or `Go / No-Go`, never these. **A ratified PASS is recorded as `Go / No-Go` = `🔴 Pass` (and `Status` = `Passed` if the status is changed), never as `Status = Dead`**, which is reserved for a listing that is gone with no ORA decision; the back-test cannot tell an undecided `Dead` row from a withdrawn listing.
4. **Recent-acquisition parity (v1.3).** The recon checklist pulls the last recorded sale price and date; if the seller acquired within 24 months, the brief states ask vs. seller basis (`acquisition-underwriting` Stage -1 item 10). A recorded sale inside 24 months is a comp, not a motivation signal.

## Confidentiality

The recon prompt carries ORA's standing rule verbatim: never put an active ORA deal name or identifier into an external `WebSearch`/`WebFetch` query, and never include not-yet-closed ORA deal data in output. The authoritative roster is `~/.claude/hooks/confidential-terms.json` (keys with `active: true`). On any surface where that file is unreachable, treat an uncertain name as confidential and keep it out of external queries.

## Port notes (v1.2)

Two changes from v1.1, both required for Cowork; behaviour is otherwise identical.

1. **`agentType:'deal-recon'` removed.** The agent's system prompt (`.claude/agents/deal-recon.md`, 2026-07-17) is inlined verbatim into the Phase 1 prompt with `model:'opus'` matching its frontmatter. The `Explore` verifiers are unchanged — `Explore` is a built-in agent type available on both surfaces.
2. **`new Date()` removed.** Workflow scripts throw on argless `new Date()`, `Date.now()` and `Math.random()` — they would break resume. The ledger date now arrives via `args.today` or falls back to a `<STAMP-DATE>` token.

If `.claude/agents/deal-recon.md` is later edited on the Code surface, re-inline it here — the two copies are not linked. Since v1.4 this copy deliberately differs (the 11-cluster geography and the LTV split): keep both when re-inlining.

## Changelog

- **v1.5 (2026-11-06; renumbered from v1.4 after #215 landed):** rule 3 gains the write-once first-sighting never-write rule (`Verdict at First Sighting`, `Score at First Sighting`) and records a ratified PASS as `Go / No-Go` = 🔴 Pass, reserving `Status = Dead` for listings that are gone (Gabriel-approved, business-loops review F-11); also re-query the Sourcing Log by natural key immediately before any create, and any row it marks as a duplicate gets both `Exclude from Calibration` and `Duplicate Of`, through which the back-test recovers the scan's first-sighting prediction (merge-gate F-001 on #214). No score, gate, floor or governor value changed.
- **v1.4 (2026-11-05):** The recon prompt's buy-box sentence named only the seven holdings states (OH, MD, IN, WI, MO, KS, TN), so the analyst read Grand Rapids, Richmond, Des Moines, Louisville and Chicago as out of scope and TN as a target. It now names the eleven clusters in `target-markets.json`, re-inlines the Amendment H portfolio clause that `.claude/agents/deal-recon.md` gained in ora-claude-config #396, and splits LTV into the 40% portfolio aggregate and the 65% per-property refi ceiling. `tools/doctrine_consistency.py` now fails CI if this line drops a cluster state. The agent file still carries the old state list; that fix belongs to ora-claude-config. No scored or governor constant changed.
- **v1.3 (2026-10-27):** recon checklist item 5 also pulls the last recorded sale; seller acquired within 24 months → ask vs. seller basis in the brief (parity with `acquisition-underwriting` v4.37 Stage -1 item 10); item 6 also notes the construction type (tilt-up baseline vs PEMB/masonry/brick, per the Construction-Type Multiplier).
- **v1.2 (2026-08-22):** cross-surface port — runs on Cowork and Code (detail under Port notes above).
