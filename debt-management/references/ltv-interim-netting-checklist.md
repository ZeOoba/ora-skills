# INTERIM — Manual pre-close aggregate-LTV netting checklist (until a pending-debt register exists)

**INTERIM procedure, in force until a pending-debt register exists and replaces it.** Approved by Gabriel 2026-10-26 to land as interim doctrine. It closes the gap that the acquisition-underwriting STAGE 2.3 Part A all-cash governor sees only debt already booked in the live Master Workbook, so a signed-but-unbooked refi or assumed loan is invisible to it. The gap is closed by PROCEDURE: one hand-filled worksheet per test, no script and no register.

Governor constants are unchanged and are not restated beyond the existing ones: DSCR 1.25x; portfolio-aggregate LTV 40% (flagged only strictly above); per-property 65%. Flag-not-kill: acquisition-underwriting Calibration Ruling 5 — a breach is a flag that needs Gabriel's sign-off, never an automatic block.

## When it runs

- `debt-management` Refinance Evaluation step 5: before recommending, accepting or signing any refi, or any new, assumed or seller-financed loan an ORA entity owes (secured, unsecured or parent-level, including a property-entity mortgage that survives an entity-interest purchase).
- `debt-management` Term-Sheet Redline step 0: again on the FINAL principal in the document about to be signed (including when the document reaches review through `legal-intelligence`).
- `deal-execution` PSA gate: a signed PSA that sells an asset, or a loan-bearing PSA, is listed on the next worksheet (rule 5) and, if it carries a loan, takes its own test.

## Owner and filing

- **Owner:** the session running the refi or loan evaluation fills the worksheet. Gabriel signs any netting in-turn (rule 6); the session never signs for him.
- **Filing:** the finished worksheet is filed in that deal's folder (deal-file naming, e.g. `LTVNettingWorksheet_[Property]_[MMDDYYYY]`), with every document it relies on attached: lender statement or facility agreement (undrawn), payoff letter, closing statement, recorded assignment, executed amendment, signed PSA. At signing and at closing, `deal-execution` Post-Closing item 11 attaches the signing and closing documents to the same worksheet.
- **Pending-deals list:** with no register, the pending items in lines 5 and 6 come from the Acquisition Pipeline Tracker rows under a signed PSA or signed loan and from the open worksheets already filed in deal folders. If the list cannot be established, that is a STOP (rule 9).

## 1. Rules (read top to bottom; each rule only ever raises the figure unless a document is in hand)

