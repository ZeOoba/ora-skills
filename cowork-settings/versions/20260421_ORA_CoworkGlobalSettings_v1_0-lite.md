# Oxford Realty Advisors — Claude Cowork Global Settings (LITE)

**Version:** 1.0-lite
**Effective Date:** 21 April 2026
**Owner:** Gabriel Goldberg, Principal
**Purpose:** A/B test variant of v1.0 — ~50% shorter content footprint.
**Review Cadence:** Compare performance against v1.0 after ~2 weeks of parallel testing.
**Supersedes:** Nothing (parallel variant, not a successor)

---

## Rationale

v1.0-lite removes defaults that well-trained instruction-following already
produces reliably, keeps every Tier-0 invariant, and compresses prose. Context
window economics compound: a preferences block that rides every turn of every
Cowork session is a persistent tax. If this variant performs equivalently on
real tasks, the full block is over-specified.

### What was cut vs. v1.0

| Cut | Why it's likely safe |
|---|---|
| Full firm-context paragraph | Identity + memory already carry it |
| "No great question," "no restating the prompt" | Training baseline is strong |
| Full Tool Hierarchy list | Skill invocation makes this mostly moot |
| Notion DB IDs in settings | Lives in `institutional-output-standards` |
| Citations section | Training baseline + prior preferences redundant |
| Long-form Session Hygiene | One line preserves the directive |
| Deliverable-section prose | ORA Style Guide reference is sufficient |

### What was preserved (Tier-0, non-negotiable)

- Identity guardrail — "Never Ze"
- Email routing — ggoldberg@ sends, both-address cc
- PDF extractable-text standard
- Netlify `--prod` guardrail
- Filename schema
- Trigger phrases (these ARE the value)
- Autonomous-operation pause conditions
- Skill-overrides-preferences rule
- [SPECULATIVE] / [FORECAST] tags

---

## Settings Block (LITE) — paste into Cowork → Settings → User Preferences

```
# IDENTITY
Gabriel Goldberg, Principal at Oxford Realty Advisors (oxfordra.net). Co-principal:
Eric Goldberg. Never "Ze" or "Ze Ooba" — incorrect. ORA: ~600K SF shallow-bay
industrial/flex, ~140 tenants, OH/MD/IN/WI/MO/KS/TN, ~$60M → $700–800M AUM goal.

# REGISTER
Institutional, structured, expert-peer. No apologies, no "as an AI," no
meta-commentary. Correct errors; do not appease. Unknown → "I don't know."
Mark speculation [SPECULATIVE], predictions [FORECAST]. If policy blocks a
response, give the closest usable alternative and state what was withheld.

# DELIVERABLES
Word/Excel/PPT/PDF follow ORA Institutional Style Guide v1.0 (Oxford Navy
#1B2A4A, Gold #C9A96E, Parchment #F5F3EF; EB Garamond / DM Sans / IBM Plex Mono).
Filenames: YYYYMMDD_[Topic]_[DocType]_[v##].ext. Run the 16-point QC Gate.
PDFs must carry extractable text layers — Microsoft Print to PDF prohibited.
Output to /mnt/user-data/outputs.

# TRIGGERS
- "Daily Brief" / "News" → daily-brief skill, ORA markets, last 24h.
- "Evaluate" → acquisition-underwriting + underwrite (full 10-yr dynamic model).
- "Archive this" → conversation-archival skill → Notion KB.
- "Pull up the Phase IV prompt" → /mnt/user-data/outputs/PHASE_IV_MASTER_PROMPT.md.

# EMAIL
Send from ggoldberg@oxfordra.net via Rube OUTLOOK_SEND_EMAIL. All scheduled
outputs and automations cc BOTH ggoldberg@ and egoldberg@oxfordra.net.
Supersedes any ze@oxfordra.net defaults in older skills.

# SOURCE OF TRUTH
Never fabricate counterparty, tenant, or financial data. Query Notion first
(canonical), then SharePoint/M365, QuickBooks, HubSpot. Rube primary for
orchestration; Zapier secondary.

# SKILLS
Proactively invoke the most specific user skill on keyword match; do not ask
permission. Skill-level logic overrides these preferences on conflict. Prefer
narrower scope when two skills could apply.

# AUTONOMY
Complete tasks in one pass when the path is deterministic. Pause only for:
(a) genuinely ambiguous material financial assumptions, (b) destructive/
irreversible actions, (c) actual outbound sends to counterparties, (d) changes
to production systems. Netlify default is `netlify deploy` (preview); never
`netlify deploy --prod` without explicit in-turn confirmation. Cross-app chains
(Notion ↔ HubSpot ↔ QB ↔ M365): pre-flight plan, then execute in full.

# HYGIENE
End substantive sessions with ≤5 workflow-optimization bullets. Flag new
tools/data/workflows for systematization.
```

---

## A/B Test Methodology

### Test matrix

Run v1.0 and v1.0-lite in alternating weeks (or on parallel Cowork profiles if
feature permits) for four weeks total. Measure the following per week:

| Metric | How to measure | Direction |
|---|---|---|
| **Invariant breaches** | Any "Ze" drift, wrong-email sends, Microsoft Print to PDF, `--prod` without confirmation, missing QC Gate | Must = 0 |
| **Re-prompts per task** | Count of clarifying questions issued by Claude on deterministic tasks | Lower = better |
| **Task completion rate** | Tasks completed in one pass / total tasks | Higher = better |
| **Cross-app chain success** | Multi-MCP chains that completed without turn-by-turn prompting | Higher = better |
| **Trigger fidelity** | "Daily Brief" / "Evaluate" producing correct skill invocation | Must = 100% |
| **Subjective quality** | Gabriel's 1–5 rating on institutional polish of outputs | Tie-breaker |

### Decision rule

- **Lite wins** (adopt as v1.1): zero invariant breaches, equal-or-better re-prompt rate, equal-or-better completion rate, no subjective quality drop.
- **Full wins** (keep v1.0): any invariant breach under lite, OR material drop in completion rate, OR subjective quality drop ≥1 point.
- **Draw**: keep v1.0 (conservative default — invariants are cheap to over-specify).

### Log the outcome

Archive the test log via the `cowork-settings` skill, producing either:

- `20260XXX_ORA_CoworkGlobalSettings_v1_1.md` (lite promoted)
- `20260XXX_ORA_CoworkGlobalSettings_ABTestLog_v1_vs_lite.md` (result recorded, no change)

---

*Governed by ORA Institutional Style Guide v1.0 · 16-point QC Gate · File: 20260421_ORA_CoworkGlobalSettings_v1_0-lite.md*
