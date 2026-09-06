# indy_probe*.py — archived 2026-09-06 (ORA Automation Audit R23 follow-up)

Nine one-off Indianapolis-metro endpoint-discovery probes from the `county-parcel-screen`
Indy research pass. Archived, not deleted (Hard Invariant 6).

**Why archived:** each was scratch for a single discovery question (statewide parcel layer
schema, MapIndy property service, DLGF bulk paths, collar-county GIS servers, owner-bearing
sources for Hendricks/Boone/Johnson). Verified 2026-09-06: **zero inbound references** across
every `.md`/`.py`/`.js`/`.mjs` in the repo. Their findings are already captured in
`county-parcel-screen/references/county-endpoints.md` and `market-status.md`, which are the
durable artifacts; the probes themselves are the working-out, not the answer.

**If you need one back:** they run standalone against public ArcGIS REST endpoints and need
no repo context — copy one out rather than re-adding the whole set. If an endpoint has since
moved, `references/county-endpoints.v1.json` is the current registry of record for parcel
layers, and `parcel-data-recovery/references/endpoints.md` for footprint/CAMA/bulk-export.
