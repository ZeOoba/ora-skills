# ORA Cowork Global Settings — Changelog

**From:** `old.md`
**To:** `20261017_ORA_CoworkGlobalSettings_v3_0.md`
**Generated:** 2026-10-17
**Scope:** Section-level diff with Tier-0 invariant audit.

---

## ✎ Section modified — `DELIVERABLE STANDARDS`

**Added lines:**

```
[DocType]_[Property]_[MMDDYYYY] · models
```

**Removed lines:**

```
[DocType]_[Property]_[MMDDYYYY] (adopted 2026-07-09) · models
```

<details><summary>Unified diff</summary>

```diff
--- DELIVERABLE STANDARDS (old)
+++ DELIVERABLE STANDARDS (new)
@@ -2,7 +2,7 @@
   Style Guide v1.0+ (Oxford Navy #1B2A4A, Gold #C9A96E, Parchment #F5F3EF;
   EB Garamond / DM Sans / IBM Plex Mono).
 - File naming — three separate schemas, do NOT unify: deal files
-  [DocType]_[Property]_[MMDDYYYY] (adopted 2026-07-09) · models
+  [DocType]_[Property]_[MMDDYYYY] · models
   ORA_[DocType]_[Property]_v[X.Y].xlsx · session outputs
   YYYY-MM-DD_[Topic]_[DocType]_v##.ext in an /outputs/ subfolder. Never delete —
   move to /archive/.
```
</details>

## ✎ Section modified — `EMAIL & ROUTING`

**Added lines:**

```
- Send path: Outlook COM via
  C:\Users\Owner\.claude\scheduled-tasks\_shared\send-via-outlook.ps1 is the
  SOLE automated send path. No fallback connector exists; Gmail is disabled on the tenant.
  On a non-zero COM exit:
```

**Removed lines:**

```
- Send path: Outlook COM via send-via-outlook.ps1 is the SOLE automated send
  path. Composio was REMOVED 2026-06-11 — no fallback connector exists. Rube
  EOL'd 2026-05-15. Gmail is disabled on the tenant. On a non-zero COM exit:
```

<details><summary>Unified diff</summary>

```diff
--- EMAIL & ROUTING (old)
+++ EMAIL & ROUTING (new)
@@ -1,8 +1,9 @@
 - All scheduled/automated outputs route to ggoldberg@oxfordra.net ONLY. Sole
   exception: the Daily Brief (ora-am-brief) cc's egoldberg@oxfordra.net.
-- Send path: Outlook COM via send-via-outlook.ps1 is the SOLE automated send
-  path. Composio was REMOVED 2026-06-11 — no fallback connector exists. Rube
-  EOL'd 2026-05-15. Gmail is disabled on the tenant. On a non-zero COM exit:
+- Send path: Outlook COM via
+  C:\Users\Owner\.claude\scheduled-tasks\_shared\send-via-outlook.ps1 is the
+  SOLE automated send path. No fallback connector exists; Gmail is disabled on the tenant.
+  On a non-zero COM exit:
   retry once, then flag the failure loudly (Notion completion row;
   automation-health-monitor producer-beacon catches silent sends) — do NOT halt.
 - Never ze@oxfordra.net. Counterparty mail follows its class routing (Voice Register).
```
</details>

## ✎ Section modified — `SCHEDULER (dual-fleet)`

**Added lines:**

```
the target surface. JSON-splice registration is PROHIBITED
  (produces registered-but-unscheduled tasks). The MSIX
```

**Removed lines:**

```
the target surface. JSON-splice registration is PROHIBITED (proven
  registered-but-unscheduled 2026-06-09). The MSIX
```

<details><summary>Unified diff</summary>

```diff
--- SCHEDULER (dual-fleet) (old)
+++ SCHEDULER (dual-fleet) (new)
@@ -4,8 +4,8 @@
   registry; SKILL.mds in OneDrive…/Documents/Claude/Scheduled/).
   Cowork-created tasks land in LAMS by design — do not migrate.
 - Register ONLY via the create_scheduled_task MCP in a supervised session on
-  the target surface. JSON-splice registration is PROHIBITED (proven
-  registered-but-unscheduled 2026-06-09). The MSIX
+  the target surface. JSON-splice registration is PROHIBITED
+  (produces registered-but-unscheduled tasks). The MSIX
   Claude_pzs8sxrjxfjjc\LocalCache\Roaming\... path is the SAME file as the
   AppData\Roaming\... path via virtualization — never a second store.
 - Dead-man chain: ora-cowork-heartbeat → Notion page 35c6ecd8… → GitHub watchdog.
```
</details>

## ✎ Section modified — `TRIGGER PHRASES`

**Added lines:**

```
- "Pull up the Phase IV prompt" → retrieve the Knowledge Base page
  "Phase III / Phase IV AI Infrastructure Roadmaps (reconstructed)"
  (Notion 3956ecd8-9e59-8166-ad54-d5491b69251a). The original file is lost;
  say so when quoting it.
- "Archive this" → file to the Notion Knowledge Base (3386ecd8).
```

**Removed lines:**

```
- "Pull up the Phase IV prompt" → retrieve
  /mnt/user-data/outputs/PHASE_IV_MASTER_PROMPT.md.
- "Archive this" → route to Notion Knowledge Base via conversation-archival skill.
```

<details><summary>Unified diff</summary>

