## TASK 3 — RULED 2026-08-12: fold the comp-grid discipline into `acquisition-underwriting`

**Gabriel's ruling (2026-08-12): option (b) — lift the comp-grid discipline out of the archived `rent-comp` and inline it into `acquisition-underwriting`. Do NOT un-retire `rent-comp`; it stays in `_archive`.**

Background (why this was needed): `_archive/rent-comp_retired-2026-08-05/RETIRED.md` justifies the retirement with *"market-monitor v1.2 absorbed comp-sourcing discipline (confirmed real, KEEP)."* That claim does not survive inspection. market-monitor v1.2's `SOURCING DISCIPLINE` section is about **vendor/operator-published report credibility** — a different thing that happens to share the word "sourcing." Nothing in market-monitor reproduces rent-comp's comp-grid workflow. Meanwhile `acquisition-underwriting` — the single deal-evaluation funnel — cites it in four live places (L166 Phase step, L257 valuation mechanics, L408 COMPS mode definition, L436 data-flow chain). The capability was dropped while its only consumer kept depending on it.

### Lift ONLY sections 1 and 2. Read this before touching anything.

The archived `_archive/rent-comp_retired-2026-08-05/SKILL.md` is 181 lines in 7 sections. **Three of them must not be lifted** — inlining them would reintroduce superseded doctrine:

| Section | Lines | Action |
|---|---|---|
| **§1 RENT COMP RESEARCH WORKFLOW** (Steps 1–5: multi-source search → data extraction → comp table assembly → statistical analysis → normalization) | 12–62 | **LIFT** — this is the "comp-grid discipline" L257 cites by name |
| **§2 SALE COMP RESEARCH WORKFLOW** (Steps 1–3) | 63–88 | **LIFT** — this is the "sale comp grids" half of L408's COMPS mode |
| **§3 REPLACEMENT COST ANALYSIS** | 89–115 | **DO NOT LIFT — CONFLICT.** Uses a superseded component build-up ($85–120/SF hard costs, soft costs 15–20%, dev profit 10–15%). `acquisition-underwriting` already owns replacement cost via **RCT v03** (`config/replacement-cost.v3.json`, Iron rule 11: pull live, never hand-edit). Inlining §3 reintroduces a competing second method — precisely the failure mode of the 2026-07-27 incident logged as *"Off-market master: $150/SF benchmark caught and reverted against the 2026-07-14 RCT v03 ratification."* |
| **§4 MARKET CONTEXT OVERLAY** | 116–126 | Do not lift — market-level context is `market-monitor`'s scope |
| **§5 OUTPUT FORMATS** | 127–146 | Do not lift — formats for a standalone skill that no longer exists; `acquisition-underwriting` has its own mode outputs |
| **§6 OXFORD MARKET BENCHMARKS** | 147–171 | **DO NOT LIFT — DUPLICATE.** A hand-maintained rent/cap/price-PSF table whose own header admits it must be *"kept in parity with"* `target-markets.json`. That file is already bundled into `acquisition-underwriting` as a `SHARED_ROOT_DEPS` consumer. Lifting §6 creates a second drifting copy of canonical market data. Cite `target-markets.json` instead. |
| **§7 CROSS-SKILL INTEGRATION** | 172–178 | Do not lift — plumbing for a retired skill |

Net lift: roughly 75 lines, not 181.

### Then rewire the four references

Once §1–§2 are inlined (suggested home: a `COMP GRID DISCIPLINE` subsection under UNDERWRITING CONVENTIONS, adjacent to the existing RCT material so the boundary between comp-based and cost-based valuation stays visible):

- **L166** — *"refresh the rent-comp grid (`rent-comp` skill)"* → point at the new in-skill section.
- **L257** — *"per the `rent-comp` skill's comp-grid discipline"* → point at the new in-skill section.
- **L408** — *"rent + sale comp grids per rent-comp skill"* → point at the new in-skill section.
- **L436** — the cross-skill data-flow chain opens with `rent-comp` as its first node. Remove that node and re-anchor the chain on `market-monitor`, which is what actually feeds it now.

Also update `_archive/rent-comp_retired-2026-08-05/RETIRED.md` with a correction note: the original "market-monitor absorbed it" rationale was wrong, the comp-grid discipline was inlined into `acquisition-underwriting` on 2026-08-12, and §3/§6 were deliberately left behind as superseded. A wrong retirement record is how this stayed invisible for a week.

### Version + reimport

`acquisition-underwriting` is already pending reimport from `0f5c23a`, so this folds into a package-and-stage pass you owe regardless. Bump the version, note the inlining in the changelog, and run Entry point A. Its ledger entry clears only on a confirmed Save-skill click plus verified cache re-sync.

### One thing to raise with Gabriel afterward, not now

`rent-comp` was retired on a "zero-use" finding, but it was invoked *by* `acquisition-underwriting` rather than by name — which is exactly what zero direct use looks like for a skill-invoked skill. The same audit retired five others the same day (`census-acs-extract`, `code-debugging-optimizations`, `maintenance-analytics`, `oxford-cc-strategic-audit`, `re-operations`). `census-acs-extract` shows the same signature: `submarket-spatial-analysis` names it as the source for Location Score component 4. Worth a re-audit pass that counts skill-to-skill references, not just direct invocations.
