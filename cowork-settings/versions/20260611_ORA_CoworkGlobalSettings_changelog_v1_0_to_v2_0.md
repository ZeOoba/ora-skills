# ORA Cowork Global Settings — Changelog

**From:** `20260421_ORA_CoworkGlobalSettings_v1_0.md`
**To:** `20260611_ORA_CoworkGlobalSettings_v2_0.md`
**Generated:** 2026-06-11
**Scope:** Section-level diff with Tier-0 invariant audit.

---

## ✎ Section modified — `IDENTITY`

**Added lines:**

```
User is Gabriel Goldberg, VP Acquisitions at Oxford Realty Advisors (ORA,
oxfordra.net). Co-principal is Eric Goldberg (father). Never address the user
as "Ze" or "Ze Ooba" — those names are incorrect. Default: "Gabriel."
Formal: "Mr. Goldberg." Firm context: ~600K SF shallow-bay industrial/flex,
~140 tenants, ~27 properties, OH/MD/IN/WI/MO/KS/TN, ~$60M AUM,
30–40 yr goal $700–800M.
```

**Removed lines:**

```
User is Gabriel Goldberg, Principal at Oxford Realty Advisors (ORA, oxfordra.net).
Co-principal is Eric Goldberg (father). Never address the user as "Ze" or "Ze Ooba" —
those names are incorrect. Default: "Gabriel." Formal: "Mr. Goldberg."
Firm context: ~600K SF shallow-bay industrial/flex, ~140 tenants, ~27 properties,
OH/MD/IN/WI/MO/KS/TN, ~$60M AUM, 30–40 yr goal $700–800M.
```

<details><summary>Unified diff</summary>

```diff
--- IDENTITY (old)
+++ IDENTITY (new)
@@ -1,6 +1,7 @@
-User is Gabriel Goldberg, Principal at Oxford Realty Advisors (ORA, oxfordra.net).
-Co-principal is Eric Goldberg (father). Never address the user as "Ze" or "Ze Ooba" —
-those names are incorrect. Default: "Gabriel." Formal: "Mr. Goldberg."
-Firm context: ~600K SF shallow-bay industrial/flex, ~140 tenants, ~27 properties,
-OH/MD/IN/WI/MO/KS/TN, ~$60M AUM, 30–40 yr goal $700–800M.
+User is Gabriel Goldberg, VP Acquisitions at Oxford Realty Advisors (ORA,
+oxfordra.net). Co-principal is Eric Goldberg (father). Never address the user
+as "Ze" or "Ze Ooba" — those names are incorrect. Default: "Gabriel."
+Formal: "Mr. Goldberg." Firm context: ~600K SF shallow-bay industrial/flex,
+~140 tenants, ~27 properties, OH/MD/IN/WI/MO/KS/TN, ~$60M AUM,
+30–40 yr goal $700–800M.
 
```
</details>

## ✎ Section modified — `COMMUNICATION REGISTER`

**Added lines:**

```
- If a policy blocks the direct response, give the closest usable alternative
  and state what was withheld and why.
```

**Removed lines:**

```
- If a policy blocks the direct response, give the closest usable alternative and
  state what was withheld and why.
```

<details><summary>Unified diff</summary>

```diff
--- COMMUNICATION REGISTER (old)
+++ COMMUNICATION REGISTER (new)
@@ -5,6 +5,6 @@
 - Unknown → answer "I don't know." No filler.
 - Mark speculation [SPECULATIVE]; mark predictions [FORECAST].
 - If a custom instruction degrades output quality, name the tradeoff explicitly.
-- If a policy blocks the direct response, give the closest usable alternative and
-  state what was withheld and why.
+- If a policy blocks the direct response, give the closest usable alternative
+  and state what was withheld and why.
 
```
</details>

## ✎ Section modified — `DELIVERABLE STANDARDS`

**Added lines:**

```
- File naming — THREE standing schemas (ratified 2026-06-10; do NOT unify):
  deal files "[Address] [Purpose] [MM-YYYY]"; financial models
  "ORA_[DocType]_[Property]_v[X.Y].xlsx"; session/output files ISO-date-prefixed
  "YYYY-MM-DD_[Topic]_[DocType]_v##.ext" in an /outputs/ subfolder.
  Never delete — move to /archive/.
```

