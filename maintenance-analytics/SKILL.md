---
name: maintenance-analytics
description: "Predictive maintenance and CapEx forecasting for Oxford Realty Advisors portfolio. Use this skill whenever the user mentions: maintenance forecast, CapEx budget, roof replacement schedule, HVAC lifecycle, repair history analysis, deferred maintenance, capital planning, reserve study, maintenance prediction, R&M analysis, expected useful life, or any request to analyze historical repair data and forecast future capital needs. Also trigger when the user uploads maintenance logs, vendor invoices, or R&M expense reports."
---

# Predictive Maintenance & CapEx Forecasting

Systematic capital expenditure forecasting from historical R&M data for Oxford Realty Advisors' 600K+ SF industrial portfolio.

---

## 1. R&M DATA INGESTION

Accept maintenance data in these formats:
- **XLSX/CSV** from PM platforms (Rent Manager, Yardi, AppFolio)
- **QB Desktop** R&M expense exports (via `OneDrive\Claude_Workspace\01_Cowork_OS\Cowork_OS_Workspace\QB Exports\`)
- **Manual entry** of major CapEx items
- **Vendor invoices** (PDF — extract via pdf skill)

### Normalization Schema
Transform all input into this standard format:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| Date | DATE | Yes | Date of work completion or invoice |
| Property | TEXT | Yes | Property name or address |
| Building | TEXT | No | Building ID if multi-building property |
| Category | ENUM | Yes | See Category Taxonomy below |
| Subcategory | ENUM | Yes | See Category Taxonomy below |
| Description | TEXT | Yes | Work description |
| Cost | NUMBER | Yes | Total cost including labor and materials |
| Vendor | TEXT | No | Vendor/contractor name |
| Is CapEx | BOOLEAN | Yes | True if >$2,500 and extends useful life |
| Useful Life | NUMBER | No | Expected years of useful life for CapEx items |
| Unit/Tenant | TEXT | No | If tenant-specific |
| Warranty | TEXT | No | Warranty expiration date if applicable |

---

## 2. CATEGORY TAXONOMY

Classify all maintenance items into these categories:

### Capital Systems
| Category | Subcategories | Useful Life | Est. Cost/SF |
|----------|--------------|-------------|-------------|
| **Roof** | Inspection, Patch Repair, Partial Replacement, Full Replacement, Coating | 20-25 yr (full), 8-12 yr (coating) | $8-12/SF (full), $2-4/SF (coating) |
| **HVAC** | Filter Change, Minor Repair, Compressor, Full Unit Replacement | 15-20 yr | $3,000-5,000/unit (RTU) |
| **Parking/Paving** | Seal Coat, Crack Fill, Partial Repave, Full Repave, Striping | 20-25 yr (full), 3-5 yr (seal) | $3-5/SF (full), $0.15-0.25/SF (seal) |
| **Overhead Doors** | Spring Repair, Panel Replace, Opener, Full Door Replacement | 15-20 yr | $3,000-5,000/door |
| **Fire Suppression** | Inspection, Head Replace, Valve Repair, System Replacement | 25-30 yr | Varies by system type |
| **Electrical** | Minor Repair, Panel Upgrade, Lighting Retrofit, Service Upgrade | 25-40 yr (panel), 10-15 yr (lighting) | $2-4/SF (LED retrofit) |

### Maintenance Systems
| Category | Subcategories | Cycle |
|----------|--------------|-------|
| **Plumbing** | Minor Repair, Pipe Replacement, Sewer Line, Water Heater, Backflow | As needed |
| **Structural** | Foundation Repair, Exterior Wall, Load-Bearing, Tilt Panel | As needed |
| **Exterior** | Painting, Siding, Fascia, Gutters, Downspouts | 7-10 yr (paint) |
| **Landscaping** | Mowing, Tree Trim, Irrigation, Hardscape | Seasonal |
| **Signage** | Repair, Replacement, New Install | 10-15 yr |

### Operational
| Category | Subcategories |
|----------|--------------|
| **Tenant-Caused** | Damage Repair, TI Demolition, Unit Turn, Cleaning |
| **Janitorial** | Common Area, Snow/Ice, Pest Control |
| **Compliance** | ADA, Environmental, Fire Code, Elevator |

---

## 3. LIFECYCLE FORECASTING MODEL

For each property in the portfolio, build a 10-year CapEx forecast:

### Step 1 — System Age Assessment
For each major system at each property:
```
Current Age = Current Year - max(Year Built, Last Replacement Year)
Remaining Life = Expected Useful Life - Current Age
Projected Replacement Year = Current Year + Remaining Life
```

If last replacement date is unknown, use year built as baseline (conservative assumption).

### Step 2 — Cost Estimation
For each projected replacement:
```
Estimated Cost = Cost/SF × Property SF (for area-based systems)
   OR
Estimated Cost = Cost/Unit × Unit Count (for unit-based systems like HVAC, doors)
```

Apply 3% annual inflation to all future cost estimates.

### Step 3 — Priority Scoring
Score each item 1-10:
- **Age Factor (0-3):** 0 if <50% life used, 1 if 50-75%, 2 if 75-100%, 3 if past useful life
- **Failure Risk (0-3):** Based on R&M frequency trend (increasing = higher risk)
- **Cost Impact (0-2):** 0 if <$10K, 1 if $10-50K, 2 if >$50K
- **Tenant Impact (0-2):** 0 if minimal, 1 if disruptive, 2 if habitability/safety risk

Score ≥7: **Critical — budget this year**
Score 5-6: **Plan — budget within 2 years**
Score 3-4: **Monitor — include in 5-year plan**
Score ≤2: **Defer — no action needed**

---

## 4. R&M PATTERN ANALYSIS

When historical R&M data is available, analyze:

### Trend Detection
- **Increasing frequency:** If a system has 3+ repair events in 12 months, flag as potential failure precursor
- **Cost escalation:** If repair costs are trending upward for a system, flag replacement consideration
- **Seasonal patterns:** Identify recurring seasonal maintenance (HVAC spring/fall, snow removal, seal coating season)

### Vendor Analysis
- Identify most-used vendors by category
- Calculate average cost per vendor for similar work (flag outliers)
- Track warranty periods and coverage

### Property Benchmarking
- Calculate R&M $/SF by property
- Identify properties with R&M $/SF >150% of portfolio average
- Compare to industry benchmarks: industrial R&M typically $0.50-1.50/SF annually

---

## 5. OUTPUT — CapEx Forecast Workbook

Use the xlsx skill to produce:

### Tab 1 — CapEx Forecast by Property
| Property | System | Current Age | Remaining Life | Projected Year | Estimated Cost | Priority Score |

### Tab 2 — Portfolio Summary (10-Year)
| Year | Total CapEx Budget | By Category Breakdown | Cumulative Spend |

### Tab 3 — Annual Reserve Calculation
```
Annual Reserve/Property = 10-Year Total CapEx ÷ 10
Annual Reserve/SF = Annual Reserve/Property ÷ Property SF
Portfolio Annual Reserve = Sum of all property reserves
```
Industry benchmark for industrial: $0.25-0.75/SF annually in reserves.

### Tab 4 — System Lifecycle Dashboard
Visual matrix: Properties (rows) × Systems (columns), color-coded by remaining life:
- 🟢 Green: >50% life remaining
- 🟡 Yellow: 25-50% life remaining
- 🔴 Red: <25% life remaining or past useful life

### Tab 5 — Deferred Maintenance Register
All items past expected useful life, sorted by priority score.

### Tab 6 — R&M History Analysis (if data provided)
Trend charts, vendor summary, property benchmarking.

File naming: Follow ORA File-Naming Standard v1.0+ — `YYYYMMDD_[Subject]_[DocType]_v##.ext` format. Canonical: `Claude_Workspace/00_Governance/References/Standards/ORA File-Naming Standard 2026-05-14.md`

---

## 6. CROSS-SKILL INTEGRATION

- **acquisition-underwriting:** Feed CapEx estimates into underwriting models for year-1 and ongoing capital budgets
- **re-operations:** Align CapEx forecast with monthly operations checklist and budget tracking
- **portfolio-reporting:** Include CapEx forecast summary in quarterly portfolio reports
- **tax-appeal:** Deferred maintenance register supports arguments for lower assessed value
