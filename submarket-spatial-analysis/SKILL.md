---
name: submarket-spatial-analysis
description: Submarket and spatial analysis for ORA properties and acquisition candidates. Use when the user mentions: submarket, spatial analysis, drive time, isochrone, intermodal proximity, highway access, last-mile, demographics, employment density, population growth, MSA, micropolitan, traffic count, locational benchmark, location quality score, GIS, mapping, or any task requiring geographic analysis of properties relative to demand drivers. v1.0
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
- Places search (mcp__places...) for nearby anchors
- Web search for submarket reports (CBRE, Cushman, JLL)
- ESRI / Mapbox via places_search where available

## Standard Workflows

### Acquisition Location Score (1–100)
1. Distance to nearest interstate (weight 25%).
2. Distance to nearest intermodal (BNSF, NS, CSX) — for industrial (weight 20%).
3. 30-min drive-time population (weight 15%).
4. 30-min drive-time labor pool of relevant occupations (weight 15%).
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
- Drive-time calculations use OSRM or Mapbox where available; assumptions stated explicitly.

## Dependencies

- acquisition-underwriting skill (consumes location score for IC memo)
- market-monitor skill (submarket trends)
- rent-comp skill (rental rate inputs)
- docx skill (memo deliverables)
