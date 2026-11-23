# Screen packet — field map (`ora.acq-screen-packet/1`)

Companion to the SKILL.md **SCREEN PACKET** section (v4.59). The SKILL.md rules govern; this file is the field-by-field map from this skill's own outputs to the packet.

**Reader of record:** `scripts/import-acq-screen-packet.ts` in the oxford-command-center repo (`parseScreenPacket`), validated against the engine's `AcquisitionInput` Zod contract in `src/contracts/acquisition.ts`. An unknown key anywhere rejects the packet: in the envelope, in `deal`, directly in `input`, or inside `input.use` / `input.ddKnown` (the importer rejects any key Zod stripped), so a misspelled field is never silently dropped. The importer also rejects a non-finite number (`1e400`) and a `screenedAt` later than today (UTC) plus one day; one file naming the same candidate in two packets is skipped as ambiguous. If the importer and this file disagree, the importer wins and this file (plus `scripts/screen_packet.py`) is a bug to fix.

**Local check:** `python scripts/screen_packet.py <packet.json>` (stdlib only) mirrors the importer's format rejects. Exit 0 = shape valid; it does not check the candidate crosswalk, which needs the warehouse.

## Envelope

| Key | Required | Value |
|---|---|---|
| `schema` | yes | the literal `ora.acq-screen-packet/1` |
| `skillVersion` | yes | `acquisition-underwriting v<X.Y> <MODE>`, e.g. `acquisition-underwriting v4.59 FULL` |
| `screenedAt` | yes | the run date, strict `YYYY-MM-DD` |
| `deal` | yes | at least one of `candidateId`, `notionPageId`, `hubspotDealId`; `address` is a label only (never matched) |
| `sourceFiles` | no | file names of the workbook, IC memo and any screen file the packet was read from |
| `input` | yes | the `AcquisitionInput` fields below; omit `dealId` (the importer fills it with the candidate id) |
| `notes` | no in the contract, **required by this skill** | one string per populated field naming its source, plus `left-null` |

### `deal` identity

- `candidateId` = `deal:<Notion page id>` of the deal's **Acquisition Pipeline Tracker** row (`bcfe4a03`), the page id in its dashed 36-character UUID form. This is the id the command-center Notion sync creates.
- `notionPageId` = the same page id without the `deal:` prefix. Give one or the other, not both from different rows.
- `hubspotDealId` only when the deal has no Pipeline Tracker row but has a HubSpot deal. Never give a Notion id and a HubSpot id for the same property: they are separate candidates and the importer rejects the pair as ambiguous (one property scored twice double-counts the ranked pipeline). Score ONE twin, the Notion row by default.
- The Deal Sourcing Log (`9a6ae219`) is not a candidate source. A deal that is only on the Sourcing Log has no candidate; see SKILL.md (no packet, say why).

## `input` field map

Rates and shares are decimals (`0.0743` = 7.43%). Money in whole USD. SF in square feet. Every field is optional; **omit what the run did not establish** (an omitted field reads as null, and the engine treats null conservatively).

