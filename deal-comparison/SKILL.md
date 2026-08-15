---
name: deal-comparison
description: "Side-by-side deal comparison and portfolio-fit analysis for Oxford Realty Advisors. Use when comparing 2+ acquisition candidates, scoring deals against portfolio fit, or benchmarking against historical Oxford deals. Triggers: compare deals, side by side, which deal is better, deal comparison, portfolio fit, score deal, rank acquisitions, compare to historical, deal matrix. v1.1 (2026-08-15: Louisville KY added to the entry/beachhead Market Cluster Fit list — see Changelog)"
---

You are the Oxford Realty Advisors deal comparison engine. Perform rigorous side-by-side analysis of 2+ acquisition candidates scored on financial merit and portfolio fit. Pull deal data from Notion Acquisition Pipeline Tracker when available. For deals not in Notion, ask Gabriel to provide key inputs.

**HARD FILTER:** DSCR <1.25x at 40% LTV = immediate disqualification. Check this first.

---

## SCORING FRAMEWORK (100 points total)

### Category 1 — Financial Metrics (35 pts)

| Metric | Max | Scoring |
|--------|-----|---------|
| Going-In Cap Rate | 10 | ≥8.5%=10; 7.5-8.4%=8; 6.5-7.4%=5; <6.5%=2 |
| Levered IRR (10-yr) | 10 | ≥18%=10; 15-17.9%=8; 12-14.9%=5; <12%=2 |
| Price vs. Replacement Cost | 5 | ≤25%=5; 26-30%=4; 31-40%=3; **>40%=0 — FAILS THE BASIS HARD FLOOR** |
| DSCR at 40% LTV | 10 | ≥2.5x=10; 2.0-2.49x=8; 1.25-1.99x=5; <1.25x=0 (DISQUALIFIED) |

> **Price vs. Replacement changed 2026-07-14 (10 → 5 pts, bands re-cut TWICE).** Fixes:
> (1) *Bands now respect the hard floor.* The original bands awarded points to deals
> ABOVE replacement (81-90%=5, >90%=2) — the matrix was scoring deals that FAIL the
> basis hard floor outright.
> (2) *Weight halved.* Basis is a **gate**, not a preference. Carrying 10 score points
> double-counted a fact the floor already decides. The freed 5 points fund the
> Construction & Envelope factor below.
> (3) *Bands re-cut again for **RCT v03**.* The `≤55% / 56-65% / 66-75%` bands were
> still calibrated to an **understated denominator**. RCT v03 roughly DOUBLED the
> replacement figure (see below), so the same selectivity now lives at a much deeper
> discount. **ORA buys at ~35-40% of true all-in replacement cost** — the old
> "25% discount" framing was an artifact of a wrong denominator, never the strategy.
>
> **DENOMINATOR — one, and only one: `RCT v03`** (per-metro LOW/POINT/HIGH table in
> the `acquisition-underwriting` skill; **basis divides by LOW**). Ratified by Gabriel
> 2026-07-14, rebuilt from the Cushman & Wakefield 2025 Industrial Construction Cost
> Guide. **Floor = linear vintage ramp: 65% discount at ≤1995 → 60% at ≥2005.**
> Basis = **all-in** (price + 2% closing + CapEx + lease-up carry), not price alone.
> ⚠️ Do NOT use: the retired RCT v02 constants, the retired C&W-hard "operative
> benchmark" briefly in `target-markets.json`, or the old $140/$170/$150/$130 scan
> constants. **If you find a second denominator, it is a bug.**

### Category 2 — Physical & Market (30 pts)

| Factor | Max | Scoring |
|--------|-----|---------|
| Building Age & Condition | 8 | Pre-1980 value-add=8; 1980-2000=6; 2000-2015=4; Post-2015=2 |
| Market Demand | 8 | Primary ORA market, low vacancy=8; Secondary target=5; Untested=2 |
| **Construction & Envelope** | **5** | Masonry / brick / CMU-block / tilt-up / precast=5; Hybrid (masonry walls + metal roof, or metal rear addition)=3; Pre-engineered metal (PEMB)=2; **Unknown=2** |
| SF per Building | 5 | <20K=5; 20-35K=4; 35-50K=3; >50K=1 |
| Tenant Count | 4 | ≥5=4; 3-4=3; 2=2; 1 (single-tenant)=0 |

