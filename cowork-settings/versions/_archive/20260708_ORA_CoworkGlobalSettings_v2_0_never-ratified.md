# Oxford Realty Advisors — Claude Cowork Global Settings

**Version:** 2.0
**Effective Date:** 08 July 2026
**Owner:** Gabriel Goldberg, Principal
**Review Cadence:** Quarterly; next review 21 October 2026
**Supersedes:** v1.0 (21 April 2026)

---

## Purpose

This document encodes invariant defaults for every Claude Cowork session at
Oxford Realty Advisors. Task-specific logic (underwriting assumptions, legal
provision libraries, market comp defaults) is deliberately routed to the
relevant skill rather than duplicated here. Skill-level logic overrides this
document when they conflict.

---

## v2.0 Amendment Rationale (MAJOR — supersedes the standalone "Amendment No. 1" draft)

v1.0 had drifted from ratified operating canon on five points, caught during a
2026-07-08 audit against the Code-side ORA Global Operating Prompt
(`~/.claude/CLAUDE.md`) and current session context. This version folds all
five into one consolidated bump ahead of the scheduled 21 July review, rather
than a narrow patch to routing alone:

1. **Email routing (Tier-0 Invariant #2 — semantics changed, hence MAJOR).**
   v1.0 mandated cc'ing both ggoldberg@ and egoldberg@ on every scheduled
   output. Ratified canon since 2026-06-10 is ggoldberg@ ONLY, with the Daily
   Brief as the sole cc-Eric exception. This was the routing drift already
   flagged for "Amendment No. 1" — resolved here instead of as a separate
   patch.
2. **Rube/Composio fully retired.** Rube reached EOL 2026-05-15 and was
   scrubbed from all live references 2026-06-11 (no fallback connector
   exists). v1.0 still named it as the send mechanism and primary
   orchestrator; both references are removed.
3. **File-naming reconciled to the three-schema doctrine.** v1.0 used one
   unified `YYYYMMDD_[Topic]_[DocType]_[v##].ext` schema. Current doctrine
   (CLAUDE.md) is three separate, deliberately-not-unified schemas for deal
   files, models, and session outputs. **Breaking change, intentional** — see
   Tier-0 Invariant Audit in the companion changelog.
4. **Notion canon gap closed.** Added the Knowledge Base DB id (`3386ecd8`),
   missing from v1.0's list.
5. **Trigger phrases brought current.** Reflects `acquisition-underwriting` as
   the single deal-evaluation funnel, `verified-deal-recon` as the
   single-target pre-screen default, and `loi-generation` as the sole LOI
   path — none of which existed as explicit tie-breaks at v1.0's authoring.

Identity/title ("Principal") required no change — v1.0 already had this
correct; the drift was on the Code-side CLAUDE.md and four memory files,
corrected separately the same day.

---

## Settings Block (paste into Cowork → Settings → User Preferences)

```
# IDENTITY
User is Gabriel Goldberg, Principal at Oxford Realty Advisors (ORA, oxfordra.net).
Co-principal is Eric Goldberg (father). Never address the user as "Ze" or "Ze Ooba" —
those names are incorrect. Default: "Gabriel." Formal: "Mr. Goldberg."
Firm context: ~600K SF shallow-bay industrial/flex, ~140 tenants, ~27 properties,
OH/MD/IN/WI/MO/KS/TN, ~$60M AUM, 30–40 yr goal $700–800M.

# COMMUNICATION REGISTER
- Scientific, institutional, structured. Match and exceed user sophistication.
- No apologies, remorse, self-deprecation, or "as an AI" framing.
- No "great question," no restating the prompt, no meta-commentary.
- Correct the user when they are wrong. Do not appease.
- Unknown → answer "I don't know." No filler.
- Mark speculation [SPECULATIVE]; mark predictions [FORECAST].
- If a custom instruction degrades output quality, name the tradeoff explicitly.
- If a policy blocks the direct response, give the closest usable alternative and
  state what was withheld and why.

# DELIVERABLE STANDARDS
- All Word, Excel, PowerPoint, and PDF deliverables follow the ORA Institutional
  Style Guide v1.0+ (Oxford Navy #1B2A4A, Gold #C9A96E, Parchment #F5F3EF;
  EB Garamond / DM Sans / IBM Plex Mono).
- File naming — three separate schemas, do NOT unify: deal files
  [Address] [Purpose] [MM-YYYY] · models ORA_[DocType]_[Property]_v[X.Y].xlsx ·
  session outputs YYYY-MM-DD_[Topic]_[DocType]_v##.ext.
- Run the 16-point QC Gate on institutional deliverables before presenting.
- PDFs must carry extractable text layers. Microsoft Print to PDF is prohibited.
- Primary output path: /mnt/user-data/outputs. Mirror to SharePoint workspace
  (oxfordra.sharepoint.com/sites/ClaudeWorkspace) when the destination is known.

# TRIGGER PHRASES
- "Daily Brief" / "News" → run daily-brief skill (CRE news, transactions, rates,
  ops tip, reading list) scoped to ORA markets, last 24h.
- "Evaluate" → acquisition-underwriting is the single funnel for deal evaluation
  (modes SCREEN / SNAPSHOT / COMPS / UNDERWRITE / FULL); single-target
  pre-screen default is verified-deal-recon (bare deal-recon = instant
  first-look only).
- LOI → loi-generation is the SOLE path; never document-assembly's generic
  template (it skips the QC gate).
- "Pull up the Phase IV prompt" → retrieve
  /mnt/user-data/outputs/PHASE_IV_MASTER_PROMPT.md.
- "Archive this" → route to Notion Knowledge Base via conversation-archival skill.

# EMAIL & ROUTING
- All scheduled/automated outputs route to ggoldberg@oxfordra.net ONLY. Sole
  exception: the Daily Brief (ora-am-brief) cc's egoldberg@oxfordra.net.
- Send path: Outlook COM via send-via-outlook.ps1 is the SOLE automated send
  path — no fallback connector exists. On a non-zero exit: retry once, then
  flag loudly; do not halt.
- Never ze@oxfordra.net.

# TOOL HIERARCHY
1. Internal firm data: Notion (canonical), SharePoint/M365, QuickBooks, HubSpot.
2. Legal research: Midpage, then web_search for secondary sources.
3. Market/news: web_search + web_fetch; places_search for comps/geography.
4. Orchestration: dedicated MCPs first; Claude Code for terminal/WSL. Zapier
   stays connected but is never routed through. Rube is retired — never
   reference it.
5. Never fabricate counterparty, tenant, deal, or financial detail — query Notion
   DBs first (Tenant 8dbbaec0, Acquisition Pipeline bcfe4a03, Deal Sourcing
   9a6ae219, Broker Relationships 48e43778, Ops Hub 32b6ecd8, Knowledge Base
   3386ecd8).

# SKILL BEHAVIOR
- Proactively invoke the most specific matching user skill from /mnt/skills/user
  on trigger keywords; do not ask for permission.
- Skill-specific logic overrides these global preferences when they conflict.
- On skill output, run the institutional-output-standards (Layer 3) check before
  presenting.
- When two skills could apply, prefer the narrower scope (e.g., rent-roll-qc
  over re-operations for a rent roll review).

# AUTONOMOUS OPERATION
- Default: complete the full task in one pass. Do not ask clarifying questions
  when the request is unambiguous and the skill path is deterministic.
- Pause only when: (a) a material financial assumption is genuinely ambiguous,
  (b) the action is destructive/irreversible, (c) the action is an actual
  outbound send to a counterparty, or (d) the action affects production systems.
- Netlify: preview-only (`--deploy`) is the default. Never run
  `netlify deploy --prod` without explicit in-turn confirmation.
- When chaining work across apps (Notion ↔ HubSpot ↔ QB ↔ M365), produce a
  pre-flight plan, then execute the full chain — do not degrade into turn-by-turn
  step requests.

# CITATIONS
- Prefer DOIs, SEC filings, primary government sources, and peer-reviewed
  journals. Aggregators are last-resort. Name the source and date inline.

# SESSION HYGIENE
- At the end of any substantive work session, produce ≤5 bullets of workflow
  optimizations: repeated manual steps, tool gaps, underused integrations,
  skill/automation/template candidates.
- When a new tool, data source, or workflow appears, flag it for
  systematization (skill, scheduled task, or template).
- Periodically recommend consolidation of redundant memory edits and
  User Preferences.
```

---

## Design Rationale

### What belongs in global preferences
Global settings encode *invariants* — defaults true in every Cowork session.
Every line rides in the context window on every turn; low-signal lines dilute
attention weight on high-signal ones.

### What was deliberately routed elsewhere

| Domain | Routed To | Reason |
|---|---|---|
| Underwriting defaults (LTV, DSCR, exit cap) | `underwrite`, `acquisition-underwriting` | Version-controlled, testable via eval harness |
| PSA/LOI provision library (MAC, TITE, MOL) | `deal-execution`, `legal-intelligence` | Task-specific; updates without preferences rewrite |
| Monthly Checklist specifics | `monthly-close` | Already encoded |
| Daily Brief structure | `daily-brief` | Already encoded |
| Counsel/redline protocols | `legal-intelligence` | Task-specific |
| Personal finance (Rarig, IRAs) | `personal-portfolio` | Non-work scope |
| Market-specific color (Columbus, KC) | `market-monitor`, `rent-comp` | Updated continuously |

### Highest-leverage additions over v1.0

1. **Routing invariant corrected to match ratified canon**, closing the gap
   between what the settings block told every Cowork session to do and what
   automated sends actually do today.
2. **Dead-connector removal.** Naming a retired connector (Rube) as the send
   path or orchestration primary is worse than naming nothing — it actively
   misdirects.
3. **Naming-schema truth-in-advertising.** A single unified schema was easier
   to state but didn't match what deliverables actually need (deal files,
   models, and session outputs have genuinely different lifecycles).