| Field | Type | Source in this skill's run |
|---|---|---|
| `isPortfolio` | bool | STAGE 0 item 2: `false` only when one building/one parcel is confirmed; `true` for an Amendment H portfolio |
| `price` | USD | the **tested price**: the price every rate field below was computed at (ask, LOI or contract price; say which in `notes.price`) |
| `maxBuildingSf` | SF | largest single building (the Gate 2 per-building test) |
| `totalSf` | SF | the SF the basis and yield math used (STAGE -1 Rule 6 / Intake Rule 12); never larger than the sum of buildings |
| `productType` | enum | the run's own Gate 1 classification: `shallow-bay-multi`, `flex`, `office-warehouse`, `functional-single-tenant`, `quasi-ios`, `retail-only`, `office-only`, `other` (multifamily, land, other alt-class = `other`) |
| `officePct` | 0..1 | office share of GBA, when measured |
| `demisableOffice` | bool | only when the run assessed demising |
| `clearHeightFt` | ft | documented clear height; an aerial or photo estimate stays null |
| `hasDriveIn`, `driveInCount`, `hasDock`, `dockCount` | bool / int | loading counts from the OM, site plan or tour |
| `multiStory` | bool | Intake Rule 12 floor split |
| `truckCourtFt` | ft | measured truck court depth |
| `constructionType` | enum | the RCT construction-type row the basis test used (v4.37 schedule), as one of the contract ids `tilt-precast` (the schedule's tilt-up / precast baseline), `cmu`, `brick`, `hybrid`, `pemb`, `mixed`, `unknown`; omit when the run did not classify it. Never the schedule's prose label (`tilt-up`, `block` are rejects) |
| `rctAdders` | list | RCT adders the basis test applied, as contract ids: `heavy-office` (heavy office build-out), `climate-controlled`, `cranes`, `esfr`, `excess-site-work`, `paving-lighting`; `[]` when the test applied none, omit when adders were not assessed |
| `yearBuilt` | int | county record or OM, the vintage the ramp used |
| `sfhaOnPad`, `sfhaOnExcessLandOnly` | bool | Gate 5 FEMA read (FIRM panel and date in notes) |
| `groundLeased`, `groundLeaseYearsRemaining` | bool / years | tenure, only when title or the OM states it |
| `envRemediationPctOfPrice` | 0..1 | `0` only on a clean Phase I; an estimate share of price otherwise; null when no Phase I |
| `use` | object | `{ automotive, childRelated, childSafetyReviewed }`, all three, only when the Gate 6 use screen ran |
| `allInBasis` | USD | the all-in basis the STAGE 1 Basis and Yield floors used (price + closing + day-one capex, per the run) |
| `replacementCostTotal` | USD | only an appraisal replacement-cost override; never the RCT computation itself |
| `market` | string | the RCT market row name the basis test used |
| `stabilizedYoc` | decimal | the stabilized yield on cost the Yield floor tested, at `price` |
| `unleveredIrr10yr` | decimal | the 10-yr unlevered IRR at `price` (exit at the market exit cap), the figure the IRR floor tested |
| `ust10yr`, `ustAsOf` | decimal / ISO date | the UST basis the IRR floor and refi used (FRED DGS10 30-day average) and its as-of date |
| `vacantSfShareAtClose` | 0..1 | vacant SF share at close |
| `exitCapPct` | decimal | the market exit cap from UNDERWRITING CONVENTIONS |
| `leveredIrr` | decimal | reported-only levered IRR at `price` |
| `underwriteHorizonYrs` | 5 or 10 | the hold the IRR used |
| `clusterTier` | enum | `owned-submarket`, `established`, `entry`, `satellite`, `none` (Gate 3 / Cat 4) |
| `driveMinutesToCluster` | minutes | when measured |
| `marketFundamentalsAdj`, `marketFundamentalsConfidence`, `compSourcedAt` | -1..1 / enum / ISO date | only when the run produced a structured market adjustment |
| `sellerMotivationScore` | 0..1 | Cat 5 points earned / 10 |
| `isVacant` | bool | true only when the building is fully vacant at close |
| `inPlaceRentPsf`, `marketRentPsf`, `marketRentConfidence`, `waltYears` | USD/SF / enum / years | rent roll and COMPS grid |
| `valueAddScore` | 0..1 | Cat 7 points earned / available |
| `ddKnown` | object | STAGE 2.5 keys `flood`, `zoning`, `roof`, `deferred-maintenance-capex`: `true` only when that item is RESOLVED with a source; unresolved = `false` |
| `asAtUtc` | ISO | omit (engine default) |

Fields the packet must not invent: anything the engine derives itself (floors, verdict, composite score, P(exec)). The run's own verdict and floor results go in `notes.sourceVerdict` / `notes.sourceFloors` as text for the reviewer; the engine re-scores from `input`.

## `notes`

- One key per populated `input` field (a combined key such as `hasDock / dockCount` is fine). Value: the source cell or section, e.g. `Returns!B57 stabilized YoC at ask`, `IC memo §6 floor table`, `FEMA FIRM 39049C0310K (2008-06-17)`.
- `left-null`: one string naming every omitted field the engine reads, each with the reason (`clearHeightFt: aerial estimate only [EST]; constructionType: not classified ...`).
- Optional context keys used on the 2026-11-23 packets: `governingSource` (which workbook/memo version governs and what it supersedes), `sourceVerdict`, `sourceFloors`, `tieOutCaveat` (where the engine's result will differ from the run's, e.g. IRR-floor add-ons the contract has no input for).
- `notes` values are strings only.

## Example

`scripts/fixtures/ScreenPacket_100SampleWay_11232026.json`: every figure, id and address is invented.
