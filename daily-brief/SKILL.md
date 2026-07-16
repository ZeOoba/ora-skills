---
name: daily-brief
description: 'Oxford Realty Advisors daily morning intelligence brief. Covers CRE news, industrial transactions, market rates, portfolio watch, ops tip, reading list, CRE law/regulatory watch, shallow bay case study, and competitive intelligence. Use when the user says: daily brief, news, morning brief, market update, CRE news, what''s happening today, what should I know. v2.7 (2026-07-16)'
---

You are generating the Oxford Realty Advisors daily intelligence brief. Execute all 9 sections in sequence and present as a structured report. Target length: concise but complete.

---

## OUTPUT FORMAT

# ORA Daily Brief — \[DAY\], \[MONTH DATE, YEAR\] — \[TIME\]

## 1. CRE NEWS

\[2-4 items\]

## 2. TRANSACTION ALERT

\[2-3 items\]

## 3. MARKET PULSE

\[Rate snapshot\]

## 4. PORTFOLIO WATCH

\[Operational flags\]

## 5. OPS TIP

\[One actionable suggestion\]

## 6. READING LIST

\[5 articles with 1-line summaries\]

## 7. LAW & REGULATORY WATCH

\[New or revised laws/regulations affecting CRE\]

## 8. SHALLOW BAY CASE STUDY

\[1 operator case study from a real company website\]

## 9. COMPETITIVE INTELLIGENCE

\[Edge information for shallow bay / Mid-Atlantic / Midwest\]

---

## SECTION 0 — PRE-FLIGHT SCHEMA INTEGRITY CHECK (Patch 7, v2.2 — added 2026-04-27)

Before generating any brief content, run this 60-second integrity probe. The check exists because Section 4b/4c depend on the Tenant Database schema, and a deletion of any required property in Notion would otherwise fail the daily brief silently.

**Procedure:**

1. Call `notion-fetch` with `id="collection://b12f4cfd-a995-4755-8341-6435ae8173b4"` (Tenant Database data source ID — NOT the wrapper ID `8dbbaec0...`).

2. **Happy path (fetch succeeds):**
   - Verify the schema contains at minimum these required properties: `Tenant Name` (title), `Lease Status` (select), `AR Balance` (number), `Lease Expiration` (date), `Property Address` (select).
   - Verify the rollups `Interaction Count` (count) and `Last Interaction Date` (latest_date) are present and target `collection://3417d600-eace-497b-b30a-16df4ef00d2e`.
   - If all checks pass: continue silently to Section 1. Do NOT mention the probe in brief output. Do NOT email. Daily success is silent.