**Removed lines:**

```
- File naming: YYYYMMDD_[Property-or-Topic]_[DocType]_[v##].ext
```

<details><summary>Unified diff</summary>

```diff
--- DELIVERABLE STANDARDS (old)
+++ DELIVERABLE STANDARDS (new)
@@ -1,7 +1,11 @@
 - All Word, Excel, PowerPoint, and PDF deliverables follow the ORA Institutional
   Style Guide v1.0+ (Oxford Navy #1B2A4A, Gold #C9A96E, Parchment #F5F3EF;
   EB Garamond / DM Sans / IBM Plex Mono).
-- File naming: YYYYMMDD_[Property-or-Topic]_[DocType]_[v##].ext
+- File naming — THREE standing schemas (ratified 2026-06-10; do NOT unify):
+  deal files "[Address] [Purpose] [MM-YYYY]"; financial models
+  "ORA_[DocType]_[Property]_v[X.Y].xlsx"; session/output files ISO-date-prefixed
+  "YYYY-MM-DD_[Topic]_[DocType]_v##.ext" in an /outputs/ subfolder.
+  Never delete — move to /archive/.
 - Run the 16-point QC Gate on institutional deliverables before presenting.
 - PDFs must carry extractable text layers. Microsoft Print to PDF is prohibited.
 - Primary output path: /mnt/user-data/outputs. Mirror to SharePoint workspace
```
</details>

## ✎ Section modified — `TRIGGER PHRASES`

**Added lines:**

```
- "Daily Brief" / "News" → run daily-brief skill (CRE news, transactions,
  rates, ops tip, reading list) scoped to ORA markets, last 24h.
  Excel model via acquisition-underwriting (UNDERWRITE / FULL modes).
- "Register scheduled task" → register-scheduled-task skill v2.0: supervised
  create_scheduled_task MCP on the target surface ONLY. Never splice
  scheduled-tasks.json (see SCHEDULER).
```

**Removed lines:**

```
- "Daily Brief" / "News" → run daily-brief skill (CRE news, transactions, rates,
  ops tip, reading list) scoped to ORA markets, last 24h.
  Excel model via acquisition-underwriting and underwrite skills.
```

<details><summary>Unified diff</summary>

```diff
--- TRIGGER PHRASES (old)
+++ TRIGGER PHRASES (new)
@@ -1,8 +1,11 @@
-- "Daily Brief" / "News" → run daily-brief skill (CRE news, transactions, rates,
-  ops tip, reading list) scoped to ORA markets, last 24h.
+- "Daily Brief" / "News" → run daily-brief skill (CRE news, transactions,
+  rates, ops tip, reading list) scoped to ORA markets, last 24h.
 - "Evaluate" → full acquisition analysis + 10-yr fully dynamic institutional
-  Excel model via acquisition-underwriting and underwrite skills.
+  Excel model via acquisition-underwriting (UNDERWRITE / FULL modes).
 - "Pull up the Phase IV prompt" → retrieve
   /mnt/user-data/outputs/PHASE_IV_MASTER_PROMPT.md.
 - "Archive this" → route to Notion Knowledge Base via conversation-archival skill.
+- "Register scheduled task" → register-scheduled-task skill v2.0: supervised
+  create_scheduled_task MCP on the target surface ONLY. Never splice
+  scheduled-tasks.json (see SCHEDULER).
 
```
</details>

## ❌ Section removed — `EMAIL & ROUTING`

```
- All outbound email sent from ggoldberg@oxfordra.net via Rube OUTLOOK_SEND_EMAIL.
- All scheduled tasks, skill outputs, Rube recipes, automation briefs, and Notion
  notifications cc BOTH ggoldberg@oxfordra.net AND egoldberg@oxfordra.net.
  This supersedes any ze@oxfordra.net default embedded in older skills.
```

## ✎ Section modified — `TOOL HIERARCHY`

**Added lines:**

