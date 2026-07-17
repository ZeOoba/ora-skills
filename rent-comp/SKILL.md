---
name: rent-comp
description: "Automated rent comparable and sale comparable research for Oxford Realty Advisors target markets. Use this skill whenever the user mentions: rent comps, comparable rents, market rent, asking rent, comparable sales, sale comps, transaction comps, cap rate comps, price per SF comps, market analysis, rental rate research, or any request to find comparable lease rates or property sales in a specific submarket. Also trigger when underwriting a deal and market comps are needed. v1.1 (2026-07-08: file-naming citation repointed from the superseded single 2026-05-14 standard to the ratified three-schema doctrine)"
---

# Automated Rent & Sale Comparable Research

Systematic comparable data collection for Oxford Realty Advisors acquisition underwriting and portfolio management.

---

## 1. RENT COMP RESEARCH WORKFLOW

When asked for rent comps in a specific submarket:

### Step 1 — Multi-Source Search
Execute these searches using web_search:

```
"[submarket] industrial warehouse lease rate per SF [current year]"
"[submarket] flex space asking rent [current year]"
"site:loopnet.com industrial for lease [city] [state]"
"site:crexi.com industrial for lease [city] [state]"
"[submarket] industrial market report [current year]" (for brokerage reports from CBRE, JLL, Cushman, Colliers, NAI)
"[city] [state] shallow bay industrial available"
```

### Step 2 — Data Extraction
Use web_fetch to extract actual asking rents from listing pages. For each listing, capture:
- Property address
- Total SF and available SF
- Asking rent ($/SF/year and lease type — NNN, MG, Gross)
- Clear height
- Year built
- Loading (dock doors, drive-in doors)
- Listing broker and date
- Source URL

### Step 3 — Comp Table Assembly
Compile into a standardized comp table:

| Address | SF | Asking Rent/SF | Lease Type | Clear Height | Year Built | Dock Doors | Drive-In | Source | Date |
|---------|-----|---------------|------------|-------------|-----------|-----------|----------|--------|------|

### Step 4 — Statistical Analysis
Calculate and present:
- **Median rent/SF** (preferred over mean for small samples)
- **Mean rent/SF** with standard deviation
- **Range** (low to high)
- **Interquartile range** (25th to 75th percentile)
- **Trend direction** (based on YoY comparison if data available)
- **Sample size** and data quality assessment

