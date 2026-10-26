# INTERIM — Pre-close aggregate-LTV test, run by Gabriel (until a pending-debt register exists)

**INTERIM, until a pending-debt register exists.** The acquisition-underwriting STAGE 2.3 Part A all-cash governor sees only debt booked in the live Master Workbook, so a signed-but-unbooked loan or sale is invisible to it. Until a register exists, Gabriel runs this short, fail-closed test before any loan or sale is signed. Constants unchanged: DSCR 1.25x; aggregate LTV 40% (flag only strictly above); per-property 65%. Flag, never kill (Calibration Ruling 5).

## Rules

1. **Who.** Gabriel runs the test and owns the ledger. A session may prepare the inputs and the arithmetic, but Gabriel computes or confirms the figure, and only Gabriel writes the ledger. One test at a time: Gabriel serialises tests. Immediately before signing, the figure is recomputed from a fresh workbook read and the current ledger, by Gabriel or by the preparing session in front of him.
2. **Signing question, every time.** Ask Gabriel: "Is any signed PSA, loan, or other agreement that sells, contributes or changes Oxford's share of an asset NOT yet on the ledger?" A yes is a STOP until he enters it.
3. **The figure.**
   - Numerator: booked debt at Oxford share from the live workbook (every borrower-side loan, including unsecured and parent-level), plus every PENDING ledger loan at full face, plus the loan under test at full face.
   - Denominator: booked portfolio value at exit cap, Oxford share, minus the value sold under every signed sale or share decrease on the ledger and under the sale being tested (the asset's booked value × the fraction of Oxford's share sold). A pending acquisition's value does not count, except the deal under test, for its own test.
   - Result: strictly above 40.00% (unrounded; never round down) is **LTV-FLAGGED (portfolio)**: Gabriel signs off or the transaction is not accepted.
4. **No reduction without a document and Gabriel.** A payoff, paydown, retirement, sell-down or share cut is credited only when the live workbook shows it and Gabriel marks the ledger row BOOKED-VERIFIED. The ONLY in-test netting: the loan under test's own full payoff of one booked loan, with Gabriel's in-turn sign-off, the figure echoed back, capped at that loan's principal at Oxford share (a payoff letter's interest or premium never nets).
5. **The fence.** The test covers ONLY:
   - (a) one new, refinanced or assumed loan on an asset Oxford owns 100% (or a parent-level loan, or a 100%-owned acquisition) whose share does not change; or
   - (b) a sale or share decrease with no loan.

   EVERYTHING ELSE is a STOP for Gabriel's manual calculation, counting every loan of the event at full face and removing only documented items: an event with more than one loan; a share increase (buy-out); a share decrease together with a loan; partial-paydown netting or any payoff figure that is not a plain full payoff; a loan on a JV asset (Oxford share below 100%); a cross-collateralised loan; a test that touches a loan or asset already on a PENDING row (including a re-test of a signed loan); any PENDING share increase on the ledger; duplicate or overlapping ledger rows; a PENDING item the workbook already shows; an unreadable or inconsistent ledger; a yes to the signing question.
6. **Two bases stay separate.** The STAGE 2.3 governor is the all-cash figure; this test is the separate pre-close test and can sit above it (it counts unsecured and parent-level loans and pending items). Report both; never merge them.
7. **Re-test.** A changed term before signing is re-tested on the final figure; a changed term after signing is a new test (and a fence STOP while the signed row is PENDING).

## Ledger (Gabriel's; sessions never write it)

`C:\Users\Owner\OneDrive - Oxford Capital Partners\Claude_Workspace\01_Workspace\LTV_Pending\LTV_Pending_Ledger.xlsx` (created by Gabriel on first use). One row per signed item: what (LOAN / SALE / SHARE CHANGE) · asset and loan · face (loan) or asset · Oxford share before / after · signed document and date · status PENDING / BOOKED-VERIFIED / WITHDRAWN, with who set it. An item leaves the count only when Gabriel marks it BOOKED-VERIFIED (with the workbook read time and the document showing it booked) or WITHDRAWN (with the reason; he sets WITHDRAWN on any terminated or failed deal).

## Worksheet (a record only; never read as a source)

Filed in `LTV_Pending\Worksheets\` as `LTVTest_[Property]_[Loan or SALE]_[YYYYMMDD]_[HHMM]`:

| Line | Entry |
|---|---|
| Header | Date; workbook read time; ledger last-modified time; signing-question answer |
| 1 | Booked debt, Oxford share |
| 2 | Booked value, Oxford share, at exit cap |
| 3 | PENDING ledger loans at full face (listed) |
| 4 | Value sold under signed sales / share decreases (listed) |
| 5 | Loan under test, full face; own value (acquisition under test) or own value sold (sale under test) |
| 6 | Netting (rule 4), with Gabriel's sign-off text and time |
| 7 | Result = (1 + 3 + 5 loan − 6) / (2 − 4 + own value − own value sold), vs 40% |
| 8 | STOPs (fence items) and Gabriel's manual calculation, if any |

Example (synthetic; base debt 70, value 200): refi of a booked 20 to 24 reads 94/200 = 47.00% gross and 74/200 = 37.00% netted with Gabriel's sign-off; a signed sale of an asset worth 30 reads 70/170 = 41.18% (flag), and a later loan of 6 reads 76/170 = 44.71%.

## Cost and residual risk

- Over-flags while items are PENDING (a closed refi keeps counting until BOOKED-VERIFIED; two pending acquisitions read 43.00% against a true 35.83%).
- Depends on Gabriel entering rows and answering the signing question truthfully; a signing he neither enters nor admits is invisible.
- Fenced shapes (buy-outs, multi-loan events, JV-asset loans) are manual and unchecked by this procedure.
- No signing-time hook exists in the repo: the prompts in `deal-execution`, `disposition-analysis` and `legal-intelligence` are reminders, and the signing question is the backstop.
