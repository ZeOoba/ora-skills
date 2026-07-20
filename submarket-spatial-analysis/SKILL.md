---
name: submarket-spatial-analysis
description: Submarket and spatial analysis for ORA properties and acquisition candidates. Use when the user mentions: submarket, spatial analysis, drive time, isochrone, intermodal proximity, highway access, last-mile, demographics, employment density, population growth, MSA, micropolitan, traffic count, locational benchmark, location quality score, GIS, mapping, or any task requiring geographic analysis of properties relative to demand drivers. v1.3 (2026-07-20: reconciled two independent lines of work — a real Drive-Time Method ladder (ORS keyed API -> keyless OSRM public server -> straight-line last resort, OSRM live-verified 2026-07-18/19) recovered from the stale next5-sourcing-data branch, plus Location Score step 4 now calling census-acs-extract for a CONFIRMED metro labor-quality sub-finding)
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
- **Drive-time routing** (see Drive-Time Method below): OpenRouteService (ORS) public API — `[GG: ORS API key needed — free signup at openrouteservice.org; set ORS_API_KEY in the environment]` — with a keyless OpenStreetMap-based OSRM public server (`router.project-osrm.org`) as fallback.

## Standard Workflows

### Drive-Time Method (resolution ladder — try in order, label the result honestly)

Any step that needs a drive-time (isochrone population, labor pool, distance-to-anchor by road) resolves the travel time through this ladder and **states which tier produced the number** in the output:

1. **OpenRouteService (ORS) — preferred, needs a free key.** If `ORS_API_KEY` is present, call the ORS public API:
   - Matrix (many origins→destinations, durations): `POST https://api.openrouteservice.org/v2/matrix/driving-car` with header `Authorization: {ORS_API_KEY}`, body `{"locations": [[lon,lat],...], "metrics": ["duration"]}`.
   - Isochrones (true drive-time polygon for ring population): `POST https://api.openrouteservice.org/v2/isochrones/driving-car`, body `{"locations": [[lon,lat]], "range": [1800], "range_type": "time"}` (1800 s = 30 min). Intersect the polygon with Census block-group centroids for the 30-min population/labor pool.
   - Free tier ≈ 2,000 matrix calls/day, 500 isochrone calls/day — ample for ORA volume. Label: **"drive-time: ORS road network"**.
   - `[GG: ORS API key needed — free signup at openrouteservice.org]`
2. **OSRM public server — keyless fallback (verified live 2026-07-18, independently re-confirmed 2026-07-19 via a real `route` + `table` request between Columbus OH and Rickenbacker Inland Port — both returned valid duration/distance).** If no ORS key, use the public OSM demo server (no key, best-effort, rate-limited — never for bulk production):
   - Route (point-to-point duration/distance): `GET https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false` → `routes[0].duration` (seconds), `.distance` (m).
   - Table (durations matrix): `GET https://router.project-osrm.org/table/v1/driving/{lon1,lat1;lon2,lat2;...}?annotations=duration` → `durations` matrix (seconds).
   - OSRM has **no isochrone endpoint** — for ring population, sample candidate block-group centroids within a straight-line radius and keep those whose table-driving-time ≤ threshold. Label: **"drive-time: OSRM public OSM server (best-effort)"**.
3. **Straight-line approximation — LAST resort, always labeled as such.** If both ORS and OSRM are unavailable/erroring, estimate: road distance ≈ great-circle × 1.3 detour factor; time ≈ distance ÷ assumed speed (55 mph highway / 30 mph arterial / 20 mph urban). Label: **"drive-time: straight-line estimate (no routing service) — REPLACE with ORS/OSRM before any IC-grade figure"**.

Never present a tier-3 estimate as a routed figure; the tier label is mandatory in every memo/scorecard cell that carries a drive-time.

### Acquisition Location Score (1–100)
1. Distance to nearest interstate (weight 25%).
2. Distance to nearest intermodal (BNSF, NS, CSX) — for industrial (weight 20%).
3. 30-min drive-time population (weight 15%) — resolve travel time via the Drive-Time Method ladder above (ORS → OSRM → straight-line), labeling the tier.
4. 30-min drive-time labor pool of relevant occupations (weight 15%) — same Drive-Time Method ladder for the ring, PLUS a mandatory sub-step: call census-acs-extract's `extract_metro_attainment(year)` for the subject property's metro CBSA, for the most recent available year AND a 5-year-prior anchor year (2024 vs 2019, or the nearest available anchor pair per that skill's own ANCHORS dict), and report the bachelor's+-attainment level, share, and 5-year delta as a CONFIRMED sub-finding within this weighted component. Cite it explicitly: "CONFIRMED (Census ACS 1yr Summary File B15003, FTP, no key)" so it reads as visually distinct from the drive-time-ladder figures around it. The two are complementary, not overlapping: the Drive-Time Method resolves the population/labor-pool RING; census-acs-extract confirms labor QUALITY (attainment) at the metro level — see Boundaries.
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
- Drive-time figures follow the Drive-Time Method ladder (ORS road network → keyless OSRM public server → straight-line estimate) and **must state which tier produced them**. ORS needs a free API key (`ORS_API_KEY`; see the placeholder in Inputs) — until it is set, live routing runs on the keyless OSRM public server (best-effort, not for bulk production), and only falls to a straight-line estimate if both are unavailable. If a dedicated routing MCP connector is ever added, prefer it and update this line and tech.md together.
- census-acs-extract closes the labor-quality/attainment sub-gap at the metro level (step 4's CONFIRMED sub-finding); it does NOT resolve the drive-time population/labor-pool ring itself — that's the Drive-Time Method ladder's job, above. Don't conflate the two: a CONFIRMED attainment figure does not mean the drive-time ring is routed at ORS/OSRM quality — check the tier label on that figure separately.

## Dependencies

- acquisition-underwriting skill (consumes location score for IC memo)
- market-monitor skill (submarket trends)
- rent-comp skill (rental rate inputs)
- docx skill (memo deliverables)
- census-acs-extract skill (metro-level labor-quality/attainment confirmation, Location Score component 4)

## Changelog

- **v1.3 (2026-07-20):** Reconciled two independent, previously-unmerged lines of work that had drifted into a version collision:
  - Recovered the Drive-Time Method resolution ladder (ORS keyed API → keyless OSRM public server → straight-line estimate last, each tier honestly labeled) from a stale unmerged commit (`b5ad834`, 2026-07-19) sitting in the `next5-sourcing-data` worktree — OSRM public server (`router.project-osrm.org` route + table endpoints) verified live 2026-07-18, re-confirmed 2026-07-19. That commit's companion `ora-flood-zoning-dd` edit was NOT carried forward — it cross-linked a `county-parcel-screen` skill and `county-endpoints.v1.json` registry that do not exist anywhere in this repo's history (confirmed via full-history search); that half of the branch rests on a phantom dependency and was left out.
  - Retained the `census-acs-extract` metro labor-quality/attainment confirmation added earlier the same day (was tagged v1.2, 2026-07-20). Location Score steps 3/4 and the Boundaries section now clearly separate the two: the Drive-Time Method ladder resolves the population/labor-pool ring; census-acs-extract confirms labor quality (attainment) at the metro level.
- **v1.2 (2026-07-18, unmerged until this reconciliation):** Drive-Time Method ladder added (ORS → OSRM → straight-line).
- **v1.1 (2026-07-16):** Removed references to mcp__places/ESRI/Mapbox/OSRM as connected tools (none were connected); drive-time/nearby-anchor steps stated the actual method used.