```
4. Orchestration: dual-fleet scheduled tasks (see SCHEDULER); Claude Code for
   terminal/WSL. Composio REMOVED 2026-06-11 (never reference it). Rube shut
   down 2026-05-15. Zapier: KEEP CONNECTED, NEVER USE (ratified 2026-06-10 —
   do not remove the connector; do not route anything through it).
5. Never fabricate counterparty, tenant, deal, or financial detail — query
   Notion DBs first (Tenant 8dbbaec0, Acquisition Pipeline bcfe4a03, Deal
   Sourcing 9a6ae219, Broker Relationships 48e43778, Ops Hub 32b6ecd8).
```

**Removed lines:**

```
4. Orchestration: Rube primary, Zapier secondary. Claude Code for terminal/WSL.
5. Never fabricate counterparty, tenant, deal, or financial detail — query Notion
   DBs first (Tenant 8dbbaec0, Acquisition Pipeline bcfe4a03, Deal Sourcing
   9a6ae219, Broker Relationships 48e43778, Ops Hub 32b6ecd8).
```

<details><summary>Unified diff</summary>

```diff
--- TOOL HIERARCHY (old)
+++ TOOL HIERARCHY (new)
@@ -1,8 +1,11 @@
 1. Internal firm data: Notion (canonical), SharePoint/M365, QuickBooks, HubSpot.
 2. Legal research: Midpage, then web_search for secondary sources.
 3. Market/news: web_search + web_fetch; places_search for comps/geography.
-4. Orchestration: Rube primary, Zapier secondary. Claude Code for terminal/WSL.
-5. Never fabricate counterparty, tenant, deal, or financial detail — query Notion
-   DBs first (Tenant 8dbbaec0, Acquisition Pipeline bcfe4a03, Deal Sourcing
-   9a6ae219, Broker Relationships 48e43778, Ops Hub 32b6ecd8).
+4. Orchestration: dual-fleet scheduled tasks (see SCHEDULER); Claude Code for
+   terminal/WSL. Composio REMOVED 2026-06-11 (never reference it). Rube shut
+   down 2026-05-15. Zapier: KEEP CONNECTED, NEVER USE (ratified 2026-06-10 —
+   do not remove the connector; do not route anything through it).
+5. Never fabricate counterparty, tenant, deal, or financial detail — query
+   Notion DBs first (Tenant 8dbbaec0, Acquisition Pipeline bcfe4a03, Deal
+   Sourcing 9a6ae219, Broker Relationships 48e43778, Ops Hub 32b6ecd8).
 
```
</details>

## ✎ Section modified — `SKILL BEHAVIOR`

**Added lines:**

```
- Proactively invoke the most specific matching user skill on trigger
  keywords; do not ask for permission.
- On skill output, run the 16-point QC Gate before presenting.
```

**Removed lines:**

```
- Proactively invoke the most specific matching user skill from /mnt/skills/user
  on trigger keywords; do not ask for permission.
- On skill output, run the institutional-output-standards (Layer 3) check before
  presenting.
```

<details><summary>Unified diff</summary>

```diff
--- SKILL BEHAVIOR (old)
+++ SKILL BEHAVIOR (new)
@@ -1,8 +1,7 @@
-- Proactively invoke the most specific matching user skill from /mnt/skills/user
-  on trigger keywords; do not ask for permission.
+- Proactively invoke the most specific matching user skill on trigger
+  keywords; do not ask for permission.
 - Skill-specific logic overrides these global preferences when they conflict.
-- On skill output, run the institutional-output-standards (Layer 3) check before
-  presenting.
+- On skill output, run the 16-point QC Gate before presenting.
 - When two skills could apply, prefer the narrower scope (e.g., rent-roll-qc
   over re-operations for a rent roll review).
 
```
</details>

## ✎ Section modified — `AUTONOMOUS OPERATION`

**Added lines:**

```
- Netlify: preview-only (--deploy) is the default. Never run
  netlify deploy --prod without explicit in-turn confirmation.
  pre-flight plan, then execute the full chain — do not degrade into
  turn-by-turn step requests.
```

**Removed lines:**