1. Start from the live Master Workbook (read order per the firm's source-of-record canon), not a mirror, and not `00_Home!G7` alone. Note the read time. A workbook read older than the last closing, payoff or signing you know of is stale: re-read.
2. Numerator = booked debt (Oxford-share balance of every borrower-side loan, including unsecured and parent-level loans) PLUS every pending loan at its FULL face (balance plus any committed-undrawn availability you can document from the lender statement or facility agreement). The workbook has no commitment or undrawn column, and Original Principal is NOT a commitment; undrawn availability comes only from the loan document. Undrawn you cannot document counts as 0 and is written on the worksheet as "undrawn not documented".
3. Denominator = booked portfolio value at each asset's market exit cap (acquisition-underwriting UNDERWRITING CONVENTIONS), Oxford share. A pending acquisition's value does NOT count until it is booked, except the deal under test, which counts its own underwritten value for its own test only.
4. NO reduction is credited without a document in hand: a payoff, paydown, retirement, sell-down or share cut counts only when the document (payoff letter, closing statement, recorded assignment, executed amendment) is attached to the worksheet with its date. A workbook cell that looks lower is not a document. A verbal or emailed "it closed" is not a document.
5. Pending sales are projected out of the denominator the moment a PSA is signed: remove the asset's value, keep its debt in the numerator until the payoff document is in hand. This can only raise the figure. Unsigned sale talk is not projected; a signed sale is. The `deal-execution` PSA gate is the trigger that puts a signed sale on the worksheet; a 1031 exchange sale is handled the same way.
6. Refi netting (the loan under test's own payoff) is allowed in the test of that loan only, and only with Gabriel's in-turn sign-off. Echo the figure back to him on the worksheet ("netted: old loan <id>, <amount>, document <name, date>") and record his sign-off text and time. The sign-off covers that test only; it is not carried to a later test, a re-test, or another loan. If any term changes, ask again.
7. Two-basis convention stays (acquisition-underwriting STAGE 2.3 Part A): the STAGE 2.3 governor is the ALL-CASH figure (an all-cash acquisition adds no debt); the IRR model, levered IRR, DSCR and IC memo carry the post-close refi, and the IC memo's with-refi portfolio LTV line stays informational. This checklist is the SEPARATE pre-close test for any refi or any new, assumed or seller-financed loan. Report both numbers; never merge them.
8. Result: at or below 40% passes; strictly above 40% is **LTV-FLAGGED (portfolio)**. Compare the unrounded figure; never round down. A flag goes to Gabriel with the figure, the binding loan(s) and the headroom; he signs off or the loan is not accepted. Never kill.
9. Any step you cannot complete (unknown id, unreadable workbook, missing document for a claimed reduction, pending-deals list not established) is a STOP to Gabriel, not a zero and not a pass.

## 2. Worksheet (one per test)

The loan under test appears on line 8a ONLY. Line 5 lists the OTHER pending loans and must never include the loan under test, so its face is counted once.

| # | Line | Entry |
|---|---|---|
| 1 | Workbook read time and source | |
| 2 | Booked debt, Oxford share (all borrower-side loans), from the line-1 read | |
| 3 | Booked value, Oxford share, at exit cap, from the line-1 read | |
| 4 | Booked ratio (line 2 / line 3); compare to `00_Home!G7` and explain any gap | |
| 5 | OTHER pending loans at full face, excluding the loan under test (list: id, lender, face, documented undrawn, post-close Oxford share, document); total | |
| 6 | Pending sales signed (asset, value removed, loan kept in line 2 or 5, PSA date); total value removed | |
| 7 | Reductions credited (document, date, amount): only documented reductions the line-1 read has not yet booked; normally none; total | |
| 8a | Loan under test: full face incl. documented undrawn, at post-close Oxford share; document | |
| 8b | Loan under test: own payoff to net (if any) and its payoff document | |
| 8c | Own value: the underwritten value of the pending acquisition the loan under test belongs to, for this test only; otherwise 0 | |
| 9 | Gabriel's in-turn netting sign-off (text, time) and the echoed figure | |
| 10 | Gross figure = (line 2 − line 7 + line 5 + line 8a) / (line 3 − line 6 + line 8c) | |
| 11 | Netted figure, only with line 9 = (line 2 − line 7 + line 5 + line 8a − line 8b) / (line 3 − line 6 + line 8c); otherwise "not netted" | |
| 12 | Result: line 11 if signed, else line 10, vs 40%; binding loan(s); headroom | |
| 13 | STOPs / unconfirmed items | |

## 3. Worked synthetic example (invented numbers, not firm figures)

Booked (line 2 / line 3): debt 70, value 200, ratio 35.00%. Each bullet is a separate test from that booked base.

- **Cash-out refi of one property** (old loan 20 is booked in line 2; new loan face 24). Line 5 = 0 (no other pending loans; the new loan goes on line 8a only), line 8a = 24, line 8b = 20, line 8c = 0. Gross (line 10): (70 + 24) / 200 = 94 / 200 = 47.00%, flagged. With the old loan's payoff letter attached and Gabriel's in-turn sign-off echoed ("netted 20.0, old loan, payoff letter dated"), netted (line 11): (70 + 24 − 20) / 200 = 74 / 200 = 37.00%, pass. Without the sign-off the answer stays 47.00%. Listing the new loan on line 5 as well would have read (70 + 24 + 24) / 200 = 59.00%: that is the double count the line-5 exclusion prevents.
- **Signed PSA selling an asset worth 30 that carries a loan of 10** (a re-read with no new loan: line 8a = 0). Line 6 = 30; the loan of 10 stays in line 2 until the payoff document arrives: 70 / (200 − 30) = 70 / 170 = 41.18%, flagged (the unprojected 35.00% would have understated it). After the payoff document (line 7 = 10): (70 − 10) / 170 = 60 / 170 = 35.29%.
- **Signed acquisition, asset 20 with an assumed loan 8, not yet booked.** Its own test: line 8a = 8, line 8c = 20: (70 + 8) / (200 + 20) = 78 / 220 = 35.45%, pass. A LATER test of a different loan lists the assumed loan on line 5 (8) with no own value for it: (70 + 8) / 200 = 39.00% before the later loan's own face is added, until the acquisition is booked.
- **Two such pending acquisitions** on a later test read (70 + 16) / 200 = 43.00%, flagged, though the true post-close ratio is 86 / 240 = 35.83%. That over-flag is the intended cost of the conservative rule; the remedy is the document trail, not a lower figure.

## 4. Traps (check each by hand)

Learned from the adversarial review of an unlanded register implementation; the case figures are that review's synthetic cases.

1. **Stale share.** A closing that raises Oxford's share of the collateral (a JV buy-out from 50% to 100%) must be weighted at the POST-close share. Counting an assumed loan of 6.0 at the old 50% (3.0) while the value side is already at 100% lowered the numerator with no payoff (36.67% pass vs a true 41.67% flag). Weight loan and asset at the same, final share.
2. **JV buy-out and other pending debt.** Before testing a buy-out, list every OTHER pending loan on that asset; each must also be weighted at the post-buy-out share. Otherwise the buy-out credits 100% of the value while the other loan still counts at half (27.00% vs a true 44.00%). If two events touch the same asset, sequence them: finish one, then test the other.
3. **Re-testing a signed item.** Once a PSA or loan is signed, a later change is a NEW test with the old one explicitly closed or withdrawn by Gabriel. A re-test must not restore an asset that a signed sale removed, and must not drop a leg the signed deal carried; both lowered the figure in review (52.5% to 42.0%, and a 40.00% pass where 50.00% flagged).
4. **Unknown or mistyped ids.** A sale or paydown aimed at an asset or loan id that does not exist in the workbook does nothing and silently passes (40.00% vs 48.00%). Match every id to the live workbook by eye (address, entity, loan number), not by memory.
5. **Unsecured and parent-level loans** have no collateral share to cross-check. A typed share below the workbook share on an upsize hid the increase (15.00% pass vs 50.00% flag). Use the workbook share for booked loans; change it only with a document.
6. **Re-keyed booking.** When the workbook books a closed deal under a new loan or asset id, the pending entry and the booked entry both exist for a while. Remove the pending entry only when the booked one is verified against the closing document, never merely because both exist; otherwise value is double counted (40.00% vs a true 41.00%).
7. **Amortization and commitments.** The workbook does not show commitments; do not infer undrawn availability or a "reduction" from a balance that has fallen. A lower booked balance counts; a higher committed amount counts too, but only from the loan document.
8. **Whitespace-only or "looks signed" evidence.** A sign-off or document link that is blank or invisible text is not a document. If you cannot open it, it does not count.

## 5. Sources and status

- Governor and conventions: acquisition-underwriting STAGE 2.3 Part A (all-cash governor; with-refi line informational), CAPITAL STRUCTURE CONTEXT (two governors, two levels), Calibration Ruling 5 (flag, not kill), UNDERWRITING CONVENTIONS (exit caps; per-property 65% / 1.25x DSCR refi sizing). Hard Invariant 4. Nothing numeric here is new.
- This file is INTERIM. When a pending-debt register lands, it replaces this checklist and every pointer to it is updated in the same change.
