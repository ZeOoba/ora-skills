---
name: census-acs-extract
description: >
  Key-free extraction of U.S. Census ACS 1-Year educational-attainment and
  metro graduate-migration metrics, 2005-2024. Use when the user mentions:
  college graduate migration, brain gain, educated population growth, bachelor's
  degree share by metro, human capital growth, talent attraction, ACS attainment,
  metro graduate counts, where graduates moved, or needs demographic
  human-capital inputs for acquisition underwriting, market monitoring, or
  submarket spatial analysis. Pulls directly from the Census Summary File FTP —
  no API key required. v1.0
---

# census-acs-extract

Reusable engine that computes, for every U.S. Metropolitan Statistical Area, the
population aged 25+ holding a bachelor's degree or higher, and the change in that
stock over any window from 2005 to 2024. Built and validated by Oxford Realty
Advisors, May 2026.

## Why it exists
There is no single Census product that ranks "cities graduates moved to." This
skill reconstructs the metric from primary Census ACS Summary File microdata,
uniformly across three different file-format eras, with **no API key** (the
Census API key is emailed and cannot be retrieved unattended — this avoids that
entirely by reading the public FTP).

## Validation
Parser output matches the Census Bureau's own published Geographic Comparison
Table exactly: 2019 New York-Newark-Jersey City metro = 41.8% bachelor's+.
Anchor-year shares are monotonic and reconcile across windows.

## Metric
"Graduate" = household/civilian population 25+ with a bachelor's degree or higher
(bachelor's + master's + professional + doctorate). This is a **stock-change**
measure — it nets in-migration, out-migration, local degree completion, and
mortality. It is the best uniformly-available proxy for graduate relocation
across a 20-year span; it is not a pure migration flow.

## Usage
```python
from census_acs_extract import extract_metro_attainment, build_growth_panel

# Single year: {cbsa: (metro_name, pop25plus, bachelors_plus, share_pct)}
d = extract_metro_attainment(2024)

# Cross-window panel keyed to endpoint metros, with CBSA crosswalk applied
panel = build_growth_panel([2019, 2014, 2009, 2005], endpoint=2024, min_pop25=200000)
```
Command line: `python census_acs_extract.py 2024`

## Format eras handled automatically
- 2023-2024: table-based Summary File (table B15003)
- 2012-2022: legacy sequence-based SF (B15003)
- 2005-2011: legacy sequence-based SF (B15002; B15003 did not exist pre-2012)

Anchor years 2005/2009/2014/2019/2024 are pre-validated with their exact
sequence numbers and start positions. To add another year, read that year's
lookup file (`.../documentation/.../ACS_1yr_Seq_Table_Number_Lookup.txt`, or
`merge_5_6.txt` for 2009-era), find the table's Sequence Number and Start
Position, and add an entry to the `ANCHORS` dict.

## Caveats baked into the methodology
1. Stock-change, not flow (see Metric).
2. OMB metro boundary revisions (2009/2013/2018/2023): metros matched on CBSA
   code with a manual crosswalk for major renumbered areas (LA 31100->31080,
   Cleveland 17460->17410, Honolulu 26180->46520, Sarasota 42260/14600->35840).
3. 2005 ACS excluded group-quarters population; 2006+ include it.
4. ACS sampling error: closely-ranked metros are not statistically distinguishable.

## Optional speed-up: Census API key
The FTP method needs no key and is the default. For ad-hoc single-variable pulls
a free key (api.census.gov/data/key_signup.html, registered to
ggoldberg@oxfordra.net) enables one-line `api.census.gov` queries; the key is
emailed instantly. Not required for this skill.