```diff
--- TRIGGER PHRASES (old)
+++ TRIGGER PHRASES (new)
@@ -6,9 +6,11 @@
   first-look only).
 - LOI → loi-generation is the SOLE path; never document-assembly's generic
   template (it skips the QC gate).
-- "Pull up the Phase IV prompt" → retrieve
-  /mnt/user-data/outputs/PHASE_IV_MASTER_PROMPT.md.
-- "Archive this" → route to Notion Knowledge Base via conversation-archival skill.
+- "Pull up the Phase IV prompt" → retrieve the Knowledge Base page
+  "Phase III / Phase IV AI Infrastructure Roadmaps (reconstructed)"
+  (Notion 3956ecd8-9e59-8166-ad54-d5491b69251a). The original file is lost;
+  say so when quoting it.
+- "Archive this" → file to the Notion Knowledge Base (3386ecd8).
 - "Register scheduled task" → register-scheduled-task skill: supervised
   create_scheduled_task MCP on the target surface ONLY. Never splice
   scheduled-tasks.json (see SCHEDULER).
```
</details>

## ✎ Section modified — `TOOL HIERARCHY`

**Added lines:**

```
QuickBooks is Desktop only (~20 LLC files): SharePoint export + parse. The
   QBO MCP is structurally incompatible — never suggest re-auth.
2. Legal research: legal-intelligence skill, then web_search for secondary
   sources.
   terminal/WSL. Zapier: RETIRED — never re-authenticate, reconnect, or
   route anything through it.
```

**Removed lines:**

```
2. Legal research: Midpage, then web_search for secondary sources.
   terminal/WSL. Composio REMOVED 2026-06-11 (never reference it). Rube shut
   down 2026-05-15. Zapier: KEEP CONNECTED, NEVER USE — do not remove the
   connector; do not route anything through it.
```

<details><summary>Unified diff</summary>

```diff
--- TOOL HIERARCHY (old)
+++ TOOL HIERARCHY (new)
@@ -1,10 +1,12 @@
 1. Internal firm data: Notion (canonical), SharePoint/M365, QuickBooks, HubSpot.
-2. Legal research: Midpage, then web_search for secondary sources.
+   QuickBooks is Desktop only (~20 LLC files): SharePoint export + parse. The
+   QBO MCP is structurally incompatible — never suggest re-auth.
+2. Legal research: legal-intelligence skill, then web_search for secondary
+   sources.
 3. Market/news: web_search + web_fetch; places_search for comps/geography.
 4. Orchestration: dual-fleet scheduled tasks (see SCHEDULER); Claude Code for
-   terminal/WSL. Composio REMOVED 2026-06-11 (never reference it). Rube shut
-   down 2026-05-15. Zapier: KEEP CONNECTED, NEVER USE — do not remove the
-   connector; do not route anything through it.
+   terminal/WSL. Zapier: RETIRED — never re-authenticate, reconnect, or
+   route anything through it.
 5. Never fabricate counterparty, tenant, deal, or financial detail — query
    Notion DBs first (Tenant 8dbbaec0, Acquisition Pipeline bcfe4a03, Deal
    Sourcing 9a6ae219, Broker Relationships 48e43778, Ops Hub 32b6ecd8,
```
</details>

## ✎ Section modified — `SKILL BEHAVIOR`

**Added lines:**

```
- When two skills could apply, prefer the narrower scope (e.g.,
  verified-deal-recon over acquisition-underwriting for a single-target
  pre-screen).
- If a referenced skill is absent on the current surface, say so — never
  improvise its procedure.
```

**Removed lines:**

```
- When two skills could apply, prefer the narrower scope (e.g., rent-roll-qc
  over re-operations for a rent roll review).
```

<details><summary>Unified diff</summary>

```diff
--- SKILL BEHAVIOR (old)
+++ SKILL BEHAVIOR (new)
@@ -2,6 +2,9 @@
   keywords; do not ask for permission.
 - Skill-specific logic overrides these global preferences when they conflict.
 - On skill output, run the 16-point QC Gate before presenting.
-- When two skills could apply, prefer the narrower scope (e.g., rent-roll-qc
-  over re-operations for a rent roll review).
+- When two skills could apply, prefer the narrower scope (e.g.,
+  verified-deal-recon over acquisition-underwriting for a single-target
+  pre-screen).
+- If a referenced skill is absent on the current surface, say so — never
+  improvise its procedure.
 
```
</details>

## Tier-0 Invariant Audit

✓ All Tier-0 invariants preserved in the new version.

### Reviewer annotation (2026-10-17)
- **Breaking change not covered by the Tier-0 audit.** Zapier reverses from *keep connected, never use* to *retired, never re-auth*. Any skill or health check that reads the connector's presence as a signal will now see its absence as expected.
- **Audit pattern fixed in this release.** Invariant 5 now checks for `do NOT unify`. The old pattern, `YYYYMMDD_\[`, had been stale since v2.0 and false-flagged both v2.1 and v3.0.
- **Amendment No. 1 closed as superseded by v2.0.** The only residue was the full send-script path, which is now carried in Email & Routing.
- [SPECULATIVE] Attention budget: the block is net about the same length. Six dated-history clauses and one dead connector are replaced by operative rules, so the signal-to-token ratio should improve modestly.

---

*Generated by `cowork-settings` skill · `scripts/diff_versions.py`*
