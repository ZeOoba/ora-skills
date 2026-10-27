# INTERIM — Pre-close aggregate-LTV test, run by Gabriel (until a pending-debt register exists)

**INTERIM, until a pending-debt register exists.** The acquisition-underwriting STAGE 2.3 Part A all-cash governor sees only debt booked in the live Master Workbook, so a signed-but-unbooked loan or sale is invisible to it. Until a register exists, Gabriel runs this short, fail-closed test before any loan or sale is signed. Constants unchanged: DSCR 1.25x; aggregate LTV 40% (flag only strictly above); per-property 65%. Flag, never kill (Calibration Ruling 5).

## Rules

1. **Who.** Gabriel runs the test and owns the ledger. A session may prepare the inputs and the arithmetic, but Gabriel computes or confirms the figure, and only Gabriel writes the ledger. One test at a time: Gabriel serialises tests. Immediately before signing, Gabriel enters and saves the event's PENDING row, then the figure is recomputed by reading the LEDGER FIRST and THEN the workbook, by Gabriel or by the preparing session in front of him (the workbook is the live SharePoint Master Workbook only: no mirror, no Notion, no synced copy; record the ledger read time and the workbook's as-of time, its own last-modified time or version; STOP if that as-of time is earlier than the ledger's last-modified time or than the workbook read time on any BOOKED-VERIFIED row; an item booked between the two reads shows as a PENDING item the workbook already shows: a STOP); the event's own row is excluded from the overlap check in rule 5 and is not counted twice. A test ends only when its row is saved. Before signing, Gabriel confirms the listed PENDING rows and the ledger's last-modified time match the file as he last saved it; a mismatch, or a recompute that does not show the event's own saved row, is a STOP. If the event is not signed, Gabriel marks its row WITHDRAWN at once.
2. **Signing question, every time.** Ask Gabriel: "Is any loan of any kind, or any PSA or other agreement that sells, contributes or changes Oxford's share of an asset, signed but not yet booked in the live workbook and NOT on the ledger as PENDING (including a WITHDRAWN row since signed)?" A yes is a STOP until he enters it.
3. **The figure.**
   - Numerator: booked debt at Oxford share from the live workbook (every borrower-side loan, including unsecured and parent-level), plus every PENDING ledger loan at full face, plus the loan under test at full face.
   - Denominator: booked portfolio value at exit cap, Oxford share, minus the value sold under every PENDING sale or share decrease on the ledger (signed or not: a saved row is about to be signed, and a WITHDRAWN row leaves the count) and under the sale being tested (the asset's 100% value at exit cap, as in the denominator, × (share before − share after)); "share before" is the documents' figure, and if it differs from the share the workbook books for that asset, STOP and tell Gabriel. A new acquisition is not a share increase (that term means a JV buy-out): it goes on the ledger only as a LOAN row if it carries a loan, and its value does not count, except the deal under test, for its own test, at its market exit-cap value (as STAGE 2.3).
   - Result: strictly above 40.00% (unrounded; never round down) is **LTV-FLAGGED (portfolio)**: Gabriel signs off or the transaction is not accepted.
4. **No reduction without a document and Gabriel.** A payoff, paydown, retirement, sell-down or share cut is credited only when the live workbook shows THAT item booked (the loan's balance, or the asset's share) and Gabriel marks the ledger row BOOKED-VERIFIED. The ONLY in-test netting: the loan under test's own full payoff of one booked loan, with Gabriel's in-turn sign-off, the figure echoed back, netted at the SMALLER of the payoff letter's principal and that loan's Oxford-share balance in the line-1 workbook read (interest or premium never nets); if the two differ, tell Gabriel (the workbook may be understated). A revolving, delayed-draw or other re-drawable facility nets only if the payoff document also terminates or cancels the commitment; otherwise STOP.
5. **The fence.** The test covers ONLY:
   - (a) one new, refinanced or assumed loan on an asset Oxford owns 100% (or a parent-level loan, or a 100%-owned acquisition) whose share does not change; or
   - (b) a sale or share decrease with no loan (a payoff of the asset's own booked loan from the proceeds is not a loan row; it is not credited until BOOKED-VERIFIED).

   EVERYTHING ELSE is a STOP for Gabriel's manual calculation, counting every loan of the event at full face and removing only documented items: an event with more than one loan; a share increase (buy-out); a share decrease together with a loan; partial-paydown netting or any payoff figure that is not a plain full payoff; a loan on a JV asset (Oxford share below 100%); a cross-collateralised loan; a test that touches a loan or asset already on a PENDING row (including a re-test of a signed loan); any PENDING share increase on the ledger; duplicate or overlapping ledger rows; a PENDING item the workbook already shows; a payoff or paydown of any revolving, delayed-draw, future-funding or holdback facility that is not cancelled; any such facility with an undrawn commitment, whether under test, on the ledger or booked anywhere in the workbook (including one booked before the ledger existed), where the manual calculation counts the full commitment of every such facility at Oxford share; a sale or share decrease whose documented share before differs from the workbook's booked share; an unreadable or inconsistent ledger; a yes to the signing question.
6. **Two bases stay separate.** The STAGE 2.3 governor is the all-cash figure; this test is the separate pre-close test and can sit above it (it counts unsecured and parent-level loans and pending items). Report both; never merge them.
7. **Re-test.** A changed term before signing is re-tested on the final figure; a changed term after signing is a new test (and a fence STOP while the signed row is PENDING).

## Ledger (Gabriel's; sessions never write it)

`C:\Users\Owner\OneDrive - Oxford Capital Partners\Claude_Workspace\01_Workspace\LTV_Pending\LTV_Pending_Ledger.xlsx` (created by Gabriel on first use). One row per signed item: what (LOAN / SALE / SHARE CHANGE) · asset and loan · face (loan) or asset · Oxford share before / after · signed document and date (filled when available) · status PENDING / BOOKED-VERIFIED / WITHDRAWN, with who set it. An item leaves the count only when Gabriel marks it BOOKED-VERIFIED (with the workbook read time and the document showing that item booked) or WITHDRAWN (with the reason; he sets WITHDRAWN on any terminated or failed deal).

## Worksheet (a record only; never read as a source)

Filed in `LTV_Pending\Worksheets\` as `LTVTest_[Property]_[Loan or SALE]_[YYYYMMDD]_[HHMM]_[Code or Cowork]`: a unique name; never overwrite an existing worksheet.

| Line | Entry |
|---|---|
| Header | Date; ledger read time and last-modified time; workbook read time and as-of time (its own last-modified time or version); signing-question answer |
| 1 | Booked debt, Oxford share |
| 2 | Booked value, Oxford share, at exit cap |
| 3 | PENDING ledger loans at full face (listed) |
| 4 | Value sold under PENDING sales / share decreases (listed) |
| 5 | Loan under test, full face; own value (acquisition under test) or own value sold (sale under test) |
| 6 | Netting (rule 4), with Gabriel's sign-off text and time |
| 7 | Result = (1 + 3 + 5 loan − 6) / (2 − 4 + own value − own value sold), vs 40% |
| 8 | STOPs (fence items) and Gabriel's manual calculation, if any |

Example (synthetic; base debt 70, value 200): refi of a booked 20 to 24 reads 94/200 = 47.00% gross and 74/200 = 37.00% netted with Gabriel's sign-off; a signed sale of an asset worth 30 reads 70/170 = 41.18% (flag), and a later loan of 6 reads 76/170 = 44.71%. JV sell-down (debt 78; other value 180; JV asset 40 at 100%, Oxford 50% → 25%): value removed 40 × 0.25 = 10, so 78/190 = 41.05% (flag); reading it as 20 × 0.25 = 5 would give 78/195 = 40.00% (a false pass).

## Cost and residual risk

- Over-flags while items are PENDING (a closed refi over-counts until booked, old balance plus new face, e.g. 94/200 = 47.00%, then STOPs under the fence until BOOKED-VERIFIED; base debt 70, value 200: two pending acquisitions each worth 20 with a loan of 8 leave a ledger baseline of 86/200 = 43.00% for later tests, against a true 86/240 = 35.83%; the second acquisition's own test reads 86/220 = 39.09%).
- Depends on Gabriel entering rows and answering the signing question truthfully; a signing he neither enters nor admits is invisible.
- Fenced shapes (buy-outs, multi-loan events, JV-asset loans, revolving and other undrawn facilities) are manual and unchecked by this procedure. Unverified: whether the live workbook records commitment and drawn balance per facility (Gabriel confirms the debt tab does; if not, every test with any facility STOPs), and how AutoSave affects "the file as he last saved it". While any booked facility has an undrawn commitment, every test STOPs for the manual calculation (a repaid or partly drawn revolver can be redrawn: other debt 60, value 200, commitment 20, new loan 2 is 82/200 = 41.00% at full commitment).
- No signing-time hook exists in the repo: the prompts in `deal-execution`, `disposition-analysis`, `legal-intelligence` and `deal-retirement` are reminders, and the signing question is the backstop. `deal-retirement` step 4b is inert on Cowork while that skill is unpublished there (OI-157).
- Serialisation is Gabriel's discipline: if two sessions prepare tests before either transaction is signed, the combined figure is caught only by the later pre-signing recompute showing the other event's saved row.