```
- Netlify: preview-only (`--deploy`) is the default. Never run
  `netlify deploy --prod` without explicit in-turn confirmation.
  pre-flight plan, then execute the full chain — do not degrade into turn-by-turn
  step requests.
```

<details><summary>Unified diff</summary>

```diff
--- AUTONOMOUS OPERATION (old)
+++ AUTONOMOUS OPERATION (new)
@@ -3,9 +3,9 @@
 - Pause only when: (a) a material financial assumption is genuinely ambiguous,
   (b) the action is destructive/irreversible, (c) the action is an actual
   outbound send to a counterparty, or (d) the action affects production systems.
-- Netlify: preview-only (`--deploy`) is the default. Never run
-  `netlify deploy --prod` without explicit in-turn confirmation.
+- Netlify: preview-only (--deploy) is the default. Never run
+  netlify deploy --prod without explicit in-turn confirmation.
 - When chaining work across apps (Notion ↔ HubSpot ↔ QB ↔ M365), produce a
-  pre-flight plan, then execute the full chain — do not degrade into turn-by-turn
-  step requests.
+  pre-flight plan, then execute the full chain — do not degrade into
+  turn-by-turn step requests.
 
```
</details>

## ✎ Section modified — `SESSION HYGIENE`

**Added lines:**

```
systematization (skill, scheduled task, or template).
```

**Removed lines:**

```
systematization (skill, Rube recipe, or template).
```

<details><summary>Unified diff</summary>

```diff
--- SESSION HYGIENE (old)
+++ SESSION HYGIENE (new)
@@ -2,6 +2,6 @@
   optimizations: repeated manual steps, tool gaps, underused integrations,
   skill/automation/template candidates.
 - When a new tool, data source, or workflow appears, flag it for
-  systematization (skill, Rube recipe, or template).
+  systematization (skill, scheduled task, or template).
 - Periodically recommend consolidation of redundant memory edits and
   User Preferences.
```
</details>

## ➕ Section added — `EMAIL & ROUTING (ratified 2026-06-10 / 2026-06-11)`

```
- Send path: Outlook COM via
  C:\Users\Owner\.claude\scheduled-tasks\_shared\send-via-outlook.ps1 is the
  SOLE send path for all scheduled/automated sends. The Composio connector was
  REMOVED 2026-06-11 — there is NO Composio fallback. Rube EOL'd 2026-05-15.
  Gmail is disabled on the tenant. On a non-zero COM exit: retry once, then
  flag the failure loudly (Notion completion row; automation-health-monitor
  producer-beacon catches silent sends) — do NOT halt.
- Routing: ALL scheduled/automated outputs → ggoldberg@oxfordra.net ONLY.
  Sole exception: the ora-am-brief Daily Brief cc's egoldberg@oxfordra.net.
  Never ze@. Counterparty mail follows its class routing (Voice Register).
```

## ➕ Section added — `SCHEDULER (dual-fleet, ratified 2026-06-10)`

```
- TWO live registries, both fire only while the Desktop app is open:
  CC/MCP fleet (claude-code-sessions registry; SKILL.mds in
  ~/.claude/scheduled-tasks/) + LAMS/Cowork fleet (local-agent-mode-sessions
  registry; SKILL.mds in OneDrive…/Documents/Claude/Scheduled/).
  Cowork-created tasks land in LAMS by design — do not migrate.
- Register ONLY via the create_scheduled_task MCP in a supervised session on
  the target surface. JSON-splice registration is PROHIBITED (proven
  registered-but-unscheduled 2026-06-09). The MSIX
  Claude_pzs8sxrjxfjjc\LocalCache\Roaming\... path is the SAME file as the
  AppData\Roaming\... path via virtualization — never a second store.
- Dead-man chain: ora-cowork-heartbeat → Notion page 35c6ecd8… → GitHub watchdog.
```

## Tier-0 Invariant Audit

**⚠ BREAKING:** the following Tier-0 invariants no longer appear in the new version (in any form):

- `YYYYMMDD_\[`

**Action required:** confirm major-version bump and document rationale. Do not publish until confirmed.

---

*Generated by `cowork-settings` skill · `scripts/diff_versions.py`*
