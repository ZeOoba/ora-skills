---
name: submarket-spatial-analysis
description: Submarket and spatial analysis for ORA properties and acquisition candidates. Use when the user mentions: submarket, spatial analysis, drive time, isochrone, intermodal proximity, highway access, last-mile, demographics, employment density, population growth, MSA, micropolitan, traffic count, locational benchmark, location quality score, GIS, mapping, or any task requiring geographic analysis of properties relative to demand drivers. v1.2 (2026-07-20: Location Score step 4 now calls census-acs-extract for a CONFIRMED metro labor-quality sub-finding)
license: ORA Internal
---

# Submarket Spatial Analysis

Analyze ORA properties and acquisition candidates against spatial demand drivers: highway access, intermodal proximity, last-mile geography, employment, and demographics.

## Scope

Covers all ORA target markets (OH, MD, IN, WI, MO, KS, TN) and submarkets within them. Used for acquisition screening, tenant-mix optimization, and disposition evaluation.

## Triggers

Acquisition candidate location scoring, submarket comparison, intermodal proximity check, drive-time analysis, demographic profile, employment growth check, last-mile suitability scoring.

## Inputs

- Notion property database (lat/long for each ORA property)
- Census ACS data (demographics, employment) — public APIs
- BTS NTAD (highway, rail, intermodal) — public data
- Web search / Firecrawl for nearby anchor tenants and points of interest (no dedicated places/POI API is connected — this is a manual lookup, not a live query)
- Web search for submarket reports (CBRE, Cushman, JLL)

## Standard Workflows

### Acquisition Location Score (1–100)
1. Distance to nearest interstate (weight 25%).
2. Distance to nearest intermodal (BNSF, NS, CSX) — for industrial (weight 20%).
3. 30-min drive-time population (weight 15%).
4. 30-min drive-time labor pool of relevant occupations (weight 15%). Mandatory sub-step: call census-acs-extract's `extract_metro_attainment(year)` for the subject property's metro CBSA, for the most recent available year AND a 5-year-prior anchor year (2024 vs 2019, or the nearest available anchor pair per that skill's own ANCHORS dict), and report the bachelor's+-attainment level, share, and 5-year delta as a CONFIRMED sub-finding within this weighted component. Cite it explicitly: "CONFIRMED (Census ACS 1yr Summary File B15003, FTP, no key)" so it reads as visually distinct from the [est] figures around it. This upgrades only the labor-quality/human-capital dimension of the component — see Boundaries.
5. Submarket vacancy and rent growth trend (weight 15%).
6. Major employer / anchor tenant proximity (weight 10%).
7. Output: location score memo (DOCX) with composite score and component breakdown.

### Submarket Comparison
1. Compare 2+ submarkets across the same dimensions.
2. Normalize scores; produce ranking.
3. Output: submarket comparison memo (DOCX) with side-by-side table.

### Last-Mile Suitability
1. Distance to population centers (5/10/15 mile rings).
2. Truck-court and dock-door inventory.
3. Highway access / signal density.
4. Output: last-mile scorecard (xlsx).

### Tenant Mix Optimization
1. For an existing property, plot current tenants by industry.
2. Identify gaps relative to submarket employment composition.
3. Output: tenant mix recommendation memo (DOCX).

## Outputs

- DOCX memos with embedded maps where possible
- xlsx scorecards
- Mirror to SharePoint /Acquisitions/[deal]/Spatial/
- File naming: YYYYMMDD_[Property-or-Submarket]_Spatial_v##.docx

## Boundaries

- Forecasts of demographic change marked [FORECAST].
- Census data lag is acknowledged (typically 12–24 months).
- No routing API (OSRM/Mapbox/etc.) is currently connected — drive-time figures are estimated (straight-line distance + assumed speed, or a manual web-mapping lookup) and must state the estimation method used. If a routing MCP connector is ever added, update this line and tech.md together.
- census-acs-extract closes the labor-quality/attainment sub-gap at the metro level; the drive-time population ring remains [est] pending a routing/isochrone connector. Don't conflate the two: a CONFIRMED attainment figure does not mean the drive-time population gap is closed.

## Dependencies

- acquisition-underwriting skill (consumes location score for IC memo)
- market-monitor skill (submarket trends)
- rent-comp skill (rental rate inputs)
- docx skill (memo deliverables)
- census-acs-extract skill (metro-level labor-quality/attainment confirmation, Location Score component 4)