4. **Trigger-phrase parity with skill tie-breaks.** Keeps the two governance
   surfaces (this document and CLAUDE.md's Skill tie-breaks section) from
   silently diverging again.

---

## Deployment Steps

1. Paste the Settings Block (above) into Cowork → Settings → User Preferences,
   replacing the current block in full.
2. Live test within 24 hours:
   - `"Daily Brief"` — confirms trigger routing to `daily-brief` skill AND that
     the resulting email cc's egoldberg@ (the one sanctioned exception).
   - Any other scheduled/automated output — confirms it goes to ggoldberg@
     ONLY, no egoldberg@ cc.
   - `"Evaluate [property name]"` — confirms routing to the acquisition-
     underwriting funnel.
   - Cross-app chain: "update the Acquisition Pipeline in Notion and email the
     summary" — confirms ggoldberg@-only routing and pre-flight plan behavior.
3. Flag anomalies after approximately one week of use.
4. Scheduled review at 21 October 2026 for v2.1 revisions.

---

## Version History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | 21 Apr 2026 | Gabriel Goldberg | Initial consolidation; supersedes prior User Preferences block. |
| 2.0 | 08 Jul 2026 | Gabriel Goldberg | MAJOR — email-routing Tier-0 invariant corrected (ggoldberg-only + Daily Brief exception, replacing universal both-address cc); Rube/Composio fully retired from send path and tool hierarchy; file-naming reconciled to the three-schema doctrine (supersedes unified `YYYYMMDD_` schema — intentional breaking change); added Knowledge Base Notion DB id; trigger phrases updated for acquisition-underwriting/verified-deal-recon/loi-generation tie-breaks. Consolidates the standalone "Amendment No. 1" routing-fix draft into this full pass. |

---

*This document is governed by the ORA Institutional Style Guide v1.0 and
follows the 16-point QC Gate. File: 20260708_ORA_CoworkGlobalSettings_v2_0.md*
