# deal-execution — rationale and incident narratives

Moved out of `SKILL.md` on 2026-09-22 (body split). Provenance only — every operative rule is restated in `SKILL.md`, which is authoritative.

## File-naming citation provenance (Workflow 1 step 6)

6. File naming: per ORA's three standing naming schemas (ratified 2026-06-10; ORA Cowork Global Operating Prompt v3.0, 2026-07-16 — do NOT unify; supersedes the archived v2.0/2026-06-11 doc of the same ratified rule). PSA deliverables are deal-bound → use the deal-file schema `[Address] [Purpose] [MM-YYYY]`. (Supersedes the single unified "ORA File-Naming Standard 2026-05-14.md," which predates the 2026-06-10 three-schema ratification and is retained only as historical provenance.)

## Workflow 2 Step 0 — origin (2026-07-31, 754 Old State Route 74)

> Origin: 2026-07-31, 754 Old State Route 74. KMK Law delivered a Litera Compare output with 0 tracked changes and 29 real revisions. Its summary block named the base as ORA's own 07-22 clean draft — which is what established that seller had accepted the entire package (estoppel article, uncapped monetary-lien release, BOR rights, all sixteen representations) rather than simply not responding.

## Workflow 2A — origin (2026-06-11, 754 Old State Route 74)

When ANY PSA draft arrives that this skill did not generate — own counsel's initial draft, seller counsel's first draft, or a counter-draft — review it BEFORE it circulates. Own-counsel drafts get the same scrutiny as seller paper: a recycled template that ships today is an executed contract next month. (Origin: 2026-06-11, 754 Old State Route 74 — own counsel's draft carried a $50K deposit error, 9 LOI-conformance failures, and omitted the deal's linchpin easement, which existed in no binding document.)

## Workflow 2B — origin (2026-08-01, 754 Old State Route 74)

> Origin: 2026-08-01, 754 Old State Route 74. The 7/21 review memo recommended fifteen changes across four severity tiers. The draft transmitted to seller's counsel on 7/22 carried the §4.1/§31 restructure and the estoppel article — and dropped **nine** of the remaining recommendations: the willful-default carve-out, the MAC clause, the minimum-occupancy condition, the memorandum-of-contract right, interest-bearing escrow, the 5% casualty threshold, the 30-day Phase II extension with deposit refundability, the expanded §2.5 refund grounds, and 12-month representation survival. **Four** were ORA's own mandatory buyer-protective provisions (MAC, vacancy delivery cross-default, memorandum of contract, willful default carve-out — the bring-down certificate and interim operating covenants did survive); three were executed-LOI terms; two were ORA standing positions. **Seller never rejected any of them — they were never put to seller.** The 7/22 draft also still carried a July 1 offer-expiration date that had lapsed three weeks earlier; seller's counsel corrected it unilaterally. A review that produces recommendations nobody verifies is indistinguishable from no review at all.

## Check B — why the mandatory 6 vanish quietly

These are the provisions most likely to vanish quietly, because they are ORA-added rather than template-native — nothing in the underlying document complains when they are missing. Grep the draft for each by its operative language, not by section number.

## Notion pipeline stamping — origin (754 Old State Route 74, 2026-07-17)

This is load-bearing for the weekly `ora-deal-command-board`, which reads `Last Activity` (not Notion's system last-edited timestamp) to decide staleness. PSA negotiation that happens off-Notion must still bump `Last Activity`, or the deal false-flags STALLED while under active work. **Origin: 754 Old State Route 74, 2026-07-17 — the row sat at a frozen 6/11 timestamp through weeks of live PSA negotiation and false-flagged STALLED on the Monday board.** Do NOT rely on the board to stamp this itself — the board is read-only by charter (a board that stamped activity would reset its own stall clock merely by surfacing a deal).

## Notion pipeline stamping — why `Next Action Date` matters here and who reads it

This skill is the highest-value stamper of the three, because PSA execution is where dated obligations cluster — EMD delivery deadlines, Feasibility Period expiry, contingency-period ends. Those are exactly the dates that must not live only in a paragraph. Where a workflow produces several dated obligations at once, `Next Action Date` carries the **nearest one ORA must act on**, not the furthest; the full set belongs in the Deal-Terms Register and the diary, which is what those exist for.

Two consumers read this field and both are hardened against a bad value: `ora-deal-command-board` STEP 2b resolves it with a prose fallback and reports column-vs-prose disagreement as `DATE DIVERGENCE` rather than reconciling it, and `ora-deal-aging-sla` STEP 3d flags a past-due date whose `Last Activity` predates it as a missed self-imposed commitment. A wrong date here therefore surfaces as a contradiction rather than being silently trusted — but it still costs a human the reconciliation, so stamp what the document says, not what you infer it means.

## File-naming citation provenance (Output formats)

- File naming: per ORA's three standing naming schemas (ratified 2026-06-10; ORA Cowork Global Operating Prompt v3.0, 2026-07-16 — do NOT unify; supersedes the archived v2.0/2026-06-11 doc of the same ratified rule). Redline/closing deliverables are deal-bound → use the deal-file schema `[Address] [Purpose] [MM-YYYY]`. (Supersedes the single unified "ORA File-Naming Standard 2026-05-14.md," which predates the 2026-06-10 three-schema ratification and is retained only as historical provenance.)