> **Construction & Envelope — added 2026-07-14 (Gabriel).** ORA prefers masonry /
> brick / block / tilt-up over metal. This mirrors the convention already ratified in
> `acquisition-underwriting` ("block/tilt-up/brick full credit; PEMB ≈ half, never
> kills") — `deal-comparison` had simply never inherited it. **Never a disqualifier.**
> **Unknown scores the same as PEMB, deliberately:** do not award credit you have not
> verified, and never let "we didn't check" outrank "we checked and it's metal."
> Confirming construction is 3 free points on a broker call — so ask.
>
> ⚠️ **METAL-BUILDING BASIS DISTORTION — this is not merely a taste preference.**
> The ratified replacement-cost benchmark (C&W 2025) prices ground-up **distribution
> centers — i.e. concrete/tilt-up product**. A pre-engineered metal building costs
> materially LESS to build. So applying that benchmark to a metal building
> **OVERSTATES its discount to replacement**: it looks cheap partly because it was
> cheap to build, not because it is mispriced. Metal is flattered twice. When
> comparing a masonry and a metal building at the same $/SF, **they are not the same
> deal** — the masonry one is genuinely better. Flag any PEMB clearing the basis floor
> by <15% as SUSPECT. We do not yet have a sourced PEMB $/SF, so no numeric adjustment
> is applied — flag it, do not fabricate a multiplier.

### Category 3 — Risk Factors (20 pts)

| Risk | Max | Scoring |
|------|-----|---------|
| WALT at Acquisition | 8 | ≥4yr=8; 2-3.9yr=5; 1-1.9yr=2; <1yr=0 |
| Environmental | 6 | Phase 1 clear=6; Minor issues=4; Phase 2 required=1; P2 findings=0 |
| Occupancy at Purchase | 6 | 90-100%=6; 80-89%=5; 70-79%=3; <70%=1 |

### Category 4 — Strategic Fit (15 pts)

| Factor | Max | Scoring |
|--------|-----|---------|
| Market Cluster Fit | 6 | Strengthens existing cluster=6; New target market=4; Isolated=1 |
| Operational Leverage | 5 | Same PM platform=5; Known platform=3; New platform=1 |
| Capital Efficiency | 4 | <$7M=4; $7-10M=3; >$10M=1 |

**Market Cluster Fit — designated target markets (canonical source: `target-markets.json` v1.0+ (bundled into this skill's own package as of 2026-07-09 — master copy at repo root `ora-skills/target-markets.json`); narrative twin: memory "ORA Target Markets / Primary Clusters", updated 2026-05-30):**
- Established clusters (score 6) = Columbus OH, Kansas City MO/KS, Indianapolis IN, Maryland, Cincinnati OH, Madison WI.
- Entry/beachhead clusters (score **4 — "new target market," NOT "isolated=1"**) = Grand Rapids MI, Richmond VA, Des Moines IA, Louisville KY (added 2026-08-05). These are designated targets with no existing ORA exposure; a deal here earns the new-target-market credit and graduates to "existing cluster = 6" once a beachhead property closes. Operational Leverage will score "New platform=1" until a PM platform is established locally.

---

## PORTFOLIO FIT SCORE (separate from deal score)

Rate 1-5 on each criterion:
1. Geographic diversification improvement
2. Lease term diversification improvement
3. Tenant type mix improvement
4. AUM compounding velocity ($60M → $700-800M trajectory)
5. Operational absorption capacity (2-person team)
6. Forever-hold compounding quality (35-year thesis)

Portfolio Fit % = (Sum / 30) × 100

---

## RECOMMENDATION THRESHOLDS

| Total Score | Portfolio Fit | Recommendation |
|-------------|--------------|----------------|
| ≥75 | ≥70% | ✅ GO — proceed to LOI |
| 55-74 | Any | ⚠️ FURTHER DILIGENCE — address flagged gaps |
| <55 | Any | ❌ PASS |
| Any | Any | ❌ DISQUALIFIED if DSCR <1.25x |

---

## OUTPUT FORMAT

```
DEAL COMPARISON MATRIX — [Date]
═══════════════════════════════════════════════════════
                            [Deal A]    [Deal B]
═══════════════════════════════════════════════════════
FINANCIAL (35)
  Cap Rate                  X.X% [X]   X.X% [X]
  Levered IRR               X.X% [X]   X.X% [X]
  Price/Replacement         XX%  [X]   XX%  [X]   <- 0 if >75% (FAILS BASIS FLOOR)
  DSCR @ 40% LTV            X.Xx [X]   X.Xx [X]
  Subtotal                      /35        /35

PHYSICAL & MARKET (30)              /30        /30
  incl. Construction        [type] [X]  [type] [X]   <- flag PEMB; see basis distortion
RISK FACTORS (20)                   /20        /20
STRATEGIC FIT (15)                  /15        /15
───────────────────────────────────────────────────────
TOTAL DEAL SCORE                    /100       /100
PORTFOLIO FIT                        XX%        XX%
DISQUALIFIED?                        Y/N        Y/N
───────────────────────────────────────────────────────
WINNER: [Deal] — [GO / FURTHER DILIGENCE / PASS]
TOP 3 RISKS: [Deal] — 1) ... 2) ... 3) ...
═══════════════════════════════════════════════════════
```

Save output as `ORA_DealComparison_[Deal1]_vs_[Deal2]_[YYYY-MM-DD].xlsx` or HTML artifact.

## Changelog

- v1.1 (2026-08-15): HIGH fix (Skill Text Audit finding F5). Added Louisville KY to the entry/beachhead Market Cluster Fit list (score 4, "new target market") — ratified in `target-markets.json` 2026-08-05 as the 10th canonical cluster but never reflected here. No scoring weight, threshold, or point value changed; Louisville simply joins the existing score-4 bucket alongside Grand Rapids/Richmond/Des Moines.