### Step 5 — Normalization
Adjust comps for comparability:
- Convert all rents to NNN equivalent (subtract estimated CAM/insurance/tax for gross or MG leases)
- Note clear height premium/discount (16'+ commands premium over 12'-14')
- Note vintage adjustment (post-2000 vs. pre-1990)
- Note size adjustment (larger spaces typically lower $/SF)

---

## 2. SALE COMP RESEARCH WORKFLOW

When asked for sale comps:

### Step 1 — Multi-Source Search
```
"[submarket] industrial property sold [current year]"
"[submarket] industrial property sold [prior year]"
"site:rebusinessonline.com industrial sale [city]"
"site:connectcre.com industrial sale [city]"
"[city] [state] warehouse sold price per square foot"
"[submarket] industrial investment sale cap rate"
```

### Step 2 — Comp Table Assembly
| Address | SF | Sale Price | Price/SF | Cap Rate | NOI (if known) | Occupancy | Buyer | Seller | Date | Source |

### Step 3 — Analysis
- **Median price/SF** and **mean price/SF**
- **Median cap rate** and range
- **Price/SF by vintage** (pre-1990, 1990-2005, post-2005)
- **Price/SF by size** (sub-25K SF, 25-50K SF, 50-100K SF, 100K+ SF)
- **Trend direction** (compare to 6-12 months prior)

---

## 3. REPLACEMENT COST ANALYSIS

When evaluating basis vs. replacement cost (critical for every Oxford acquisition):

### Step 1 — Component Estimation
| Component | Estimation Method |
|-----------|-------------------|
| **Land cost** | Search "[city] [submarket] industrial land price per acre" or use county assessor land value |
| **Hard costs** | Base: $85-120/SF for tilt-up shallow bay (market-dependent). Search "[city] industrial construction cost per SF [year]" for current data |
| **Soft costs** | 15-20% of hard costs (architecture, engineering, permits, legal) |
| **Developer profit** | 10-15% of total project cost |
| **Financing costs** | 3-5% of total project cost at current rates |

### Step 2 — Calculation
```
Replacement Cost/SF = (Land/SF) + (Hard Costs/SF) + (Soft Costs/SF) + (Dev Profit/SF) + (Financing/SF)
Discount to Replacement = 1 - (Subject Basis/SF ÷ Replacement Cost/SF)
```

### Step 3 — Output
- Present replacement cost breakdown table
- Calculate and highlight discount to replacement cost
- Oxford target: acquire at ≥30% discount to replacement cost
- Flag if subject basis exceeds 80% of replacement cost (thin margin)

---

## 4. MARKET CONTEXT OVERLAY

For every comp set, provide market context:
- Current submarket vacancy rate (from brokerage reports)
- Submarket absorption trend (positive/negative, magnitude)
- New supply pipeline (SF under construction, expected delivery)
- Submarket employment drivers
- Recent notable transactions

---

## 5. OUTPUT FORMATS

### Quick Comps (Default)
Markdown tables in chat with statistical summary and market context.

### Full Comp Report
Use the xlsx skill to produce:
- **Tab 1 — Rent Comps:** Full table with statistical summary
- **Tab 2 — Sale Comps:** Full table with statistical summary
- **Tab 3 — Replacement Cost:** Component breakdown
- **Tab 4 — Market Context:** Vacancy, absorption, supply pipeline
- **Tab 5 — Source Log:** All URLs and dates for audit trail

File naming: per ORA's three standing naming schemas (ratified 2026-06-10; ORA Cowork Global Settings v2.0, 2026-06-11 — do NOT unify). This comp-research deliverable is a session/analysis output → use `YYYY-MM-DD_[Topic]_[DocType]_v##.ext` in an `/outputs/` subfolder. (Supersedes the single unified "ORA File-Naming Standard 2026-05-14.md," which predates the 2026-06-10 three-schema ratification and is retained only as historical provenance.)

### Notion Integration
When comps are collected, offer to add them to the Comparable Data database in Notion for long-term tracking and portfolio-wide analysis.

---

## 6. OXFORD MARKET BENCHMARKS

> Target-market roster is governed by `target-markets.json` (v1.6, bundled into this skill's package as of 2026-07-09 — master copy at repo root `ora-skills/target-markets.json`); the entry-phase markets carry sourced metrics there too. Keep this table's market rows in parity with that file.

Reference these Oxford portfolio benchmarks when contextualizing comps:

| Market | Avg Rent PSF (NNN) | Avg Cap Rate | Avg Price/SF | Typical Clear Height |
|--------|--------------------|--------------|--------------|--------------------|
| Columbus OH | $4.50-6.50 | 7.0-8.5% | $45-75 | 14-18' |
| Kansas City MO/KS | $4.00-6.00 | 7.5-9.0% | $40-65 | 14-16' |
| Indianapolis IN | $4.00-5.50 | 7.5-9.0% | $40-60 | 14-18' |
| Maryland (Baltimore/DC) — Baltimore submarket | $6.00-9.00 | 6.5-8.0% | $60-100 | 14-20' |
| Maryland (Baltimore/DC) — DC submarket | $8.00-12.00 | 6.0-7.5% | $80-150 | 14-20' |
| Cincinnati OH | $4.50-6.50 | 7.0-8.5% | $45-70 | 14-18' |
| Madison WI | $6.00-8.50 | 6.5-8.0% | $60-95 | 14-18' |
| Grand Rapids MI | $6.40-10.00 | 7.5-9.0%* | $130-160 | 16-24'† |
| Richmond VA | $8.00-9.00 | 6.25-7.0%* | $108-133 | 16-24'† |
| Des Moines IA | $6.40-9.40 | 7.0-7.6%* | $115-125 | 16-24'† |

*[SPECULATIVE] Columbus/KC/Indy/MD/DC/Cincinnati/Madison ranges are estimates from general market knowledge — always verify with current data.*
*Grand Rapids / Richmond / Des Moines populated 2026-05-30 from live market research (rent & price = brokerage prints; ranges span industrial-to-flex). Sources: Grand Rapids — Colliers West Michigan Q4 2025 (vacancy 3.7%, NNN $6.39, flex >$10) + LoopNet/Crexi ($133-160/SF asking). Richmond — CBRE Q4 2025 (vacancy 4.4%, NNN $8.08) + REBusinessOnline 2025 ($108-133/SF; ~5.3% institutional core). Des Moines — Colliers Q4 2025 (vacancy 7.5%, NNN $6.90, flex ~$9.40) + LoopNet ($121/SF).*
*Cap rates marked * for these three are [SPECULATIVE] — no firm-published sub-$10M multi-tenant/flex cap series exists for any of them; treat as directional and confirm at the deal level. Clear heights marked † are typical-product estimates, not metro prints — verify per building.*

---

## 7. CROSS-SKILL INTEGRATION

- **acquisition-underwriting:** Feed comp data directly into underwriting models for market rent assumptions
- **tax-appeal:** Use sale comps for comparable sales approach in tax appeal analysis
- **market-monitor:** Supplement with macro market data and trend analysis
- **lease-abstraction-pipeline:** Compare extracted in-place rents against current market comps (skill renamed in v2.0; formerly `lease-abstraction`)

## Changelog

- v1.1 (2026-07-08): HIGH fix (Skill Text Audit finding 4) — added §6 benchmark rows for the 5 canonical markets missing from the table (Cincinnati OH, Madison WI, Grand Rapids MI, Richmond VA, Des Moines IA), sourced from `target-markets.json` and live 2026-05-30 brokerage research. This repo copy already carried the rows; the installed Cowork runtime copy did not (drift) — repackage and reinstall via `package-and-stage-skill`. Also (bonus, beyond audit scope): repointed the §-level file-naming citation from the superseded single "ORA File-Naming Standard 2026-05-14.md" to the ratified three-schema doctrine (see finding 5 handling).