3. **Failure path (fetch returns HTTP 400 / validation_error / any error, OR a required property is missing):**
   - This is a real corruption signal — not the wrapper-ID routing quirk (resolved 2026-04-27, see Database ID Map). The data source ID does not error on routing alone.
   - **Step A:** Post a Notion comment on the Operations Hub page `32b6ecd8-9e59-81f2-b329-df3fd0e25062` with the exact error payload, timestamp, and a link to the Database ID Map (https://www.notion.so/34f6ecd89e59811aa961f21fd2680744).
   - **Step B:** Send an alert email via Outlook COM — the SOLE send path (Composio retired 2026-06-11; there is NO fallback). Run via Desktop Commander `start_process`:
     - `powershell -ExecutionPolicy Bypass -File "C:\Users\Owner\.claude\scheduled-tasks\_shared\send-via-outlook.ps1" -To "ggoldberg@oxfordra.net" -Subject "[ALERT] Tenant DB schema integrity failure — [today's date]" -BodyFile "<path to HTML body file>" -BodyFormat html`
     - No cc. Alerts are automated outputs → ggoldberg@oxfordra.net ONLY (routing canon 2026-06-10; the cc-Eric exception applies solely to the Daily Brief email itself).
     - Body: HTML with error code/message, request ID, timestamp, missing-property names if applicable, and recommendation to inspect Notion UI.
     - On non-zero exit: retry once, then record the send failure in the Step A Notion comment — do NOT halt the brief.
   - **Step C:** Continue with the brief. Section 4b/4c will use the graceful-degradation pattern (Patch 4) automatically. Sections 1, 2, 3, 5, 6, 7, 8, 9 are unaffected.

4. **Idempotency:** This probe runs every brief cycle. If the same failure recurs across multiple days, the daily emails will repeat — that is intentional. Suppress duplicate-day comments on the Operations Hub by checking for an existing same-day integrity-failure comment before posting (skip if already present).

**Why this lives here:** A separate 5 AM scheduled task was the original design but cannot be created from inside a scheduled-task session. Folding the probe into the 6 AM brief gives the same single-day alert window with one fewer moving part.

---

## SECTION 1 — CRE NEWS

> Geographic scope is governed by `target-markets.json` (v1.0+, bundled into this skill's package as of 2026-07-09 — master copy at repo root `ora-skills/target-markets.json`). Keep the list below in parity with that file's clusters + acceptable_states.

Search the last 24 hours for significant industrial/shallow-bay news in:

- OH (Columbus, Cincinnati, Cleveland, Dayton)
- MD (Baltimore Metro, DC Metro/Northern Virginia, I-270 Corridor)
- IN (Indianapolis Metro)
- MO/KS (Kansas City Metro)
- WI (Madison)
- MI (Grand Rapids) — entry/beachhead target, added 2026-05-30
- VA (Richmond) — entry/beachhead target, added 2026-05-30
- IA (Des Moines) — entry/beachhead target, added 2026-05-30
- TN (pipeline/watch market)

Source priority: [REBusinessOnline.com](http://REBusinessOnline.com), [ConnectCRE.com](http://ConnectCRE.com), [GlobeSt.com](http://GlobeSt.com), Commercial Observer, CoStar (if accessible), local business journals.

Filter for: new development announcements, vacancy changes, major lease signings (&gt;50K SF), investment sales, policy/zoning changes, port/logistics/e-commerce demand trends.

Format: \[Source\] \[Location\]: \[Headline\]. \[1-sentence relevance to ORA.\]

---

## SECTION 2 — TRANSACTION ALERT

Search for industrial sale transactions matching ORA criteria:

- Sub-$10M total consideration
- Shallow-bay, flex, office-warehouse product type
- Target markets: OH, MD, IN, MO, KS, WI (Columbus, Cincinnati, Baltimore/DC, Indianapolis, Kansas City, Madison) + entry-phase MI (Grand Rapids), VA (Richmond), IA (Des Moines); TN watch
- Multi-tenant preferred; sub-50,000 SF per building preferred

Include when available: Price, SF, price/SF, cap rate, buyer, seller, broker. Sources: LoopNet recent sales, CoStar comps, REBusinessOnline, Crexi recent closings. Flag with ⚠️ any deal that would have passed ORA's investment screen.

Format: \[Address\], \[City State\] | \[SF\] SF | $\[Price\] ($\[$/SF\]) | \[Cap Rate\] | Buyer/Seller

---

## SECTION 3 — MARKET PULSE

**FRED Rates Prologue (Patch 8, v2.3 — 2026-04-28):** Before fetching from treasury.gov, pull authoritative series directly from the FRED CSV API (no API key required for public series). These values are the canonical source — do NOT estimate or fall back to training-data priors.

For each series below, call `web_fetch` on `https://fred.stlouisfed.org/graph/fredgraph.csv?id={SERIES_ID}`. Parse the CSV: iterate from the last row upward and take the first row where the value column is not `"."` (blank placeholder). Extract that row's date and value.

| Rate | FRED Series ID | Notes |
|---|---|---|
| 5-Year Treasury | `DGS5` | Daily, constant maturity |
| 10-Year Treasury | `DGS10` | Daily, constant maturity |
| 30-Day SOFR | `SOFR` | NY Fed / FRED |
| Fed Funds Upper | `DFEDTARU` | FOMC target range upper |
| Fed Funds Lower | `DFEDTARL` | FOMC target range lower |

Label every FRED-sourced value inline with its release date, e.g. *"4.31% — FRED DGS10, 2026-04-24 close."* If a FRED fetch returns HTTP error or all-blank values, fall through to treasury.gov / NY Fed as fallback and mark the cell `[treasury.gov fallback]`. Both FRED and treasury.gov fail → mark `Unavailable as of [time]`.

**Notion-outage mirror fallback (Patch 9, v2.6 — 2026-07-15):** If the FRED CSV fetch and the treasury.gov/NY Fed fallback both fail, or the "Rate Snapshot — Current" Notion page that feeds this section's `rate_status` context (published by `ora-am-brief` Block A) is unreachable at generation time: search Gabriel's mailbox (`outlook_email_search`) for that morning's `ora-health-guard` connector pre-flight email — subject beginning `✅ ORA Connector Pre-Flight — [today YYYY-MM-DD]` or `⚠️ ORA Connector Pre-Flight — [today YYYY-MM-DD]` — and parse the `rate_snapshot` JSON block from the body. Use it for this section's rate table. Carry its `confidence` field through verbatim — it will be exactly `PRIMARY` or `SECONDARY`, never any other value — and label every cell sourced from the mirror `[MIRROR FALLBACK — confidence: PRIMARY|SECONDARY]`. Keep any `n/a` cell in the mirror as `n/a`; never interpolate or estimate a value to fill it. If no such email exists for today, or it also lacks usable data, fall through to the `Unavailable as of [time]` rule above.

Fetch current rates from [treasury.gov](http://treasury.gov), NY Fed SOFR page, CME FedWatch (as secondary confirmation only after FRED prologue above):

RateCurrentChange (30-day)5-Year Treasury\[X.XX%\]\[+/- X bps\]10-Year Treasury\[X.XX%\]\[+/- X bps\]30-Day SOFR\[X.XX%\]\[+/- X bps\]Fed Funds Target\[X.XX–X.XX%\]

Also note: Fed commentary, upcoming FOMC dates, CMBS spread (10-yr AAA) if findable, and significant moves in STAG, PLD, EGP as industrial REIT sentiment proxies.

**Data-as-of caveat (Patch 6, v2.1):** When the brief generates before the Fed H.15 daily print is posted (~4:15 PM ET), Section 3 must show the most recent business-day close and explicitly label it: *"Latest available (Fed H.15 release, [previous business day] close)."* Never fabricate "today's" close.

---

## SECTION 4 — PORTFOLIO WATCH

Execute Notion/HubSpot checks:

4a — Scheduled Tasks: Did overnight tasks run? Any errors or missed executions?

4b — Lease Expirations (Notion Tenant Database):

- Any leases expiring in next 30 days?
- Any expiring 31-90 days with no HubSpot renewal activity? Format: \[Tenant\] | \[Property\] | \[Expiration\] | \[Status\]

4c — Delinquency (last Delinquency Tracker output in Notion):

- Any AR balance &gt; $0? Flag anyone &gt;30 days. Format: \[Tenant\] | \[Property\] | $\[Amount\] | \[Days Outstanding\]

4d — Active Deal Actions (Notion Acquisition Pipeline Tracker):

- Deals with deadline in next 7 days?
- Deals stuck at same stage &gt;14 days with no activity? Format: \[Deal\] | \[Stage\] | \[Next Action\] | \[Deadline\]

If no flags: "✅ No items requiring immediate attention."

**Tenant DB ID routing (Patch 4, v2.1 — corrected 2026-04-27 from initial misdiagnosis):**

The Tenant Database has TWO IDs and **the correct one to use depends on which API you are calling.** This is not a "canonical vs. legacy" distinction — both IDs are correct, just for different surfaces.

| Call type | Use this ID | Why |
|---|---|---|
| `notion-fetch` (this MCP) | **Data source ID:** `b12f4cfd-a995-4755-8341-6435ae8173b4` (or `collection://b12f4cfd-a995-4755-8341-6435ae8173b4`) | Calling fetch on the wrapper returns the misleading `validation_error: "Aggregation property not found in data source"` |
| `notion-update-data-source` | **Data source ID** | Operates at the data-source layer |
| Browser navigation (`notion.so/{id}`) | **Database wrapper ID:** `8dbbaec0-611a-4617-be07-6a77d0d0307a` | The wrapper is what URLs use |
| ~~Composio `NOTION_QUERY_DATABASE_WITH_FILTER` / `NOTION_CREATE_DATABASE_ITEM` / `lease-renewal-pipeline` paginator~~ | **RETIRED 2026-06-11** | Composio connector removed. Route all row queries and CRUD through the Notion MCP (`notion-fetch` / `notion-search` / `notion-create-pages` / `notion-update-page`) using the data source ID. The wrapper ID remains valid only for browser URLs. |

**The misdiagnosis on 2026-04-27 was treating the data source ID as universally "canonical" — it's not. Use the table above.**

**Defensive pattern for Section 4b/4c:**

```
try:
  notion-fetch id=collection://b12f4cfd-a995-4755-8341-6435ae8173b4   # data source ID for fetch
  produce 4b/4c with live schema introspection data
except validation_error("Aggregation property not found"):
  # Should NOT happen with the data source ID. If it does, the failure is real schema corruption.
  insert canonical fallback message:
    "Section 4b/4c degraded — Tenant DB schema corruption detected on data source `b12f4cfd-a995-4755-8341-6435ae8173b4`. Falling back to most recent Lease Expiration Brief."
  notion-search for most recent "Lease Expiration Brief" or "Lease Expiration Dashboard" under Operations Hub.
```

For querying tenant *rows* (not schema), use the Notion MCP (`notion-fetch` on the data source ID, paginating as needed). The former Composio wrapper-ID path is RETIRED (connector removed 2026-06-11) — `lease-renewal-pipeline` requires the same migration.

**Database ID Map** for all ORA databases is maintained in the Knowledge Base sub-page `Database ID Map — v1.0` (created 2026-04-27). Resolve once and cache when adding new databases.

**4b Notion-vs-Workbook cross-check (Patch 10, v2.7 — 2026-07-16):** Notion Tenant DB's `Lease Expiration` field has a documented history of data-quality defects from its original March 2026 import (duplicate rows, phantom rows, stale/wrong fields — partially remediated 2026-07-12, but field-level date accuracy was never itself audited). Confirmed 2026-07-16: this section reported Chesapeake Brands, LLC and Stone Crest Counters LLC both expiring 2026-07-31 — both wrong (Notion carried the identical incorrect date on both rows, a data-entry defect, not two independent errors); the real expirations per the Master Workbook are 2027-03-31 and 2028-07-31 respectively. Meanwhile J&R Enterprises genuinely does expire 2026-07-31 but had no value in Notion at all, so this section silently omitted it. Both Notion rows were corrected 2026-07-16, but the underlying gap in this section's method is what let it happen and could recur for any other tenant. Before reporting a lease-expiration date sourced from Notion in 4b:
- If `C:\Users\Owner\oxford-command-center\data\snapshots\portfolio.json` is reachable from the current run surface, read its `leases` array (each entry has `company`/`tenantName`, `propertyKey`, `unit`, `leaseEnd`) and match by **property + unit + tenant contact/company, not tenant name alone** — several Tenant DB tenants share near-identical names, and matching on name alone risks pairing the wrong record. `meta.asOf`/`meta.source` in that file document its vintage; it is Master Workbook-derived, which CLAUDE.md designates the firm's source of record for firm figures.
- If the matched Workbook lease date **disagrees** with Notion's, or one source has a date the other lacks: report **both** values in the 4b row with a `⚠ DISCREPANCY` tag, rather than presenting Notion's figure alone as settled. Do not silently prefer one source over the other in the brief text — flag it for Gabriel.
- If `portfolio.json` is unreachable from this run surface (a known Cowork-vs-Code cross-surface gap — do not treat this as an error to retry), report the Notion-sourced figure as-is but append the one-line caveat: "Notion Tenant DB has a documented history of Lease Expiration data errors — not cross-checked against the Workbook this run." Do not fail or skip the section over this.
- This cross-check does not extend to 4c/4d — those aren't implicated in the 2026-07-16 finding.

**Notion-outage mirror fallback (Patch 9, v2.6 — 2026-07-15):** If Notion is unreachable for this section — Section 0's pre-flight probe failed, or any of the live 4a–4d queries above error out — search Gabriel's mailbox for the same `ora-health-guard` connector pre-flight email described in Section 3's fallback and parse its `portfolio_watch` JSON block (keyed `4a`/`4b`/`4c`/`4d`). Use it in place of the live queries and tag the whole section `[MIRROR FALLBACK]`. Apply these producer-documented caveats rather than presenting the mirror as live current data:
- The block reflects state as of 05:15 ET that morning, not live at 06:00 — state this explicitly.
- `4b` and `4c` may carry `null` — their producers are retired/stale (the Lease Expiration Dashboard refresh was retired 2026-06-09) — present as "not currently tracked," not as a fresh zero-flags result.
- `4d` is a directional read only (deadline/stuck-stage snapshot, not confirmed live) — label it as such.
- If `portfolio_watch` itself is `null` in the mirror email (Notion was already down at 05:15 when the mirror was captured), Section 4 has no fallback available today — state plainly "Section 4 unavailable — Notion down at both 05:15 and 06:00 checkpoints" rather than fabricating content or silently dropping the section.

---

## SECTION 5 — OPS TIP

Generate one actionable suggestion for improving ORA's software automation, file organization, or operational workflow. Rotate through these topic domains (do not repeat on consecutive days):

1. Zapier — new automation (specify trigger → filter → action)
2. HubSpot — workflow, property, or view for pipeline visibility
3. Notion — database improvement, formula, or view
4. QuickBooks Desktop — report, memorized transaction, or class structure improvement (manual access via SharePoint export; no live MCP)
5. PM Platforms — Rent Manager, AppFolio, or Yardi feature to leverage
6. Document management — naming convention, folder structure, or template
7. Claude / AI — a script or automation buildable in one session

Format: Topic: \[Domain\] | Suggestion: \[1-2 sentences\] | Effort: \[Low/Medium/High\] | Time saved: \[hrs/month\]

---

## SECTION 6 — READING LIST

Identify 5 articles Gabriel should read today based on ORA's goals:

- Portfolio growth (acquisitions, market entry, deal sourcing)
- Operational excellence (PM technology, tenant management, accounting automation)
- Technology for RE (PropTech, API integrations, platform building)
- Finance/capital markets (interest rates, debt, REIT activity)
- Business strategy (family office structure, generational wealth, compounding)

Prioritize: acquisition opportunities, market data with actionable implications, operational best practices for 140+ tenant portfolios, technology replacing current SaaS stack.

Format per article: \[#\]. \[Article Title\] — \[Publication\] \[URL\] \[One sentence: why relevant to ORA specifically\]

---

## SECTION 7 — LAW & REGULATORY WATCH

Search for new or revised federal, state, or local laws/regulations enacted or proposed in the last 7 days that affect commercial real estate, specifically industrial/flex property owners.

Search terms to use:

- "commercial real estate law 2026" + \[state: OH, MD, IN, MO, WI, KS, TN\]
- "industrial zoning regulation" OR "warehouse zoning" + target states
- "landlord tenant law commercial" + target states
- "CMBS regulation" OR "commercial mortgage regulation" 2026
- "1031 exchange" legislation updates
- "opportunity zone" regulation changes
- "environmental regulation industrial" + EPA + 2026
- "property tax assessment commercial" + target states
- "ADA commercial real estate" updates
- Federal: FASB lease accounting, SEC real estate disclosure rules, CFPB commercial lending

For each item found, include:

- \[Jurisdiction\] \[Law/Rule Name or Bill Number\]: \[What changed\]. \[Impact on ORA — 1 sentence.\]
- Status: \[Enacted / Proposed / In Committee / Effective Date\]

If nothing material found in last 7 days, note the last significant regulatory change relevant to ORA and its current status.

Sources: [congress.gov](http://congress.gov), state legislature websites, NAR legislative tracker, BOMA regulatory updates, law firm CRE client alerts (JLL Law, DLA Piper, Ballard Spahr).

---

## SECTION 8 — SHALLOW BAY CASE STUDY

Each day, identify and summarize one real-world case study, project spotlight, or operational lesson from a real shallow-bay or multi-tenant flex industrial operator's website.

Source from actual company websites (not aggregators). Rotate through these operators daily:

- Brennan Investment Group ([brennanllc.com](http://brennanllc.com))
- Basis Industrial ([basisindustrial.com](http://basisindustrial.com))
- STAG Industrial ([stagindustrial.com/investors](http://stagindustrial.com/investors))
- Broadstone Net Lease / Broadstone Industrial
- Seagis Property Group ([seagisproperty.com](http://seagisproperty.com))
- Link Logistics ([linklogistics.com/insights](http://linklogistics.com/insights))
- Ares Industrial ([aresindustrialreit.com](http://aresindustrialreit.com))
- Exeter Property Group
- LBA Realty
- Whitebox Real Estate

What to look for on each site: press releases, project spotlights, investor presentations, blog posts, market reports, deal announcements, leasing strategies, development pipelines.

Format: Operator: \[Company Name\] Source URL: \[Direct link to the page\] Topic: \[Acquisition / Development / Leasing / Operations / Capital Markets\] Summary: \[3-4 sentences on what they did, the market, the asset type, and the outcome or thesis\] ORA Takeaway: \[1 sentence — what Gabriel can apply or learn from this specific to ORA's strategy\]

If a company's site yields nothing useful today, move to the next operator on the list.

---

## SECTION 9 — COMPETITIVE INTELLIGENCE

Generate intelligence that gives ORA a specific edge over other shallow-bay buyers and landlords in the Mid-Atlantic (MD, VA, DC) and Midwest (OH, IN, MO, KS, WI) markets. This section must be actionable — not general market commentary.

Run these specific searches:

1. "shallow bay industrial" OR "flex industrial" for sale \[target markets\] — new listings in last 48 hours on Crexi, LoopNet, CoStar that ORA has not yet screened
2. Competitor activity: search "\[Brennan Investment Group OR Basis Industrial OR STAG OR Seagis OR LBA\] acquires" + target markets — any deals announced this week
3. Off-market signals: search for "\[property address\] industrial auction" OR "industrial bankruptcy sale" OR "motivated seller industrial" in target markets
4. Broker intelligence: any new industrial broker hires, team moves, or boutique firm launches in target markets that could affect deal flow to ORA
5. Tenant demand signals: any large employer announcements (expansions, relocations, new facilities) in target markets that will drive warehouse/flex demand in next 12-24 months
6. Zoning/entitlement pipeline: any new industrial park approvals or rezoning actions that will add supply to ORA's target submarkets in 12-24 months — affects exit cap assumptions
7. Lender activity: any new bridge or permanent lenders entering shallow-bay industrial space, or existing lenders tightening terms — affects ORA's acquisition financing options

Format per item: Category: \[Listing / Competitor Move / Off-Market / Broker Intel / Tenant Demand / Supply Pipeline / Lender\] Finding: \[Specific, factual, sourced finding — 2-3 sentences\] ORA Action: \[What to do with this information — call a broker, adjust underwriting, etc.\]

Minimum 3 items; maximum 6. Prioritize items requiring action within 72 hours.

---

## DELIVERY NOTES

- Total brief should take Gabriel &lt;7 minutes to read
- Sections 1-3, 7-9 require web search — execute all searches before generating output
- Section 4 uses Notion/HubSpot MCPs — check those before generating output
- If a rate or item cannot be found, note "Unavailable as of \[time\]" — never fabricate
- Save brief to Notion under the Operations Hub (parent page id `32b6ecd8-9e59-81f2-b329-df3fd0e25062`) with title `Daily Brief — [YYYY-MM-DD]`.

  **Pre-create dedup guard (Patch 3, v2.1):** Before creating a new page, run `notion-search` for the title `Daily Brief — [YYYY-MM-DD]` filtered to the Operations Hub parent. If 0 matches, create. If exactly 1 match, use `notion-update-page command=replace_content` to overwrite. If 2+ matches, create the new canonical page, then retitle older duplicates with prefix `🗑️ ... [DUPLICATE — SUPERSEDED by <new_page_id>]` so the workspace surface is clean.

- When running as a scheduled task: send the HTML brief via Outlook COM — the SOLE send path (v2.5, 2026-06-11):
  1. Write the full HTML brief to a temp file (avoids command-line length limits and quoting issues).
  2. Desktop Commander `start_process`: `powershell -ExecutionPolicy Bypass -File "C:\Users\Owner\.claude\scheduled-tasks\_shared\send-via-outlook.ps1" -To "ggoldberg@oxfordra.net" -Cc "egoldberg@oxfordra.net" -Subject "ORA Daily Brief — [DAY, MONTH DATE YEAR]" -BodyFile "<temp file path>" -BodyFormat html`
  3. The Daily Brief is the SOLE sanctioned cc to egoldberg@oxfordra.net (routing canon 2026-06-10). Every other automated output goes to ggoldberg@oxfordra.net only.
  4. Exit codes: 0 = sent; non-zero → retry once, then flag the failure loudly in the Notion completion row (the automation-health-monitor producer-beacon check catches silent sends) — do NOT halt.

- **Routing (effective 2026-06-11):** Composio was fully RETIRED on 2026-06-11 (connector removed — there is NO Composio fallback). Rube EOL 2026-05-15; Gmail is disabled on the tenant. Outlook COM via `send-via-outlook.ps1` is the only send mechanism. Any remaining `OUTLOOK_SEND_EMAIL`, `COMPOSIO_*`, or `RUBE_*` invocation will hard-fail and must be migrated to the COM script.

---

## CHANGELOG

- **v2.7 (2026-07-16):** Added Patch 10 — Section 4b Notion-vs-Workbook cross-check. Two Notion Tenant DB rows (Chesapeake Brands, LLC; Stone Crest Counters LLC) were found reporting an identical, incorrect 2026-07-31 Lease Expiration (actual: 2027-03-31 and 2028-07-31 per the Master Workbook), while a third tenant genuinely expiring 2026-07-31 (J&R Enterprises) had no Notion value and was silently omitted. Section 4b now cross-references `oxford-command-center\data\snapshots\portfolio.json` by property/unit/contact (not tenant name alone) when reachable, flags any disagreement with `⚠ DISCREPANCY` instead of trusting Notion alone, and caveats the output when the cross-check can't run this session. Companion fix on the ora-pm-ledger (Command Center-sourced) side of this same 2026-07-16 finding.
- **v2.6 (2026-07-15):** Added Patch 9 — Notion-outage mirror fallback for Sections 3 and 4. Implements the contract `ora-health-guard` Block B.3 has emailed every morning since it was written but that this skill never actually consumed: on a Notion read failure at 06:00, Section 3 now uses the health-guard's `rate_snapshot` mirror (carrying its `PRIMARY`/`SECONDARY` `confidence` label through verbatim, `n/a` cells kept as `n/a`, never interpolated) and Section 4 now uses its `portfolio_watch` mirror (tagged `[MIRROR FALLBACK]`, with the 4b/4c null-producer and 4d directional-read caveats preserved) — rather than degrading to a live-fallback attempt or a bare "DATA UNAVAILABLE."
- **v2.5 (2026-06-11):** Composio fully retired (connector removed; Gabriel-ratified 2026-06-11 — no fallback). All sends repointed to Outlook COM via `_shared/send-via-outlook.ps1`: Section 0 Step B alert (now ggoldberg-only per 2026-06-10 routing canon), scheduled-task brief send (keeps the sanctioned cc to egoldberg — the sole exception), Notion ID-routing table (Composio NOTION_* rows retired; row queries via Notion MCP). Description version re-synced with changelog (closes the v2.2-desc/v2.4-changelog drift from the 2026-06-09 skill-text audit). Resolves that audit CRITICAL #1.
- **v2.4 (2026-05-15):** Rube sunset reached — Patch 5 EOL warning superseded; routing bullet rewritten in past tense to reflect Composio Platform as canonical MCP path (itself superseded by v2.5: Composio retired 2026-06-11). Light clarification added that the `tenant-db-schema-integrity` standalone task referenced in v2.2 was never deployed (folded into Section 0 instead).
- **v2.3 (2026-04-28):** Added Patch 8 — FRED Rates Prologue for Section 3. Replaces treasury.gov as the primary rate source with FRED CSV API (fredgraph.csv endpoint, no API key required). Resolves treasury.gov token-cap fetch failures. FRED series: DGS5, DGS10, SOFR, DFEDTARU, DFEDTARL. treasury.gov retained as fallback. Fed Funds table row updated to show DFEDTARU–DFEDTARL range format.
- **v2.2 (2026-04-27 PM):** Added Patch 7 — Pre-flight schema integrity check folded in as Section 0. Replaces the (never-deployed) standalone `tenant-db-schema-integrity` scheduled task (which couldn't be installed from a scheduled-task session). Patch 4 nuance fix: clarified that data source ID is the canonical target only for `notion-fetch` and `notion-update-data-source`, not for Composio query/CRUD tools (which still require the wrapper ID).
- **v2.1 (2026-04-27 AM):** Added Patches 1, 2, 3, 4, 5, 6 — fixes Outlook user_id (P1), separates to/cc (P3), adds Notion dedup pre-create guard (P3), adds Tenant DB graceful degradation (P4), adds Rube EOL migration warning (P1, superseded by v2.4 on sunset day 2026-05-15), adds data-as-of caveat for Section 3 (P6).
- **v2.0:** Initial 9-section structure.
