---
name: "deal-log-refresh"
description: "Use when a deal's model, IC memo or analysis version increments and the Notion Deal Sourcing Log entry must be refreshed with the new numbers, file names and next action."
---

# Deal Log Refresh

Keeps the Notion Deal Sourcing Log (data source `9a6ae219`, canonical) in step with the deal files after every version bump. Internal write only; never sends anything to a counterparty.

## When it runs

Run as the last step of any session that produced a new version of a deal's model, IC memo, price/escrow schedule or location/submarket analysis. Also run when Gabriel says the log is stale.

## Procedure

1. **Find the entry.** Search the Deal Sourcing Log by address; fetch the page. If two entries exist, stop and ask which is canonical (a `Duplicate Of` value points to the survivor).
2. **Read the source of truth, not memory.** Pull the figures from the newest model workbook and memo in the deal folder (Business\Investment Candidates -- 2026): unlevered/levered IRR by scenario, yield-on-cost, going-in cap, DSCR, basis and carrying-cost gate values, walk price, Quality / Economics / Combined / P(exec) / Expected scores, verdict. If a figure cannot be traced to a cell or memo line, leave the Notion value unchanged and say so.
3. **Classify the bump.** Compare the new memo and model to the values now on the page. **Scores-or-floors-changed** means any gate value, floor result, score component, Combined, Economics or Expected score differs from the page. **Narrative-only** means none does (wording, file names, next action, added exhibits). Record the classification in the version block.
4. **Check field types before writing.** Fetch the data source schema once and note every select, status, checkbox, date and formula property. Write only allowed option values to select fields (for example Floor Result accepts PASS, FAIL-BASIS, FAIL-YIELD, FAIL-BOTH, N/A; Verdict and Go / No-Go are Gabriel's); put any qualifying detail (which floor, which scenario, which version) in the text field it belongs to (Gate Review or Notes / Flags), not in the select. Never add a select option without Gabriel's instruction. Formula fields are read-only.
5. **Update properties.**
   - Narrative-only bump: update Edge Findings, Next Action, Notes / Flags and any changed Walk Price or ORA Max Defensible Price. Leave Gate Review, Score Components, Floor Result and DD-Critical Status unchanged.
   - Scores-or-floors-changed bump: **restate the full set in the same write** — Score Components, Gate Review, Floor Result, DD-Critical Status, Buy Box Score, Economics Score, Expected Score, Walk Price and ORA Max Defensible Price — from the memo, using the memo's wording and its FLAG / PASS results for every gate element (yield, each IRR scenario, DSCR, basis, carrying cost, and any others the page lists). A gate or score element that cannot be traced to the memo or model is left in place and marked "Restated through vNN except: <element> (untraceable)" in the field and in Notes / Flags. Never leave a page that mixes prior-version and current-version gate values without that marker.
6. **Insert a version block at the top of the page body** headed `REVISION vNN — YYYY-MM-DD (supersedes prior numbers below)`: the bump classification, the changed inputs, the headline outcomes, the walk, the scores, the gate results, and the file names. Leave earlier content in place beneath it.
7. **File names.** List the current files by their deal-folder names; note that superseded copies sit in `archive/`. Write folder paths with " / " as the separator, not backslashes, and write script or file names in plain text so the editor does not autolink them (for example, write ora_ring_demographics.py inside backticks or as plain text and check the rendered result). After writing, fetch the page and confirm no file name became a link (a name such as a .py file can render as a bracketed link); repair any that did.
8. **Confidential deals.** If the deal is on the active confidential roster, the Notion write is still internal, but do not copy terms to any external surface.
9. **Verify.** Re-fetch the page and confirm the version block and each changed property. Then search the page and properties for stale figures: every prior-version gate value, score and price that the new memo supersedes (for example an old yield, IRR, DSCR or Combined score) must either be gone from the properties or sit beneath the version block in superseded content. Report any survivor and fix it, or state why it stays.

## Boundaries

- Internal only. No email, no HubSpot write, no broker contact.
- Never delete entries; never change Verdict or Go / No-Go without Gabriel's instruction.
- Tag [est] and [SPECULATIVE] exactly as the memo does.

## Changelog

- v1.2 (2026-09-28): Added a field-type check before writing (select fields take only allowed options, with qualifying detail routed to text fields; formula fields read-only; no new select options without Gabriel) after a Floor Result write with explanatory text was rejected on the 4100 Perimeter Dr entry. Added a post-write autolink check for file names.
- v1.1 (2026-09-28): Added the bump classification step and full restatement of Score Components, Gate Review, Floor Result and DD-Critical Status whenever scores or floors change (with an untraceable-element marker instead of a partial rewrite), path and autolink handling for file names, and a stale-figure sweep in the verify step. Motivated by the 4100 Perimeter Dr entry, where v03 refreshed the scores but Gate Review and Score Components still carried v01 wording.
- v1.0 (2026-09-28): Created after the 4100 Perimeter Dr v02 revision, where the Notion entry lagged the model by two versions.