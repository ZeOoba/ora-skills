# INTERIM — Manual pre-close aggregate-LTV checklist and pending-position ledger (until a pending-debt register exists)

**INTERIM procedure, in force until a pending-debt register exists and replaces it.** Approved by Gabriel 2026-10-26 to land as interim doctrine, then redesigned at his direction 2026-10-26 to use ONE pending-position ledger he owns. It closes the gap that the acquisition-underwriting STAGE 2.3 Part A all-cash governor sees only debt already booked in the live Master Workbook, so a signed-but-unbooked refi, assumed loan, sale or share change is invisible to it. The gap is closed by PROCEDURE: a ledger Gabriel keeps by hand and a per-test worksheet, with no script and no register.

Governor constants are unchanged and are not restated beyond the existing ones: DSCR 1.25x; portfolio-aggregate LTV 40% (flagged only strictly above); per-property 65%. Flag-not-kill: acquisition-underwriting Calibration Ruling 5 — a breach is a flag that needs Gabriel's sign-off, never an automatic block.

## 1. The pending-position ledger (the ONLY source of pending items)

**Location (one, canonical):** `C:\Users\Owner\OneDrive - Oxford Capital Partners\Claude_Workspace\01_Workspace\LTV_Pending\LTV_Pending_Ledger.xlsx` (Claude_Workspace, the free working surface under Hard Invariant 5, alongside `deal-folder-intake`'s `01_Workspace\Deals\` mirror; created by Gabriel on first use). Test worksheets are filed beside it in `LTV_Pending\Worksheets\`. A copy anywhere else is never read and never governs.

**Gabriel owns it. Sessions never write it.** A session that finds a pending item PROPOSES a row in its test output (worksheet line 14); Gabriel enters it. Nothing is discovered from other worksheets, deal folders, the Acquisition Pipeline Tracker or memory: if it is not a ledger row, a test does not count it, which is why each test asks Gabriel the signing question (rule 2).

**One row per pending item:**

| Field | Content |
|---|---|
| Row id | Unique, never reused |
| Kind | `LOAN` · `SALE` · `SHARE-INCREASE` · `SHARE-DECREASE` |
| Asset | Workbook asset id and address |
| Loan id | The loan the row concerns (LOAN; the loan kept on a SALE or SHARE-DECREASE; each loan on the asset for a SHARE-INCREASE) |
| Oxford share before / after | Percent, before and after the event |
| Face | LOAN: full face incl. documented undrawn, at the after share |
| Asset value removed | SALE and SHARE-DECREASE: value at exit cap × (before share − after share) |
| Value and loans restated | SHARE-INCREASE: incremental value at exit cap × (after − before share), and each booked or pending loan on the asset × (after − before share) |
| Credit (optional) | Gabriel-entered only, with its document: the booked balance a LOAN replaces (refi payoff, modification, surviving mortgage) or the payoff of the loan a SALE kept |
| Status | `PENDING` · `BOOKED-VERIFIED` · `WITHDRAWN` |
| Signed document | Reference and date (PSA, loan document, amendment, assumption agreement) |
| Entered by / entered at | Gabriel; timestamp |
| BOOKED-VERIFIED evidence | The workbook read time that shows the item booked, and the document that shows it (closing statement, payoff letter, recorded assignment) |

**Status:** a row is entered PENDING when the PSA or loan is signed (Gabriel enters it, then signs; rule 3). It leaves the count ONLY when Gabriel marks it BOOKED-VERIFIED with the workbook read time and the document that shows it booked, or WITHDRAWN. Nothing else removes it: not a CLOSED label, a payoff letter, a closing statement, or a workbook cell that looks updated. Rows are never deleted.

## 2. Rules

1. **Workbook.** Read the live Master Workbook (read order per the firm's source-of-record canon), not a mirror, and not `00_Home!G7` alone. Note the read time. Booked debt counts every borrower-side loan at its Oxford-share balance, including unsecured and parent-level loans, so this figure can sit above the STAGE 2.3 Part A all-cash figure (which reads secured debt as booked); the two are different tests, not a contradiction, and both are reported. Booked value is each asset at its market exit cap (acquisition-underwriting UNDERWRITING CONVENTIONS), Oxford share.
2. **Ledger read and the signing question.** Read the ledger and record its last-modified time, row count and SHA-256 on the worksheet header. Then ask Gabriel: "Any PSA or loan signed since the last ledger entry?" and record his answer. A yes with no row entered is a STOP until he enters it. A ledger that cannot be read is a STOP.
3. **Counting rule: every PENDING row counts at FULL.**
   - LOAN: its full face in the numerator, at the after share. A pending acquisition's value never counts (only its loans do), except the deal under test, for its own test only.
   - SALE: its asset value leaves the denominator from the day the row is entered; its loan stays in the numerator.
   - SHARE-INCREASE: its incremental value AND every booked or pending loan on the asset restated at the after share, in every later test, until BOOKED-VERIFIED.
   - SHARE-DECREASE: treated as a sale (value removed, loan kept).
   - Double count is resolved only by BOOKED-VERIFIED: while a row is PENDING it counts at full even if the workbook already shows its booked counterpart. That over-states; it is flagged, never killed.
4. **Reductions.** No reduction is credited without a document in hand AND Gabriel's entry on the ledger (the row's Credit field). A credit applies only while the loan it reduces still appears in this workbook read at that balance; if the workbook no longer shows it, the credit is not applied and the row is a STOP until Gabriel marks it BOOKED-VERIFIED (a credit must never be taken twice). Likewise a SALE or SHARE-DECREASE whose asset no longer appears in the workbook read is a STOP until he marks it.
5. **In-test netting (the only other path).** The loan under test's own payoff, or for a modification, upsize, assumption or surviving mortgage of a booked loan the booked balance it replaces, nets in the test of that loan only, only against its document, and only with Gabriel's in-turn sign-off. Echo the figure back on the worksheet ("netted: old loan <id>, <amount>, document <name, date>") and record his sign-off text and time. It is never stored on a ledger row as a test result and never carried to a later test or re-test; if any term changes, ask again.
6. **Loan under test appears once.** It is on worksheet line 8a only. If it already has a PENDING ledger row (a signed loan being re-tested), that row is not also counted on line 4: line 8a takes the LARGER of the row's face and the tested face until Gabriel withdraws or replaces the row. A booked loan under test that is restated by a share increase is on line 8a at the after share and excluded from line 8d.
7. **Share increases only on line 8c/8d.** When the test raises Oxford's share of a booked asset (a JV buy-out), line 8c is the incremental value only and line 8d restates every OTHER booked or pending loan on it at the after share. Neither is ever negative; a share decrease is a sale (SHARE-DECREASE row).
8. **Re-read before signature.** Immediately before Gabriel signs off on the result AND immediately before the loan or PSA is signed (after Gabriel has entered its row), re-read the ledger and the workbook. If the ledger's last-modified time, row count or hash, or the workbook, changed since the test's read in any way other than this loan's own new row, re-run the test. A figure computed before that re-read never clears a signature.
9. **Result.** At or below 40% passes; strictly above 40% is **LTV-FLAGGED (portfolio)**. Compare the unrounded figure; never round down. A flag goes to Gabriel with the figure, the binding row(s) or loan(s) and the headroom; he signs off or the loan is not accepted. Never kill.
10. **Two-basis convention stays** (acquisition-underwriting STAGE 2.3 Part A): the STAGE 2.3 governor is the ALL-CASH figure; the IRR model, levered IRR, DSCR and IC memo carry the post-close refi, and the IC memo's with-refi portfolio LTV line stays informational. This checklist is the SEPARATE pre-close test for any refi or any new, assumed or seller-financed loan. Report both numbers; never merge them.
11. **STOP, never zero.** Any step you cannot complete (unreadable ledger or workbook, unknown id, missing document, unanswered signing question, a credit or sale whose item is no longer in the workbook) is a STOP to Gabriel, not a zero and not a pass.

## 3. Who proposes rows, and when

| Trigger | Action |
|---|---|
| `debt-management` Refinance Evaluation step 5 / Term-Sheet Redline step 0 (incl. via `legal-intelligence`) | Runs the test; proposes a LOAN row (with any Credit and SHARE-INCREASE row the loan implies) on worksheet line 14. Gabriel enters it when he signs, before signing; rule 8 re-read follows. |
| `deal-execution` Workflow 2A Step 5 (inbound PSA accepted) and Workflow 2B Output (CLEAR TO SEND of the execution version) | Prompts Gabriel: on execution of a PSA that sells an asset, enter a SALE (or SHARE-DECREASE) row; on execution of a loan-bearing PSA, enter its LOAN row (after its own step-5 test). There is no dedicated signing-time step in `deal-execution`, so Gabriel enters the row when he signs, and every test's signing question (rule 2) catches a missed entry. |
| `deal-execution` Post-Closing item 11 | Prompts Gabriel, once the live workbook shows the closing, to mark the row BOOKED-VERIFIED with that workbook read time and the closing document. Until he does, the row keeps counting. |
| `disposition-analysis` Step 6 | A SELL or 1031 ruling proposes a SALE row; it counts only once the PSA is signed and Gabriel has entered it. An unsigned sale is not counted. |

## 4. Worksheet (one per test; the test RECORD, never a source)

Filed in `LTV_Pending\Worksheets\` as `LTVNettingWorksheet_[Property]_[LoanId]_[MMDDYYYY]_v##` (a new file per test; never overwrite).

| # | Line | Entry |
|---|---|---|
| H | Ledger read time, last-modified time, row count, SHA-256; workbook read time; Gabriel's answer to the signing question | |
| 1 | Booked debt, Oxford share, all borrower-side loans | |
| 2 | Booked value, Oxford share, at exit cap | |
| 3 | Booked ratio (line 1 / line 2); compare to `00_Home!G7` and explain any gap | |
| 4 | PENDING LOAN rows at full face (after share), excluding the loan under test's own row; list row ids; total | |
| 5 | PENDING SALE and SHARE-DECREASE rows: asset value removed; list row ids; total | |
| 6a | PENDING SHARE-INCREASE rows: incremental value; total | |
| 6b | PENDING SHARE-INCREASE rows: restated loans (after − before share), excluding the loan under test; total | |
| 7 | Gabriel-entered Credits on PENDING rows, each with its document and only while the loan still appears in the line-1 read; total | |
| 8a | Loan under test: full face incl. documented undrawn, at after share (the larger of row and tested face, rule 6) | |
| 8b | Loan under test: own payoff, or the booked balance it replaces, and its document | |
| 8c | Own value: pending acquisition under test, its underwritten value; share increase under test, the incremental value; else 0 | |
| 8d | Share increase under test: other booked or pending loans on the asset × (after − before share); else 0 | |
| 9 | Gabriel's in-turn netting sign-off (text, time) and the echoed figure | |
| 10 | Gross = (line 1 + line 4 + line 6b − line 7 + line 8a + line 8d) / (line 2 − line 5 + line 6a + line 8c) | |
| 11 | Netted, only with line 9 = (gross numerator − line 8b) / same denominator; otherwise "not netted" | |
| 12 | Result: line 11 if signed, else line 10, vs 40%; binding row(s); headroom | |
| 13 | STOPs; pre-signature re-read times and result (rule 8) | |
| 14 | Proposed ledger row(s) for Gabriel to enter | |

## 5. Worked examples (invented numbers, not firm figures)

Base unless stated: booked debt 70, value 200 (35.00%).

| Case | Worksheet entries | Figure |
|---|---|---|
| Cash-out refi, own test (old 20 booked, new 24) | 8a 24, 8b 20 | gross 94/200 = 47.00% flag; netted with payoff letter and sign-off 74/200 = 37.00% pass |
| Modification of a booked loan, 20 → 24 | 8a 24, 8b 20 (executed amendment) | 47.00% gross; 37.00% netted |
| Signed sale entered (asset 30, loan 10 kept) | line 5 = 30 | 70/170 = 41.18% flag |
| Later loan 6 after that sale row | line 5 = 30, 8a 6 | 76/170 = 44.71% flag (a test that missed the sale would read 76/200 = 38.00%) |
| Refi closed but row not yet BOOKED-VERIFIED (row 24 PENDING; Gabriel entered the old loan 20's payoff as a Credit); later loan 7 | line 4 = 24, line 7 = 20, 8a 7 | 81/200 = 40.50% flag; without the Credit 101/200 = 50.50%; a dropped "CLOSED" row would have read 77/200 = 38.50% |
| Sale closed, row PENDING, its loan 10 payoff entered as a Credit; later loan 9 / later loan 18 | line 5 = 30, line 7 = 10, 8a 9 / 18 | 69/170 = 40.59% flag / 78/170 = 45.88% flag |
| Recap 100% → 50% (asset 40, entity loan 10) | SHARE-DECREASE row, line 5 = 20, loan kept | 70/180 = 38.89%; crediting the halved loan before a document would read 65/180 = 36.11% (barred) |
| Two concurrent tests, loans A 6 and B 6 | A alone 8a 6; B's rule-8 re-read after Gabriel enters A's row: line 4 = 6, 8a 6 | 76/200 = 38.00%, then 82/200 = 41.00% flag |
| Re-test at 22 while the signed row of 24 is PENDING | 8a = max(24, 22) = 24, row not on line 4 | 94/200 = 47.00% until Gabriel withdraws the 24 row; then 92/200 = 46.00% (counting both would be 116/200) |
| Assumed loan 8 on a pending acquisition (asset 20) | own test 8a 8, 8c 20; later test line 4 = 8 | 78/220 = 35.45% own test; 78/200 = 39.00% later |
| Two pending acquisitions, loans 8 + 8 | line 4 = 16 | 43.00% flag, though the true post-close ratio is 86/240 = 35.83%: the intended cost of the conservative rule |

**JV buy-outs (share increase, rule 7):**

| Case | Worksheet entries | Figure |
|---|---|---|
| A: base 60/150, JV asset at 50% = 20 (100% = 40), no mortgage; buy-out loan 12 | 8a 12, 8c 20, 8d 0 | 72/170 = 42.35% flag (whole value on 8c would read 72/190 = 37.89%, a false pass) |
| B: base 55/170 incl. JV mortgage 20 booked at 50% (10); parent loan 12 | 8a 12, 8c 20, 8d 10 | 77/190 = 40.53% flag (without 8d 67/190 = 35.26%) |
| B carry-over: once B is signed (rows LOAN 12 and SHARE-INCREASE: value 20, mortgage +10), a later loan 6 | line 4 12, 6a 20, 6b 10, 8a 6 | 83/190 = 43.68% flag (dropping the restated mortgage would read 73/190 = 38.42%) |
| C: base 60/170 incl. JV mortgage 20 booked at 50% (10); the surviving mortgage is the loan under test | 8a 20, 8b 10, 8c 20, 8d 0 (excluded, rule 6) | gross 80/190 = 42.11%; netted with the executed assumption or consent and sign-off 70/190 = 36.84% pass (counting it on 8d too: 90/190 and 80/190) |
| C carry-over: SHARE-INCREASE row (value 20, mortgage +10), later loan 6 | 6a 20, 6b 10, 8a 6 | 76/190 = 40.00% pass (not strictly above 40%) |

## 6. Traps (check each by hand)

Learned from the adversarial reviews of an unlanded register implementation and of this checklist's drafts; the case figures are synthetic.

1. **Stale share.** Weight every loan and the asset at the same, final share (rows SHARE-INCREASE; lines 6a/6b, 8c/8d). Counting an assumed loan at the old 50% while the value is at 100% read 36.67% pass vs a true 41.67% flag.
2. **Other debt on a JV asset.** Every booked or pending loan on an asset whose share rises is restated, in its own test (8d) and in every later test (6b), until BOOKED-VERIFIED. Missing one read 27.00% vs a true 44.00%. If two events touch the same asset, sequence them.
3. **Re-testing a signed item.** A changed term after signature is a new test; the signed row keeps counting at its face until Gabriel withdraws or replaces it (rule 6).
4. **Unknown or mistyped ids.** A row aimed at an asset or loan id that is not in the workbook is a STOP, never a silent zero (40.00% vs 48.00%). Match ids by address, entity and loan number.
5. **Unsecured and parent-level loans** have no collateral share to cross-check. Use the workbook share for booked loans; change it only through a ledger row Gabriel entered (15.00% pass vs 50.00% flag in review).
6. **Re-keyed booking.** When the workbook books a closed item under a new id, the PENDING row and the booked entry both exist until Gabriel marks the row BOOKED-VERIFIED. That over-states; it never under-states, and a Credit whose loan has left the workbook is a STOP (rule 4).
7. **Amortization and commitments.** Do not infer undrawn availability or a reduction from a fallen balance. Undrawn counts only from the loan document; Original Principal is not a commitment; undocumented undrawn counts as 0 and is written "undrawn not documented".
8. **Whitespace-only or "looks signed" evidence.** A sign-off, ledger entry or document link that is blank, invisible or cannot be opened does not count.

## 7. Cost of the design

- **Over-flagging while rows are PENDING.** Every pending row counts at full until Gabriel marks it BOOKED-VERIFIED, so tests flag more often than the true post-close ratio warrants (two pending acquisitions: 43.00% vs 35.83%). The remedy is the document trail and Gabriel's ledger entry, never a lower figure.
- **Dependence on Gabriel's entries.** The ledger is only as complete as his entries. A test cannot see a signing he has not entered, which is why every test asks the signing question and STOPs on an unreadable ledger or an unentered signing. A signing he forgets to mention is still invisible: the residual risk of an interim manual procedure.

## 8. Sources and status

- Governor and conventions: acquisition-underwriting STAGE 2.3 Part A (all-cash governor; with-refi line informational), CAPITAL STRUCTURE CONTEXT (two governors, two levels), Calibration Ruling 5 (flag, not kill), UNDERWRITING CONVENTIONS (exit caps; per-property 65% / 1.25x DSCR refi sizing). Hard Invariant 4. Nothing numeric here is new.
- This file is INTERIM. When a pending-debt register lands, it replaces this checklist and the ledger, and every pointer to it is updated in the same change.
