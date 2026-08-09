---
name: tax-appeal
description: "Property tax assessment analysis and appeal decision engine for Oxford Realty Advisors. Use this skill whenever the user mentions: property tax, tax assessment, tax appeal, assessed value, tax reduction, county assessor, millage rate, tax bill, reassessment, tax protest, tax grievance, income approach valuation, or any request to evaluate whether a property tax assessment should be appealed. Also trigger when the user uploads a property tax bill or assessment notice. v1.1 (2026-07-08: file-naming citations repointed from the superseded single 2026-05-14 standard to the ratified three-schema doctrine)"
---

# Property Tax Appeal Decision Engine

Systematic tax assessment analysis and appeal recommendation for Oxford Realty Advisors.

---

## 1. ASSESSMENT DATA COLLECTION

When a tax assessment is provided (uploaded bill, manual input, or Notion lookup):

### Required Inputs
| Field | Source |
|-------|--------|
| Property address | User or Notion Property Financials |
| Current assessed value | Tax bill or county assessor website |
| Prior year assessed value | Tax bill or county assessor website |
| Tax rate / millage | Tax bill or county lookup |
| Annual tax amount | Tax bill (calculated: assessed value × millage) |
| Assessment date | Tax bill |
| Appeal deadline | Jurisdiction-specific (see Section 5) |
| Current in-place NOI | Notion Property Financials or user input |
| Property SF | Notion Tenant Database or user input |
| Year built | Notion or county assessor |

### Auto-Calculate
- YoY assessment change: `(Current - Prior) / Prior × 100`
- Effective tax rate: `Annual Tax / Market Value estimate`
- Tax per SF: `Annual Tax / Property SF`
- Tax as % of NOI: `Annual Tax / NOI × 100`

---

## 2. THREE-APPROACH VALUATION

### A. Income Approach (Primary for Oxford properties)
```
Income Approach Value = Stabilized NOI / Market Cap Rate
```

**NOI Determination:**
- Use trailing 12-month NOI from Property Financials (preferred)
- Or construct from: Gross Potential Rent - Vacancy Allowance (5-10%) - Operating Expenses
- Exclude capital expenditures, debt service, depreciation
- Include management fee (even if self-managed, impute 3-5% for valuation)

**Cap Rate Selection:**
- Use the market-monitor skill (`rent-comp` retired 2026-08-05, comp-sourcing discipline absorbed by market-monitor v1.2) to pull recent sale comps and extract cap rates
- Or search: "[city] [property type] cap rate [year]"
- Apply appropriate cap rate for property class and condition
- Use cap rate RANGE to establish value range (not single point)

**Output:**
| Metric | Value |
|--------|-------|
| Stabilized NOI | $X |
| Market Cap Rate (low) | X.X% |
| Market Cap Rate (mid) | X.X% |
| Market Cap Rate (high) | X.X% |
| Income Value (low) | $X |
| Income Value (mid) | $X |
| Income Value (high) | $X |

### B. Comparable Sales Approach
- Use the market-monitor skill (`rent-comp` retired 2026-08-05) to pull 3-6 recent comparable sales
- Calculate median and mean price/SF from comps
- Apply to subject property: `Comparable Value = Median Price/SF × Subject SF`
- Adjust for: age, condition, location, occupancy, lease quality

### C. Cost Approach (Supporting)
```
Cost Approach Value = Land Value + (Replacement Cost - Depreciation)
```
- **Land value:** County assessor land-only value OR comparable land sales
- **Replacement cost:** `maintenance-analytics` retired 2026-08-05, no successor named — search construction costs directly
- **Depreciation:** `Age / Useful Life × Replacement Cost` (straight-line, 40-year life for industrial)

---

## 3. APPEAL DECISION MATRIX

Score the appeal opportunity on a 12-point scale:

| Criterion | Points | Condition |
|-----------|--------|-----------|
| Income approach gap | +3 | Assessed value > income approach (mid) by >15% |
| Sales comp gap | +3 | Assessed value > comparable sales value by >15% |
| YoY spike | +2 | Assessment increased >10% YoY without physical improvement |
| Dollar savings | +2 | Potential annual tax savings > $5,000 |
| Timeline | +1 | Appeal deadline is >30 days away |
| Jurisdiction track record | +1 | Jurisdiction has historically favorable appeal outcomes |

### Decision Thresholds
| Score | Recommendation | Action |
|-------|---------------|--------|
| **8-12** | **STRONG APPEAL — Proceed** | Generate full appeal package |
| **5-7** | **MODERATE — Analyze Further** | Refine valuation, consider attorney cost vs. savings |
| **0-4** | **WEAK — Likely Not Worth It** | Document analysis, revisit next reassessment cycle |

### ROI Calculation
```
Estimated Annual Savings = (Current Tax) - (Proposed Value × Millage)
Appeal Cost = Attorney fees ($2,000-5,000 typical) + filing fees + appraisal ($1,500-3,000 if needed)
Payback Period = Appeal Cost / Annual Savings
3-Year ROI = (Annual Savings × 3 - Appeal Cost) / Appeal Cost × 100
```

Flag if payback period > 2 years (marginal return).

---

## 4. APPEAL PACKAGE GENERATION

If proceeding with appeal (score ≥5):

### Document Assembly
Use the docx skill to produce an appeal letter including:

