---
name: "pm-portal-delinquency-export"
description: "Bulk-pull point-in-time delinquency/aged-receivables reports as of the 15th of each month (trailing 24 months) from each property manager portal via Claude in Chrome."
---

# PM Portal Delinquency Export

Sister skill to pm-portal-pnl-export. Pulls a delinquency snapshot **as of the 15th of each month** for the trailing 24 months, per property, from each property manager's portal, via Claude in Chrome. Delinquency is a point-in-time report: one export per as-of date (no multi-column option exists).

## Standing rules
- Downloads require in-turn user confirmation. Never enter passwords; the user signs in and switches properties (switching via the header can log the portal out).
- Reports contain tenant names and balances: internal only. Never place on an external surface, never paste into email to a counterparty, never publish as an artifact.
- Never fabricate. The property -> property manager -> platform -> property code mapping comes from the live ORA Master Workbook (SharePoint) first, then Notion Tenant DB (8dbbaec0) / Ops Hub (32b6ecd8). If a property's PM or code is not found, ask; do not guess. Known from the P&L skill: 29000 Information Lane = Yardi Voyager.
- Read-only reports only. Do not post, adjust, or write off anything in the PM system.

## Step 0: Build the pull matrix (before opening a browser)
1. Roster: properties in scope (user-named, or all PM-managed properties), each with PM, platform, property code.
2. Date list: the 15th of each month for the 24 months ending with the most recent 15th on or before today. As of 2026-10-05 that is 10/15/2024 through 09/15/2026 (24 dates). Recompute from today's date every run; never include a future 15th.
3. Weekend/holiday 15ths: still use the 15th as the as-of date (calendar snapshot). Do not shift.
4. Present the matrix (properties x 24 dates = N exports) and the estimated call count, then proceed. Group by platform, then property, to minimize property switching.

## Yardi Voyager
1. Reports > Receivables > Delinquency (confirm exact menu path and report name on first use; Yardi installs vary). Confirm property code in the Property field.
2. Parameters: As-Of / Aging date = the 15th (MM/DD/YYYY); Post Month = the month of the as-of date; include all tenant statuses the user specifies (default: Current + Past, ensure Past tenants with balances are not dropped); aging buckets 0-30 / 31-60 / 61-90 / 90+; Display > Excel.
3. HISTORICAL-ACCURACY CHECK (mandatory, first export of each property): Yardi delinquency reports can reflect current ledger state (later receipts/adjustments applied) rather than a true historical snapshot, depending on post-month and as-of settings. Run one date where the user has a known snapshot (prior saved report or month-end AR in the close package) and tie out total delinquent. If it does not tie, STOP and tell the user the as-of method is not a true snapshot; propose the alternative (per-tenant ledger / receipts-as-of rebuild) rather than delivering misleading history. [UNVERIFIED until first run]
4. Native select dropdowns do not render in screenshots; cycle with Down key or type the first character of an option. Re-verify field coordinates with a screenshot each session; do not reuse P&L skill coordinates blindly (different form).
5. Batch limit ~7 actions per call; wait ~3s after Excel click (button greys while downloading).

## Rent Manager Owner Web Access (krg.owa.rentmanager.com)
Path verified 2026-10-05: Reports > Delinquency. Backing call: krg.owaapi.rentmanager.com/ReportsView/viewreport?report=85.
1. The header selector shows the logged-in property (e.g. 16623 - Fairground Village Center), but the report's "Properties to Include" multi-select lists every property on the login (observed: 2000 Zettler Rd, 2012 Zettler Rd, 2800 Banwick Rd, 384 Old Morrison Rd, 4595 E 5th Ave; all selected by default). With "Run Properties separately" checked, ONE export per as-of date covers all selected properties, so the Rent Manager matrix is 24 exports total. Map each property to its ORA entity from the Master Workbook before delivery; do not infer.
2. Form settings: As of Date = the 15th; Charges to Include = All selected; Detail or Summary = Detail; Tenants to Include = All (options All / Current / Past; the default Current drops past tenants with balances); Run Properties separately = checked; Keep Rent Charges Separate = checked; Include Prospects = default; balance and delinquent-days filters blank.
3. Output dropdown (bottom right) defaults to PDF; options PDF / CSV / HTML / Text / Excel. Select Excel (it does not persist across page reloads; confirm before each session).
4. Date entry: click the As of Date field, ctrl+a, BackSpace, type MM/DD/YYYY with slashes. Reset the date before every run.
5. Run Report turns green with a check mark when the export completes; the file lands in the browser's default Downloads folder with a generic name. Rename per Post-processing.
6. One as-of date per tool call. browser_batch failed repeatedly in the extension on this form: use individual calls, and click the submit button by element ref (find/read_page) when a coordinate click errors.
7. Verify every run: call read_network_requests after clicking Run (start tracking before the first run). A 503 on the viewreport call or a missing green check means NO file was produced. Observed 2026-10-05: 503 twice in a row on 11/15/2024. Retry at most twice, then stop and report; retry later or ask the user to check portal status.
8. Apply the same HISTORICAL-ACCURACY CHECK as Yardi (tie one date to a known snapshot) before delivering history. [UNVERIFIED]
9. On the first successful file, confirm the column layout (aging buckets may not appear in Detail mode) and record it here.

## Other PM platforms
If a property sits on a portal not listed (AppFolio, Buildium, bespoke owner portal, emailed PDF reports), do not improvise. Report it to the user, state what is needed (login, report name, whether history is available), and add the procedure to this skill after a supervised first run.

## Extension failure modes
- "failed in the extension" on a Yardi tab: get_page_text may still work; try a fresh tab, site access "On all sites".
- "failed in the extension" on browser_batch (Rent Manager): fall back to single calls.
- "Tab not in group": user must re-attach the side panel to the tab.
- After 2-3 failed attempts on the same action: stop and report what was tried.

## File location caveat
Browser downloads land on the USER's computer (Downloads), not in the cloud workspace. Unless the desktop bridge is linked (remote-devices tools present), the session cannot see, rename or merge them. If not linked, ask the user to link a folder or attach the files, or give an exact rename table (as-of date -> target filename).

## Post-processing
1. Files download with default names lacking property/date. Rename immediately to `YYYY-MM-DD_[Property]_Delinquency_AsOf-YYYYMMDD_v01.xlsx` (leading date = run date) under an /outputs/ subfolder. Never delete; superseded files move to /archive/.
2. Per property, merge the 24 snapshots into one workbook (xlsx skill): a Summary tab (rows = as-of dates; columns = total delinquent, 0-30 / 31-60 / 61-90 / 90+, # delinquent tenants, % of billed rent where billing is available) plus one tab per as-of date, or a long-format Detail tab (as-of date, tenant, suite, bucket, balance). Add a portfolio roll-up across properties.
3. Tenant-level trend flags: tenants delinquent 3+ consecutive snapshots; balances that age across buckets; balances that disappear (paid vs written off, unknown unless the report shows it; label [UNKNOWN] rather than infer).
4. Reconcile each month's total to AR in the monthly close package where available; list variances.
5. Run the 16-point QC Gate before presenting. Mirror to the SharePoint Claude workspace when the destination is known. Deliver to the connected folder / outputs path.
6. Do not email results. If the user later requests distribution, internal routing is ggoldberg@oxfordra.net only.

## Completion report
State: properties covered, dates pulled vs 24 expected, any gaps (with reason), tie-out results, files written. End with <=5 workflow optimization bullets (e.g., standing request to PMs for scheduled monthly delinquency email on the 15th to replace manual pulls).