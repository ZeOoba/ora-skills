---
name: masterlease-jurisdiction-rebase
description: "Rebase Oxford Realty Advisors jurisdiction-conformed Master Lease property templates onto a new master revision in one command, and generate state-conformed (MD/MO) property templates from the OH-anchored master. Use whenever the user mentions: new master lease version, rebase the lease templates, regenerate the MD/MO templates, jurisdiction overlay, conform the lease to a state, state-conformed lease template, update property lease forms, lease template for Easton / Salisbury / Northwood / Raytown, or uploads a new ORA_MasterLease_ShallowBayIndustrial_v*.docx. Also use when adding a NEW property or state overlay to the lease-template system. Edits the master DOCX in place (native formatting preserved) with asserted-count substitutions — the anti-contamination discipline from the 2026-08-03 propagation audit. Companion to lease-form-qc (which QCs drafted leases); this skill produces the templates leases are drafted FROM. v1.0 (2026-08-03)"
---

# Master Lease Jurisdiction Rebase — Oxford Realty Advisors

One-command regeneration of state-conformed property lease templates whenever the
controlled master (`ORA_MasterLease_ShallowBayIndustrial_v*.docx`) revs. Built from the
2026-08-03 conformance session, where it produced the MD-EAS / MD-SBY / MO-RAY v2.2
variants and then rebased them onto v2.4 with zero manual edits.

## Why this exists

The 2026-08-03 propagation audit proved that hand-copying leases spreads defects
(34–36/39 failures on every executed lease; ZIP cross-contamination between properties).
The same failure mode applies to templates: hand-porting jurisdictional edits onto each
new master revision silently drops or duplicates clauses. This engine applies every
jurisdictional change as an **asserted-count substitution** — if an anchor string moved
or vanished in the new master, the run fails loudly and names the anchor, instead of
producing a quietly wrong template.

## Canonical master — the drift rule

**Never build from a cached or knowledge-store copy of the master.** Version drift
happened twice on 2026-08-03 (a v2.1 cache was used while v2.4 was canonical).

- Canonical location: **UNRESOLVED — SharePoint search finds no copy of the master
  (verified 2026-08-03).** Ask Gabriel for the current master, or have him upload it.
  When he pins a SharePoint path, record it here (edit this section) and in
  memory/rules.md on the Code surface.
- Freshness check before any run: compare the version string in the supplied master's
  filename (`v2.4` etc.) against the newest version mentioned anywhere in the session
  and in this skill's changelog. If the supplied master is not the highest version
  known, stop and ask which is canonical.
- The six ratified standing lease positions (2026-08-03, carried in `lease-form-qc`)
  are baked into the master. This skill must never alter them: modified gross /
  calendar base year · co-tenancy not guaranty · 1.0× deposit · 10% late fee + 18%
  default interest (savings clause is allowed and included; silent reduction is not) ·
  flat Hazardous Materials ban · no extension option.

## How to run

```bash
python3 scripts/rebase.py --master <path/to/ORA_MasterLease_..._vX.Y_TEMPLATE.docx> \
    --property MD-EAS --out <output-dir>
# or all configured properties:
python3 scripts/rebase.py --master <master.docx> --all --out <output-dir>
```

Outputs `ORA_MasterLease_ShallowBay_<property>_vX.Y_TEMPLATE.docx` per property —
the master edited in place (python-docx cross-run splice), so native formatting,
numbering, styles, headers and exhibits survive untouched.

The script:
1. Loads `config/properties.json` (property facts) and `config/state_overlays.json`
   (state law tables).
2. Applies every substitution with an expected match count; any mismatch aborts with
   the anchor named.
3. Inserts the Maximum Lawful Rate savings clause after Counterparts (cloned styling;
   skipped if already present).
4. Post-checks: zero residue of the master's anchor state, zero unfilled entity/state
   tokens, savings clause present and positioned, state statutes at expected counts.

## When a run fails (anchor drift)

An assertion failure means the new master changed the anchor text — that is the system
working. Diff the new master against the prior one (pandoc to text is fine), update the
anchor in `scripts/rebase.py` or the configs, note the change in the changelog below,
and re-run. Never loosen an assertion to "0 or 1" to make a run pass.

## Adding a property or state

- New property in MD/MO: add an entry to `config/properties.json` (entity from the
  executed-lease record or the ratified LLC roster — never invented; SF from the
  Portfolio Basis workbook / Master Workbook; PM block from executed-lease practice,
  tokens where unknown).
- New state (IN/WI/KS/TN are pre-listed as RESEARCH-REQUIRED): complete the state's
  entry in `config/state_overlays.json` with fresh statutory research — UETA citation,
  possession/eviction statutes, holdover statute, environmental overlay, parcel-number
  nomenclature, plus any state-specific clause (Maryland's §3-101(e) memorandum-of-lease
  proviso is the model, keyed by the `extra_no_recording` field). Do not copy another
  state's citations as scaffolding; an empty field fails closed.

## Facts provenance (do not re-derive from leases)

Entity names (29000 INFORMATION LANE, LLC · 2203 NORTHWOOD, LLC · 9620 STATE 350, LLC)
were sourced from executed leases on 2026-08-03. Building SF (48,000 / 53,700 / 34,560)
from the Portfolio Basis workbook. Salisbury ZIP 21801 from an executed lease — county
verification still open. ZIPs, suites, parcel/tax-account numbers, per-building Northwood
RSF, and the Raytown PM block are deliberately tokenized: fill at drafting time from the
county record or PM agreement, and run `lease-form-qc` on every drafted lease before it
leaves the office.

## Changelog

- v1.0 (2026-08-03): Engine extracted from the v2.2 build + v2.4 rebase session.
  Anchors keyed to master v2.4. MD (Talbot/Wicomico) and MO (Jackson) overlays ratified;
  IN/WI/KS/TN stubs fail closed pending research.
