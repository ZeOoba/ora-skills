# census-acs-extract — Integration Hooks

How the existing ORA skills consume the human-capital dataset. The canonical
data product is `metro_graduate_growth_panel.csv` (174 MSAs ≥200k adults 25+,
four windows: 5/10/15/20-yr ending 2024). Columns per metro: `grads_end`,
`share_end`, and for each base year {2019,2014,2009,2005}: `net_*` (graduate
gain), `pct_*` (growth %), `dshare_*` (bachelor's-share change, ppt).

## 1. market-monitor
Add a "Human Capital" line to each market profile. For a target metro's CBSA
code, surface `pct_2014` (10-yr graduate-population growth) and `dshare_2014`
(brain-gain intensity) alongside vacancy/rent/absorption. Refresh annually when
the new ACS 1-Year lands (each September).
- Hook: `build_growth_panel([2014], endpoint=<latest>)` filtered to the metro.

## 2. acquisition-underwriting
Inject a demand-side demographic factor into the screen. A submarket in a metro
with top-quartile 10-yr graduate growth supports stronger rent-growth and
absorption assumptions for shallow-bay/flex tenant demand. Use `pct_2014` decile
rank as a 0-1 "human-capital tailwind" input to the underwriting model.
- Hook: join the OM's metro CBSA to `metro_graduate_growth_panel.csv`.

## 3. submarket-spatial-analysis
The panel is metro-level; pair it with the spatial skill's drive-time/employment
layers to weight locations by metro-wide talent trajectory. Use `share_end`
(current attainment level) for the static quality score and `dshare_2009`
(15-yr trend) for momentum.
- Hook: metro CBSA as the join key; spatial skill provides intra-metro geometry.

## ORA target-market quick reference (10-yr, 2014→2024)
| Metro | CBSA | 10-yr graduate gain | growth | Δ share |
|---|---|---|---|---|
| Columbus, OH | 18140 | +150,620 | +32.7% | +5.6 ppt |
| Kansas City, MO-KS | 28140 | +149,873 | +31.2% | +6.0 ppt |
| Indianapolis, IN | 26900 | +167,421 | +40.7% | +7.8 ppt |
| Nashville, TN | 34980 | +251,872 | +65.6% | +11.2 ppt |
(All ORA target markets show above-replacement graduate growth. Full values and
other windows live in metro_graduate_growth_panel.csv — filter by CBSA.)

## Refresh cadence
Census releases ACS 1-Year each September for the prior year. Re-run
`build_growth_panel([...], endpoint=<new year>)` after release; add the new
endpoint year to the `ANCHORS` dict if it is the first time that format-era year
is used (table-based years 2023+ need no new parameters).
