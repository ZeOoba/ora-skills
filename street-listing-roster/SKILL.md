---
name: "street-listing-roster"
description: "Use when Gabriel names a street or corridor and asks to find the for-sale industrial properties on it, or why they are priced as they are."
---

# street-listing-roster (v1.1)

Street or corridor name in, verified roster of for-sale industrial listings out, with a pricing-driver read. This skill enumerates, enriches and sanity-checks; it does not score. Scoring belongs to `acquisition-underwriting` (SCREEN), single-target pre-screens to `verified-deal-recon`, off-market owner work to `county-parcel-screen`.

## Step 0 — Resolve the street name
User street names are often abbreviated ("Cane Road" was Cane Run Road, 40258/40216). Search the variants, state the resolved name and zip codes up front, and note which end of a long street each listing sits on (character can change sharply along one road).

## Step 1 — Enumerate
Run WebSearch for `<street> <city> industrial for sale`, plus one query per zip. Then fetch, in this order, the sources that have worked: brokerage property pages (CBRE, Colliers, Cushman), CityFeet and CommercialSearch listing indexes, ZoomProspector property reports. LoopNet, Crexi, CoStar and Showcase generally return robots-disallowed, 403 or empty shells to WebFetch. **Never route around a block** (no curl/Python fetch, no cached mirrors); a Chrome-tab pull of two LoopNet property pages on 2026-09-28 returned only related-listing snippets, so it is not a dependable substitute. When a needed listing is behind a block, list it as UNREACHED and ask Gabriel to paste the listing text or an export he holds.

## Step 2 — Data-quality sanity checks (mandatory before any figure is quoted)
- **SF equals lot area:** a listing whose "SF" equals acres × 43,560 (e.g. 696,960 SF = 16.0 ac) is land, not a building. Reclassify.
- **Status:** one aggregator showing OFF MARKET or "no longer advertised" means the listing may be dead; verify on a second source before treating it as live.
- **Lease vs sale:** brokerage pages mix both; record transaction type per row.
- **Conflicting listings:** same address at two prices or two SF figures triggers acquisition-underwriting Stage -1 Rules 3 and 6 (price conflict; SF variance).
- **Buy-box edges:** flag >50,000 SF per building and >$10M at once.
- Year built, clear height and tenancy are usually absent from aggregators; mark them UNK, never infer.

## Step 2b — Enrichment pass (v1.1)
For every live sale candidate, run the `listing-enrichment-gate` chain for the listing's county: parcel ID, parcel land acres, footprint or assessor SF, parcel zoning and overlays, county-hosted flood mirror. Where the gate has no registry for the county, mark the row NOT ENRICHED and say why; never fill from listing wording. Tie listing acreage to parcel acreage (a listing whose acres exceed its parcel spans other parcels: name the gap, do not build a basis view on it). Cite the FEMA source per row as the county mirror with its effective date, and state that a FEMA determination letter is still required pre-LOI. If a PVA/assessor record or broker OM has been supplied, run the gate's record-ingest step and upgrade the row from PROVISIONAL toward CERTIFIED.

## Step 3 — First-pass basis arithmetic (report, do not score)
For each live sale candidate compute ask $/SF, all-in $/SF (ask × 1.02, plus stated CapEx if known), and discount to the RCT v03 LOW for the market in `acquisition-underwriting`. Year built UNK defaults to the 1995 endpoint (65% floor) and is flagged. Compute the ceiling (floor $/SF × SF ÷ 1.02) at BOTH the listing SF and the lower verified SF, and show both when they differ. State pass/fail against the vintage-ramp floor as a flag, never a kill (Ruling 5). Implied cap rate from a market rent guess is [SPECULATIVE] and must say so.

## Step 4 — Submarket read
Pull the metro and submarket prints via `market-monitor` (SUBMARKET CACHE PROTOCOL). Segment test per Stage 2.1: state BLENDED vs product-segmented. Then check corridor factors with sources: flood (FEMA/MSD; use `ora-flood-zoning-dd`), legacy environmental (coal ash, plants, LUST/UST registries), access and highway, and functional mismatch versus the corridor's dominant product (e.g. a 28K SF building in a bulk park). Rank the pricing drivers; separate evidenced drivers from inference and tag inference [SPECULATIVE].

## Step 5 — Answer the premise honestly
If the data shows the assets are market-priced, say so and say what would change the answer. Do not manufacture a discount narrative.

## Output — the standard roster file (v1.1)
Every street run writes the same file, so runs are comparable and diffable.

**Path and name.** `/mnt/user-data/outputs/YYYY-MM-DD_<Street>-<City>/YYYY-MM-DD_<Street>-<City>-Enrichment-Roster_Table_v##.md` (session-output schema; new run = next version number; never overwrite or delete a prior version — move it to `/archive/`). A working table, not an institutional deliverable: if it goes to IC or a counterparty, route it through `document-assembly` and the ORA style guide and QC Gate.

**Header block.** Run date; resolved street name and zips; enrichment method (registries used per county, PROVISIONAL or CERTIFIED per row); floor formula with RCT version and market LOW (e.g. Louisville $237.07 × 35% at the 1995 default ramp); footprint-is-not-GBA note; list of PVA/assessor-only fields still NOT AVAILABLE.

**Table.** One column per property (a wide table, one row per attribute), in this row order: Parcel ID; ZIP; Ask; Listing SF; Parcel land acres (tie to listing acres); Footprint in parcel (SF, building count, roof height); SF variance (listing vs footprint) with the Rule 6 outcome (proceed / FLAG use lower SF / HARD STOP cap T2); Zoning (parcel) with the Rule 8 note; Overlays; Flood (county mirror zone, subtype, effective date); Ceiling at lower SF; Ceiling at listing SF; Ask vs ceiling (lower SF); Ask discount to RCT LOW (all-in, lower SF); Verdict (PROVISIONAL/CERTIFIED/UNREACHED plus the flag). Land-only rows use the land treatment: $/acre on the parcel-verified acres and the SFHA note (Ruling 4: land credit is SCREEN/COMPS until a FEMA determination).

**Flags and next actions.** One block per property, then one for all: listing/parcel acreage mismatches, dead-listing checks, mezzanine questions, levee or SFHA notes, zoning permitted-use checks owed, and the exact data gap that blocks CERTIFIED.

**Companion drafts.** When a county requires a records request to close a gap, write it beside the roster as `YYYY-MM-DD_<Street>-<Agency>-Records-Request_Draft_v##.md`, headed DRAFT NOT SENT, with parcel IDs prefilled and requester contact fields left as bracketed blanks. Never send: an outbound send to an agency needs Gabriel's explicit in-turn confirmation.

**Re-runs.** When a prior roster exists for the street, load the latest version first and add a Changes block to the new one: asks, statuses, listings added or removed, fields newly verified.

**Chat reply.** Lead with the outcome, the 2-4 facts that changed the picture, the file path, and the open gaps. Sources section with links. On a candidate Gabriel wants to pursue, hand to `acquisition-underwriting` SCREEN; do not log to the Deal Sourcing Log from this skill.

## Changelog
- v1.1 (2026-09-28): Added Step 2b (enrichment pass via `listing-enrichment-gate`), dual-SF ceilings in Step 3, and the standard roster file spec (path, header, row order, flags, companion records-request draft, re-run diffing). Origin: the four-parcel Cane Run Road run of 2026-09-28. No floor, ramp, or threshold changed.
- v1.0 (2026-09-28): Initial version.