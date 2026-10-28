# Construction-Type RCT Multiplier: Evidence File (v4.37)

Backs the **Construction-Type Multiplier Schedule** in `SKILL.md` (Replacement Cost Table). Compiled from the 2026-10-27 research task for 211 Piper Circle (Annville PA). Figures below are as reported by that research; they were **not re-fetched** when the schedule was merged. Every multiplier is `[EST]` and calibration-pending (see "Open item").

## Sources

| # | Source | What it supports | Data vintage / caveat |
|---|---|---|---|
| 1 | Marshall & Swift, via Michigan State Tax Commission *Assessor's Manual Vol. II*: 2003 edition (CAL 232 / 238) and ©2014 edition (CAL 142 / 146 / 148) | Class S (steel frame) vs. Class C (masonry) whole-building cost ratios and typical economic lives (35 yrs Class S Average vs. 40 yrs Class C Average, industrial shell) | **2003 and 2014 cost tables.** Ratios used, not dollar levels. Ratios hold non-shell costs constant, so the multiplier applies to the full POINT, never to a shell-only share. Secondary reproduction (assessor manual), not the licensed MVS product. |
| 2 | RSMeans-format M.690 Warehouse table | Cross-check on masonry vs. steel-frame warehouse cost spread | **Edition unknown.** Treat as directional only. |
| 3 | Moore Precision Cost, 2013 | Masonry vs. tilt-up at about 0.92 (informs the CMU row, 0.97 after blending with source 1) | **2013 vintage**; a single contractor-published comparison. |
| 4 | MBMA (Metal Building Manufacturers Association) Insurance Bulletin 9 | Metal building (ISO Class 3) carries about 23% higher building loss cost than block with a metal roof (ISO Class 4). Durability context for FORG/BDS only; not scored | Industry-association source; undated in the research notes. |
| 5 | Cushman & Wakefield, 2026 Industrial Construction Cost Guide | Small-tier warehouse hard cost $144/SF, +3.6% YoY. Confirms the tilt-up/precast small tier is the right baseline for RCT v03 | Current (2026). RCT v03 itself is built from the **2025** guide (`cw-2025-construction-costs.json`); the 2026 figure is a drift check, not a table change. |
| 6 | AGC / BLS PPI tables, retrieved 2026-08-13 | Section 232 steel duty raised to 50% on 2025-06-04; PPI to July 2026: steel mill products +22.5%, prefabricated metal buildings +8.6%, concrete block/brick +3.7% | Current. Basis of the tariff note: the PEMB discount may be 1-2 points narrower than the multiplier implies. |

## How the multipliers were set

- **Tilt-up 1.00** is the baseline because the C&W small tier behind RCT v03 is tilt-up/precast.
- **PEMB 0.90 (0.87-0.92, confidence Low until the MVS/RSMeans purchase)** is the most-documented row, still rated Low confidence, rated from the Marshall & Swift Class S vs. Class C whole-building differentials (source 1). The research notes do not restate the underlying ratio or how it was blended with the other sources, so the derivation is not reproducible from this file.
- **CMU 0.97, brick 1.10, hybrid 0.93** are ratified estimates; precast carries no adjustment (1.00, inside the tilt-up/precast baseline; the original 1.03 was withdrawn 2026-10-27); the Moore 2013 masonry-vs-tilt-up figure (about 0.92, source 3) sits at the low edge of the CMU range (0.92-1.00). Confidence Low to Moderate-low as listed in the schedule.
- **PEMB size tilt** (0.88 under ~20,000 SF, 0.90 at 20,000-40,000, 0.92 at 40,000-50,000) is `[EST]` and has no direct source; it reflects the lower relative fixed cost of the structure at small footprints.
- **Vendor claims ignored:** PEMB marketing of "half the cost of tilt-up" compares erected kits to complete buildings.

## Data-vintage caveats (read before relying on a multiplier)

1. The two Marshall & Swift editions are 2003 and 2014. Relative ratios age more slowly than dollar levels, but steel moved sharply after 2018 and again with the 2025 tariff step; the PPI series (source 6) says steel-intensive cost rose faster than masonry, which argues for a narrower PEMB discount than the 2014 ratio.
2. Source 2 has an unknown edition and source 3 is 2013. Neither can anchor a multiplier alone.
3. No source in this file is a current licensed Marshall Valuation Service or RSMeans cost model.

## Open item (carried in QUESTIONS FOR GABRIEL)

Buy one current **Marshall Valuation Service Section 14** page set or an **RSMeans 2026 Square Foot Costs** warehouse model, then re-confirm every multiplier at the **December back-test**. Until then all multipliers stay `[EST]`.

## First application

211 Piper Circle: PEMB, 26,800 SF, multiplier 0.90. Penn Corridor POINT $258.85 (same value as Maryland/Baltimore-DC) x 0.90 + $12 conditioned adder = $244.97; LOW $220.47. Basis walk moved from $2,399,818 to about $2,154,977.
