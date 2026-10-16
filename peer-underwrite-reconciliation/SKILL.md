---
name: "peer-underwrite-reconciliation"
description: "Use when the user supplies other LLM or third-party underwrites (ChatGPT, Gemini, Grok, broker pro formas) of a deal ORA has underwritten and asks to improve the IC memo and IRR model from them."
---

# Peer Underwrite Reconciliation

Purpose: extract what is valuable from outside underwrites without importing their errors, and use them as an independent check on ORA's own model. Origin: East Pointe Plaza, 2026-10-01 (ChatGPT, Gemini, Grok). The third reviewer exposed that ORA's own first-pass reading of the rent roll was wrong.

## Rules

1. **Read every document fully before planning.** Run `pdfinfo` on each. A Print-To-PDF producer or empty `pdftotext` means no text layer: render pages (`pdftoppm -png -r 110`) and read visually (acquisition-underwriting Stage -1 Rule 7). Use separate output filenames per document.
2. **Extract every figure into one table** (metric, each outside value, ORA live value, audit note). Outside figures are typed as inputs (blue); ORA values are live links to the model.
3. **Audit against source documents, not against ORA's prior conclusions.** Source = seller financials, rent roll, OM, county records, market reports. For each outside figure decide: ties to source / ties to source on a different basis / unsupported / contradicted.
4. **Convergence rule.** When two or more outside documents agree with each other and disagree with ORA, treat ORA's reading as the suspect until proven otherwise. Re-read the source column by column (see rent-roll-qc Step 0A) before labelling the outside figures errors. Never write "error" in an adopted/rejected ledger without testing the alternative reading.
5. **Re-run outside assumptions through ORA's cost structure.** Outside gross-rent or NOI claims usually omit vacancy, downtime, TI/LC, management fee, reserves, reassessed tax, or assume NNN recovery. Solve the rent or price that actually clears the floors (required-rent solve; price clearing 8% yield on cost) instead of arguing with their number.
6. **Replicate their returns.** Feed the outside document's own exit cap, rate, LTV and growth into the ORA engine. If the outside IRR does not reproduce, say so with both numbers. Test any quoted loan against the 1.25x DSCR governor on in-place and reported NOI, not just the outside NOI.
7. **Valuation-cap test.** Compare the outside valuation cap to the market cap the same document cites; quantify the value at the market cap using its own NOI.
8. **Corroboration is information.** Where an outside NOI or opex independently lands near ORA's, say so (triangulation).
9. **Deliverables.** (a) A Peer Underwrite Recon tab in the model: metric table, then ADOPTED and REJECTED / CORRECTED lists per document. (b) An IC memo appendix with the same ledger. (c) Any adopted lens (rent normalization, outlot option, rent-basis cases) built as formula-linked tabs, with live engines rather than static values where an IRR is quoted. (d) Updated broker request list, questions for Gabriel, and bid structure. (e) A short "What changed" block in memo §1 that states plainly any correction of ORA's own earlier text.
10. **Do not change the verdict by averaging.** The outside underwrites move ORA's inputs only where a source document supports them. Verdict, scorecard and governor constants are untouched unless an input genuinely changes.
11. **Version, never overwrite.** New model and memo versions; move prior versions to /archive/.

## Output checklist

- Outside documents read in full (text layer or visual); no-text-layer files flagged.
- Figure table complete; every rejection has a tested alternative reading.
- Required-rent and price-clearing solves run; outside IRRs replicated or shown not reproducible.
- Debt-service governor test on any quoted loan.
- Ledger in the model and memo; corrections of ORA's own prior statements called out.
- Model recalculated with 0 errors; ties = 0; mirror check if a Python mirror exists.
- Memo rendered and scanned for stale figures.