1. **Cover letter** on ORA letterhead addressed to the appropriate review board
2. **Property description** with photos, SF, year built, condition notes
3. **Income approach analysis** with NOI documentation and cap rate support
4. **Comparable sales** with adjustment grid
5. **Proposed value** with supporting rationale
6. **Exhibits:**
   - A: Rent roll (redacted tenant names if confidential)
   - B: Operating expense summary
   - C: Sale comparable data sheets
   - D: Market report excerpts supporting cap rate
   - E: Photos of deferred maintenance or functional obsolescence (if applicable)

File naming: per ORA's three standing naming schemas (ratified 2026-06-10; ORA Cowork Global Settings v2.0, 2026-06-11 — do NOT unify). This appeal package is a session/analysis output → use `YYYY-MM-DD_[Topic]_[DocType]_v##.ext` in an `/outputs/` subfolder. (Supersedes the single unified "ORA File-Naming Standard 2026-05-14.md," which predates the 2026-06-10 three-schema ratification and is retained only as historical provenance.)

### Attorney Referral
Reference the Gibbs Firm (Oxford's property tax counsel) for jurisdictions requiring legal representation. Include:
- Jurisdiction
- Property parcel number
- Current assessed value
- Proposed value
- Supporting documentation package
- Appeal deadline

---

## 5. JURISDICTION-SPECIFIC PROCEDURES

### Ohio — Franklin County (Columbus properties)
- **Board:** Franklin County Board of Revision
- **Cycle:** Annual assessment, triennial reappraisal
- **Deadline:** March 31 of the tax year (file complaint with BOR)
- **Process:** Informal hearing → Board of Revision → Board of Tax Appeals → Court
- **Notes:** Ohio allows complaints for ANY year in the triennial cycle. Over-assessments can be challenged using income approach. Use web_search to verify current deadlines.

### Maryland (DC Metro / Baltimore properties)
- **Board:** Maryland State Department of Assessments and Taxation (SDAT)
- **Cycle:** Triennial reassessment (phased in over 3 years)
- **Deadline:** Within 45 days of assessment notice
- **Process:** Written appeal to SDAT → Property Tax Assessment Appeals Board → Maryland Tax Court
- **Notes:** Phase-in means you appeal the final value, not the phased value. Check which triennial group each property falls in.

### Indiana (Indianapolis properties)
- **Board:** County Assessor → Property Tax Assessment Board of Appeals (PTABOA)
- **Cycle:** Annual trending, full reassessment every 5 years (was 4)
- **Deadline:** June 15 (or 45 days after notice, whichever is later)
- **Process:** Informal with assessor → PTABOA → Indiana Board of Tax Review → Tax Court
- **Notes:** Indiana uses a cost approach as the starting point but accepts income approach for commercial.

### Missouri — Jackson County (Kansas City properties)
- **Board:** Jackson County Board of Equalization
- **Cycle:** Biennial reassessment (odd years for commercial)
- **Deadline:** Typically July 1 of reassessment year
- **Process:** Informal with assessor → Board of Equalization → State Tax Commission → Circuit Court
- **Notes:** Jackson County has been controversial for assessment practices. Always verify current procedures via web_search.

**IMPORTANT:** Always use web_search to verify current appeal deadlines before advising. Deadlines change and missing them is fatal to the appeal.

---

## 6. PORTFOLIO-WIDE TAX ANALYSIS

When requested, run the assessment analysis across the entire portfolio:

1. Pull all property assessments (from Notion Property Financials or user upload)
2. Run the 3-approach valuation for each property
3. Score each property using the appeal decision matrix
4. Rank by potential annual tax savings (descending)
5. Produce a priority list: which properties to appeal first
6. Calculate total portfolio tax savings opportunity

Output as XLSX per ORA's three standing naming schemas (ratified 2026-06-10; ORA Cowork Global Settings v2.0, 2026-06-11 — do NOT unify). This portfolio tax-savings workbook is a session/analysis output → use `YYYY-MM-DD_[Topic]_[DocType]_v##.ext` in an `/outputs/` subfolder. (Supersedes the single unified "ORA File-Naming Standard 2026-05-14.md," which predates the 2026-06-10 three-schema ratification and is retained only as historical provenance.)

## Changelog

- v1.1 (2026-07-08): HIGH fix (beyond formal Skill Text Audit scope, same doctrine class as finding 5) — both file-naming citations (Appeal package, §4; Portfolio-wide XLSX, §6) repointed from the superseded single "ORA File-Naming Standard 2026-05-14.md" to the ratified three-schema doctrine (ORA Cowork Global Settings v2.0, 2026-06-10/11).

---

## 7. CROSS-SKILL INTEGRATION

- **market-monitor:** Pull sale comps for comparable sales approach and cap rate data for income approach (`rent-comp` retired 2026-08-05, absorbed here)
- **acquisition-underwriting:** Tax analysis is a standard component of deal underwriting — feed assessed value and tax rate into pro forma
- **(no successor):** `maintenance-analytics` retired 2026-08-05 with no successor named — deferred-maintenance depreciation arguments in the cost approach need a manual source until one exists
- **ora-pm-ledger:** Track appeal deadlines in the daily ops ledger, flag upcoming deadlines in the monthly checklist (`re-operations` retired 2026-08-05, redundant with named ops siblings)
- **document-assembly:** Generate appeal letters using the ORA letterhead template
