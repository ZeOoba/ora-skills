---
name: "pm-portal-pnl-export"
description: "Use when bulk-downloading historical monthly P&L Excel exports from Yardi Voyager or Rent Manager Owner Web Access for ORA properties, then renaming and merging them."
---

# PM Portal P&L Export

Bulk-pull monthly P&Ls via Claude in Chrome. Downloads require in-turn user confirmation. Never enter passwords; the user signs in and switches properties (switching via the header can log the portal out).

## Yardi Voyager (e.g., 29000 Information Lane)
1. Reports > Financial Reports. Confirm property code in the Property field.
2. Report Type = "12 Month Statement" (monthly columns; Report Columns is greyed out on other types). Book = Cash. Account Tree = cashflow (income/expense layout; confirm with user if they use a different P&L tree).
3. Period From/To as MM/YYYY. Windows are 12 months ending in the To month; walk backward in 12-month blocks (e.g., 10/2025-09/2026, 10/2024-09/2025 ...). ~10 exports cover ~10 years.
4. Per window: triple-click To, type; triple-click From, type; click Display; zoom to verify column headers; click Excel (button greys while downloading); wait ~3s.
5. Field coordinates at 1456x836 viewport: To (437,198), From (333,198), Excel (1109,179), Display (1110,210). Re-verify with a screenshot each session.
6. Native select dropdowns do not render in screenshots; cycle with Down key or type the first character of an option.

## Rent Manager Owner Web Access
1. No monthly-column option: one export per month. Separation Method has no monthly choice.
2. Cash basis; uncheck "Collapse all parent accounts"; output format Excel.
3. Dates must be typed MM/DD/YYYY with slashes (ctrl+a, BackSpace first). Set To before From when moving forward.
4. One month per tool call (browser_batch above ~15 actions times out; Yardi tolerates ~7).
5. A green check on Run Report means the run completed.

## Extension failure modes
- "failed in the extension" on a Yardi tab: get_page_text may still work; try a fresh tab, site access "On all sites".
- "Tab not in group": user must re-attach the side panel to the tab.

## Post-processing
Files download with default names lacking property/period. Rename to YYYY-MM-DD_[Property]_PnL_[Period]_v01.xlsx under an /outputs/ subfolder, never delete (move to /archive/), then merge per property into one workbook (xlsx skill) with one tab per period or a consolidated monthly grid. Run the 16-point QC gate before presenting.