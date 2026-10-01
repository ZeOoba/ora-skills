# State Reassessment Matrix (post-sale property tax) — 11 footprint states

Moved verbatim from `SKILL.md` UNDERWRITING CONVENTIONS on 2026-09-22 (v4.23). Load this file whenever a pro-forma reassessed property tax or total carrying cost ($/SF) is computed — the Stage 1 carrying-cost floor, STAGE 2.5 item 5, the OpEx & Carrying Cost tab, and any transfer-tax / entity-deal question. The governing rule stays in `SKILL.md`: property tax = pro-forma reassessed at ORA's purchase price, never the seller's in-place bill; carrying-cost target ≤ $4.00/SF.

### State Reassessment Matrix (post-sale property tax)
| State | Reset behavior | Ratio / cap for reassessed-tax calc | Transfer tax | Entity-deal note |
|---|---|---|---|---|
| MI (Kent/GR) | HIGH — uncaps to SEV (~50% mkt) yr after sale; >50% entity transfer triggers | 50% SEV × millage | ~0.86% | Only footprint state where structure can limit base — but >50% buy uncaps anyway. Controlling-interest reaches entity. |
| IN (Marion) | MED — annual trending, fast | full GAV, **bill capped 3% GAV** | none | No transfer tax; entity moot. |
| WI (Dane) | MED — annual; sale = Tier-1 evidence (Markarian) | full mkt value × mill | 0.30% | No controlling-interest tax. |
| OH (Franklin/Hamilton) | MED-LAG — 6yr reappraisal + 3yr update; HB 126 curbs school-board chase (≥10% AND >$500K) | 35% true value | ~0.30% (county) | No controlling-interest tax; entity avoids conveyance fee. |
| MD | MED-LAG — triennial, increases phase in over 3 yrs | full value × mill | **~2.5–3.5% (outlier)** | **§12-117 taxes >80%/>$1M entity buys** — entity dodge fails. |
| MO (Jackson/Clay) | MED-LAG — biennial odd-yr; Jackson Co >15% increase needs physical inspection | 32% + comm. surcharge | none | Non-disclosure; entity suppresses price feed. |
| VA (Richmond) | MED-LAG — annual/biennial FMV | 100% FMV × mill | ~0.43% | No controlling-interest tax. |
| IA (Polk) | MED-LAG — biennial odd-yr | 100% FMV × **90% comm. rollback** | 0.16% | No controlling-interest tax. |
| TN (Nashville/Memphis) | LOW — 4-yr cycle, NO sale reset, frozen between reappraisals | 40% (real) | 0.37% | No controlling-interest tax. |
| KS (Wyandotte/Johnson) | LOW — already annual FMV; sale = just a comp | 25% | none | Non-disclosure (no SVQ on entity deal). IRB/EDX up to 100%/10yr. |
| IL (Cook) | HIGH — triennial by region (South/West suburbs 2023/2026/2029 · North 2025/2028 · City 2024/2027); CCAO income approach (loaded cap from 2026); sale price is appeal evidence (price disclosed on any appeal within 5 yrs) | 25% of market (comm/ind) × state equalizer (TY2024 final 3.0355; TY2025 tentative 2.8683) × composite rate — derive per parcel: bill ÷ (AV × equalizer) | State $0.50 + County $0.25 per $500; municipal varies (Harvey/Dolton/Posen/South Holland $5 per $1,000; City of Chicago buyer tax [verify]) | Controlling-interest transfers taxed [verify with counsel]; entity purchase does not avoid reassessment |

Abatement/PILOT levers (Edge scan; abate improvements, not basis): KS IRB/EDX (strongest) · MO Ch.100/Ch.353 · TN IDB PILOT · OH CRA/EZ/TIF · IN ERA · MD/VA Enterprise Zone · Cook Class 6b/8 (10% level ×10 yrs → 15% → 20%; new construction, substantial rehab, or reoccupancy after ≥12 months abandoned + municipal resolution; occupied buildings do not qualify).

**MI DEALS — mandatory Prop A pre-mortem line:** [MI deals only] Proposal A taxable-value UNCAP auto-flag: model go-forward tax off the year-after SEV (~50% of market), not the seller's capped Taxable Value. Carry the uncapped-vs-capped DELTA explicitly into NNN occupancy cost and lease-up downtime — it raises tenant occupancy cost and drags absorption even though NNN passes it through. Note the >50% controlling-interest trigger (MCL 211.27a(6)(h)) + ~0.86% deed transfer tax. Validation: 2196 REDACTED-119 — tax ~doubled ($33K→$68K/yr).

See `references/underwrite-model-mechanics.md` for a fully worked MI reassessment example (2900 Northridge Dr, mechanics reference for the OpEx & Carrying Cost tab's reassessment mini-calculator).
