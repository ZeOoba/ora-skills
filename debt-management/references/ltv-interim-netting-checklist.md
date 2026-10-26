# INTERIM — Manual pre-close aggregate-LTV checklist and pending-position ledger (until a pending-debt register exists)

**INTERIM procedure, in force until a pending-debt register exists and replaces it.** Approved by Gabriel 2026-10-26 to land as interim doctrine, then redesigned at his direction 2026-10-26 to use ONE pending-position ledger he owns. It closes the gap that the acquisition-underwriting STAGE 2.3 Part A all-cash governor sees only debt already booked in the live Master Workbook, so a signed-but-unbooked refi, assumed loan, sale or share change is invisible to it. The gap is closed by PROCEDURE: a ledger Gabriel keeps by hand and a per-test worksheet, with no script and no register.

Governor constants are unchanged and are not restated beyond the existing ones: DSCR 1.25x; portfolio-aggregate LTV 40% (flagged only strictly above); per-property 65%. Flag-not-kill: acquisition-underwriting Calibration Ruling 5 — a breach is a flag that needs Gabriel's sign-off, never an automatic block.

## 1. The pending-position ledger (the ONLY source of pending items)

**Location (one, canonical):** `C:\Users\Owner\OneDrive - Oxford Capital Partners\Claude_Workspace\01_Workspace\LTV_Pending\LTV_Pending_Ledger.xlsx` (Claude_Workspace, the free working surface under Hard Invariant 5, alongside `deal-folder-intake`'s `01_Workspace\Deals\` mirror; created by Gabriel on first use). Test worksheets are filed beside it in `LTV_Pending\Worksheets\`. A copy anywhere else is never read and never governs.

**Gabriel owns it. Sessions never write it.** A session that finds a pending item PROPOSES a row in its test output (worksheet line 14); Gabriel enters it and saves the file. Nothing is discovered from other worksheets, deal folders, the Acquisition Pipeline Tracker or memory: if it is not a ledger row, a test does not count it, which is why every read asks Gabriel the signing question (rule 2).

**One row per pending item; one event may have several rows (a buy-out's SHARE-INCREASE and LOAN rows share an Event id):**

| Field | Content |
|---|---|
| Row id / Event id | Row id unique, never reused; Event id shared by the rows of one signed transaction |
| Kind | `LOAN` · `SALE` · `SHARE-INCREASE` · `SHARE-DECREASE` |
| Asset | Workbook asset id and address (a pending acquisition: its address, marked not booked) |
| Loan id | LOAN: the new or surviving loan; for a refi, modification or surviving mortgage also the booked loan it replaces |
| Oxford share before / after | Percent, before and after the event |
| Face | LOAN: full face incl. documented undrawn, at the after share |
| Stored amounts (reference only) | SALE / SHARE-DECREASE: asset value removed; SHARE-INCREASE: incremental value and each restated booked loan. Re-derived from the current workbook at every test (rule 5) |
| Credit (optional) | Gabriel-entered only, with its document: the booked balance a LOAN replaces (refi payoff, modification, surviving mortgage) or the payoff of the loan a SALE kept |
| Status | `PENDING` · `BOOKED-VERIFIED` · `WITHDRAWN` |
| Signed document | Reference and date (PSA, loan document, amendment, assumption agreement) |
| Entered by / entered at | Gabriel; timestamp |
| BOOKED-VERIFIED evidence | The workbook read time that shows the item booked, and the document that shows it (closing statement, payoff letter, recorded assignment) |

**Status:** a row is entered PENDING when the PSA or loan is signed (Gabriel enters and saves it, then signs; rule 8). It leaves the count ONLY when Gabriel marks it BOOKED-VERIFIED with the workbook read time and the document that shows it booked, or WITHDRAWN. Nothing else removes it: not a CLOSED label, a payoff letter, a closing statement, or a workbook cell that looks updated. Rows are never deleted.

## 2. Rules

1. **Workbook.** Read the live Master Workbook (read order per the firm's source-of-record canon), not a mirror, and not `00_Home!G7` alone. Record its read time and file modified time or version id. Booked debt counts every borrower-side loan at its Oxford-share balance, including unsecured and parent-level loans, so this figure can sit above the STAGE 2.3 Part A all-cash figure (which reads secured debt as booked); the two are different tests, not a contradiction, and both are reported. Booked value is each asset at its market exit cap (acquisition-underwriting UNDERWRITING CONVENTIONS), Oxford share.
2. **Ledger read and the signing question, at EVERY read.** Read the ledger and record its last-modified time, row count and SHA-256 on the worksheet header. At every read and every re-read, ask Gabriel: "Is any signed PSA or loan NOT yet on the ledger?" and record each answer with its time. A yes without a matching row is a STOP until he enters it. A ledger that cannot be read is a STOP.
3. **Counting rule: every PENDING row of another event counts at FULL.**
   - LOAN: its full face in the numerator, at the after share. A pending acquisition's value never counts (only its loans do), except the deal under test, for its own test only.
   - SALE: its asset value leaves the denominator from the day the row is entered; its loans stay in the numerator.
   - SHARE-INCREASE: its incremental value, and every booked loan on the asset restated at the after share, in every later test, until BOOKED-VERIFIED. A loan that has its own PENDING LOAN row at the after share is NOT also restated (it is on line 4 already).
   - SHARE-DECREASE: treated as a sale (value removed, loans kept).
   - Double count is resolved only by BOOKED-VERIFIED: while a LOAN row is PENDING it counts at full even if the workbook already shows the loan. That over-states; it is flagged, never killed.
4. **Reductions.** No reduction is credited without a document in hand AND Gabriel's entry on the ledger (the row's Credit field). A Credit on another event's row is taken on line 7 once, at the smaller of the stored Credit and the loan's current Oxford-share balance, and only while that loan still appears in this workbook read; if it no longer appears, the row is a STOP until Gabriel marks it BOOKED-VERIFIED (a credit is never taken twice).
5. **Stored amounts are references, not figures.** Lines 5, 6a, 6b and 7 are re-derived from the CURRENT workbook read (current value × share change; current balance × share change; current balance). Where the stored amount differs, use the more conservative of the two (the larger for lines 5 and 6b, the smaller for lines 6a and 7) and tell Gabriel the row needs updating.
6. **The event under test is counted once, only on lines 8a–8d.** Its own ledger rows (LOAN, SHARE-INCREASE, Credit), if Gabriel has already entered them for a pre-signature re-run or a re-test, are excluded from lines 4, 6a, 6b and 7. Its own row's Credit is never taken on line 7: the replaced balance nets only on line 8b with Gabriel's in-turn sign-off (rule 9). On a re-test of a signed loan, line 8a takes the LARGER of the row's face and the tested face until Gabriel withdraws or replaces the row.
7. **Share increases only on lines 8c/8d.** When the test raises Oxford's share of a booked asset (a JV buy-out), line 8c is the current incremental value and line 8d restates every OTHER booked loan on it at the after share (excluding the loan under test, which is on 8a at the after share, and any loan with its own PENDING LOAN row). Neither is ever negative; a share decrease is a sale (SHARE-DECREASE row).
8. **Re-read before signature.** Immediately before Gabriel signs off on the result, and again immediately before the loan or PSA is signed: Gabriel enters this event's row(s) and saves the ledger; the session re-reads the ledger, asks the signing question again (rule 2), and re-reads the workbook and recomputes lines 1–2. The re-read must CONTAIN this event's own row(s), matching line 14 by row id and face; if not, the read is stale or unsaved: STOP. If anything else changed (ledger rows, hash, workbook), re-run the test. A figure computed before that re-read never clears a signature.
9. **In-test netting (the only other reduction path).** The loan under test's own payoff, or for a modification, upsize, assumption or surviving mortgage of a booked loan the booked balance it replaces (line 8b), nets in the test of that loan only, only against its document, and only with Gabriel's in-turn sign-off. Echo the figure back on the worksheet ("netted: old loan <id>, <amount>, document <name, date>") and record his sign-off text and time. It is never stored as a test result and never carried to a later test or re-test; if any term changes, ask again.
10. **Result.** At or below 40% passes; strictly above 40% is **LTV-FLAGGED (portfolio)**. Compare the unrounded figure; never round down. A flag goes to Gabriel with the figure, the binding row(s) or loan(s) and the headroom; he signs off or the loan is not accepted. Never kill.
11. **STOP, never zero.** Any step you cannot complete (unreadable ledger or workbook, unknown id, missing document, unanswered signing question, a stale re-read, a non-positive denominator) is a STOP to Gabriel, not a zero and not a pass.
12. **Already-booked effects.** A PENDING SALE, SHARE-DECREASE or SHARE-INCREASE whose asset is gone from the workbook, or whose booked share no longer equals the row's before share, is a STOP until Gabriel marks it BOOKED-VERIFIED (otherwise its effect would be taken twice).
13. **One event per asset and loan.** If two events (two ledger events, or a ledger event and the event under test) touch the same asset or the same loan, STOP: Gabriel sequences them (marks one BOOKED-VERIFIED or withdraws it) before the test proceeds.
14. **Two-basis convention stays** (acquisition-underwriting STAGE 2.3 Part A): the STAGE 2.3 governor is the ALL-CASH figure; the IRR model, levered IRR, DSCR and IC memo carry the post-close refi, and the IC memo's with-refi portfolio LTV line stays informational. This checklist is the SEPARATE pre-close test for any refi or any new, assumed or seller-financed loan. Report both numbers; never merge them.

## 3. Who proposes rows, and when

| Trigger | Action |
|---|---|
| `debt-management` Refinance Evaluation step 5 / Term-Sheet Redline step 0 (incl. via `legal-intelligence`) | Runs the test; proposes the event's LOAN row (with any Credit and SHARE-INCREASE row it implies) on worksheet line 14. Gabriel enters and saves it before signing; the rule-8 re-read follows. At the loan's closing, prompts Gabriel to mark the row BOOKED-VERIFIED once the workbook shows it. |
| `deal-execution` Workflow 2A Step 5 (inbound PSA accepted) and Workflow 2B Output (CLEAR TO SEND of the execution version) | Prompts Gabriel: on execution of a PSA that sells an asset, enter a SALE (or SHARE-DECREASE) row; on execution of a loan-bearing PSA, enter its LOAN row (after its own step-5 test). There is no dedicated signing-time step in `deal-execution`, so Gabriel enters the row when he signs, and every read's signing question (rule 2) catches a missed entry. |
| `deal-execution` Post-Closing item 11 | Prompts Gabriel, once the live workbook shows the closing, to mark the row(s) BOOKED-VERIFIED with that workbook read time and the closing document. Until he does, the row keeps counting. |
| `disposition-analysis` Step 6 | A SELL or 1031 ruling proposes a SALE row; it counts only once the PSA is signed and Gabriel has entered it. At the sale's closing, prompts Gabriel to mark it BOOKED-VERIFIED once the workbook shows it. An unsigned sale is not counted. |

## 4. Worksheet (one per test; the test RECORD, never a source)

Filed in `LTV_Pending\Worksheets\` as `LTVNettingWorksheet_[Property]_[LoanId]_[MMDDYYYY]_[SessionTag]_v##`, created exclusively: never overwrite; if the name exists, take the next `v##` and repeat the rule-8 re-read.

| # | Line | Entry |
|---|---|---|
| H | Ledger read time, last-modified time, row count, SHA-256; workbook read time and modified time or version id; each signing-question answer with its time | |
| 1 | Booked debt, Oxford share, all borrower-side loans (recomputed at every re-read) | |
| 2 | Booked value, Oxford share, at exit cap (recomputed at every re-read) | |
| 3 | Booked ratio (line 1 / line 2); compare to `00_Home!G7` and explain any gap | |
| 4 | PENDING LOAN rows of OTHER events at full face (after share); row ids; total | |
| 5 | PENDING SALE and SHARE-DECREASE rows of other events: value removed, the larger of stored and current (rule 5); total | |
| 6a | PENDING SHARE-INCREASE rows of other events: incremental value, the smaller of stored and current; total | |
| 6b | Same rows: restated booked loans (after − before share), the larger of stored and current, excluding the loan under test and any loan with its own PENDING LOAN row; total | |
| 7 | Credits on rows of OTHER events: the smaller of stored and current balance, only while the loan still appears in the line-1 read; total | |
| 8a | Loan under test: full face incl. documented undrawn, at after share (the larger of its own row's and the tested face, rule 6) | |
| 8b | Loan under test: own payoff, or the booked balance it replaces, and its document | |
| 8c | Own value: pending acquisition under test, its underwritten value; share increase under test, the current incremental value; else 0 | |
| 8d | Share increase under test: other booked loans on the asset × (after − before share), excluding loans with their own PENDING LOAN row; else 0 | |
| 9 | Gabriel's in-turn netting sign-off (text, time) and the echoed figure | |
| 10 | Gross = (line 1 + line 4 + line 6b − line 7 + line 8a + line 8d) / (line 2 − line 5 + line 6a + line 8c) | |
| 11 | Netted, only with line 9 = (gross numerator − line 8b) / same denominator; otherwise "not netted" | |
| 12 | Result: line 11 if signed, else line 10, vs 40%; binding row(s); headroom | |
| 13 | STOPs; pre-signature re-read times, own-row check and result (rule 8) | |
| 14 | Proposed ledger row(s) for Gabriel to enter (row id, event id, kind, face, Credit) | |

## 5. Worked examples (invented numbers, not firm figures)

Every figure below was computed by an executable model of rules 1–13 as written. Base unless stated: booked debt 70, value 200 (35.00%).

| Case | Worksheet entries | Figure |
|---|---|---|
| Cash-out refi, own test (old 20 booked, new 24) | 8a 24, 8b 20 | gross 94/200 = 47.00% flag; netted with payoff letter and sign-off 74/200 = 37.00% pass |
| Modification of a booked loan, 20 → 24 | 8a 24, 8b 20 (executed amendment) | 47.00% gross; 37.00% netted |
| Refi re-run after Gabriel entered the own row (new 32, Credit 20) | own row excluded from 4 and 7; 8a 32, 8b 20 | gross 102/200 = 51.00%; netted 82/200 = 41.00% flag (taking the Credit on line 7 as well would read 62/200 = 31.00%) |
| Signed sale entered (asset 30, loan 10 kept) | line 5 = 30 | 70/170 = 41.18% flag |
| Later loan 6 after that sale row | line 5 = 30, 8a 6 | 76/170 = 44.71% flag |
| Sale row 30, asset re-marked to 36 in the workbook (other debt 64); later loan 6 | line 5 = max(30, 36) = 36 | 70/170 = 41.18% flag (the stored 30 would read 70/176 = 39.77%) |
| Refi row 24 PENDING with the old loan 20's payoff as a Credit; later loan 7 | line 4 24, line 7 20, 8a 7 | 81/200 = 40.50% flag; without the Credit 101/200 = 50.50% |
| Sale row PENDING with its loan 10's payoff as a Credit; later loan 9 / 18 | line 5 30, line 7 10, 8a 9 / 18 | 69/170 = 40.59% / 78/170 = 45.88% flag |
| Recap 100% → 50% (asset 40, loan 10; base 70/200) | SHARE-DECREASE row, line 5 = 20, loan kept | 70/180 = 38.89% |
| Two concurrent tests, loans A 6 and B 6 | A alone; B's rule-8 re-read after Gabriel enters and saves A's row | 76/200 = 38.00%, then 82/200 = 41.00% flag |
| Re-test at 22 while the signed row of 24 is PENDING | 8a = max(24, 22), own row not on line 4 | 94/200 = 47.00% until Gabriel withdraws the 24 row; then 92/200 = 46.00% |
| Assumed loan 8 on a pending acquisition (asset 20) | own test 8a 8, 8c 20; later test line 4 = 8 | 78/220 = 35.45% own test; 78/200 = 39.00% later |
| Two pending acquisitions, loans 8 + 8 | line 4 = 16 | 43.00% flag, though the true post-close ratio is 86/240 = 35.83%: the intended cost of the conservative rule |

**JV buy-outs (share increase, rules 3, 6 and 7):**

| Case | Worksheet entries | Figure |
|---|---|---|
| A: base 60/150, JV asset 40 at 50%, no mortgage; buy-out loan 12 | 8a 12, 8c 20 | 72/170 = 42.35% flag; the same on the pre-signature re-run with the own rows entered (counting the own SHARE-INCREASE row on 6a would read 72/190 = 37.89%) |
| B: base 55/170 incl. JV mortgage 20 booked at 50% (10); parent loan 12 | 8a 12, 8c 20, 8d 10 | 77/190 = 40.53% flag |
| B carry-over: rows LOAN 12 and SHARE-INCREASE (value 20, mortgage +10); later loan 6 | line 4 12, 6a 20, 6b 10, 8a 6 | 83/190 = 43.68% flag |
| C: base 60/170 incl. JV mortgage 20 booked at 50% (10); the surviving mortgage is the loan under test | 8a 20, 8b 10, 8c 20, 8d 0 | gross 80/190 = 42.11%; netted 70/190 = 36.84% pass; the same on the re-run with own rows entered (own SHARE-INCREASE on 6a would read 80/210 = 38.10%) |
| C carry-over: rows SHARE-INCREASE (value 20) and LOAN (mortgage at 100% = 20, Credit 10 for the booked 10); later loan 6 | line 4 20, 6a 20, 6b 0 (the mortgage has its own LOAN row), line 7 10, 8a 6 | 76/190 = 40.00% pass (not strictly above); without the Credit 86/190 = 45.26% |
| Restated loan drawn up: B-type row stored +10, JV mortgage now 32 at 100% (other debt 52); later loan 6 | 6b = max(10, 16) = 16 | 90/190 = 47.37% flag (the stored 10 would read 84/190 = 44.21%) |
| Asset marked down: row stored value 20, JV asset now 30 at 100% (base 67/145); later loan 6 | 6a = min(20, 15) = 15 | 73/160 = 45.62% flag (the stored 20 would read 73/165 = 44.24%) |

## 6. Traps (check each by hand)

The percentages in traps 1–6 are quoted from the earlier adversarial reviews; their inputs are not reproduced here.

1. **Stale share.** Weight every loan and the asset at the same, final share (SHARE-INCREASE rows; lines 6a/6b, 8c/8d). Counting an assumed loan at the old 50% while the value is at 100% read 36.67% pass vs a true 41.67% flag.
2. **Other debt on a JV asset.** Every booked loan on an asset whose share rises is restated, in its own test (8d) and in every later test (6b), until BOOKED-VERIFIED, unless it has its own LOAN row. Missing one read 27.00% vs a true 44.00%.
3. **Re-testing a signed item.** A changed term after signature is a new test; the signed row keeps counting at its face until Gabriel withdraws or replaces it (rule 6).
4. **Unknown or mistyped ids.** A row aimed at an asset or loan id that is not in the workbook is a STOP, never a silent zero (40.00% vs 48.00%). Match ids by address, entity and loan number.
5. **Unsecured and parent-level loans** have no collateral share to cross-check. Use the workbook share for booked loans; change it only through a ledger row Gabriel entered (15.00% pass vs 50.00% flag).
6. **Re-keyed booking.** When the workbook books a closed item under a new id, a PENDING LOAN row and the booked entry both exist until Gabriel marks the row BOOKED-VERIFIED. That over-states; a sale, share change or Credit whose effect the workbook already shows is a STOP (rules 4 and 12) (40.00% vs a true 41.00%).
7. **Amortization and commitments.** Do not infer undrawn availability or a reduction from a fallen balance. Undrawn counts only from the loan document; Original Principal is not a commitment; undocumented undrawn counts as 0 and is written "undrawn not documented".
8. **Whitespace-only, unsaved or "looks signed" evidence.** A sign-off, ledger entry or document link that is blank, invisible, unsaved or cannot be opened does not count.

## 7. Cost of the design and known gaps

- **Over-flagging while rows are PENDING.** Every pending row counts at full until Gabriel marks it BOOKED-VERIFIED, so tests flag more often than the true post-close ratio warrants (two pending acquisitions: 43.00% vs 35.83%). The remedy is the document trail and Gabriel's ledger entry, never a lower figure.
- **Dependence on Gabriel's entries.** The ledger is only as complete and current as his entries and saves. A test cannot see a signing he has not entered, which is why every read asks the signing question and STOPs on an unreadable or stale ledger. A signing he forgets and also answers "no" to is still invisible: the residual risk of an interim manual procedure.
- **No closing-time trigger outside a session.** A loan or sale that closes when no session is running is not prompted for BOOKED-VERIFIED. This fails closed (the row keeps counting at full, over-stating); the workaround is Gabriel's weekly review of PENDING rows against the workbook.

## 8. Sources and status

- Governor and conventions: acquisition-underwriting STAGE 2.3 Part A (all-cash governor; with-refi line informational), CAPITAL STRUCTURE CONTEXT (two governors, two levels), Calibration Ruling 5 (flag, not kill), UNDERWRITING CONVENTIONS (exit caps; per-property 65% / 1.25x DSCR refi sizing). Hard Invariant 4. Nothing numeric here is new.
- This file is INTERIM. When a pending-debt register lands, it replaces this checklist and the ledger, and every pointer to it is updated in the same change.
