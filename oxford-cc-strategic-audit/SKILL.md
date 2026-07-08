---
name: oxford-cc-strategic-audit
description: >
  Comprehensive strategic audit of the Oxford Realty Advisors Command Center.
  Evaluates whether the platform helps ownership make better decisions, compound
  NOI, and scale with minimal overhead — across 12 business goal dimensions.
  Produces a full executive report: graded goals, ranked failure list, top-10 ROI
  improvements, kill list, future-state design, and the "If I Were COO" action plan.
  Use when ownership wants a business-effectiveness review, not a code-quality review.
  Trigger phrases: strategic audit, business audit, is the command center working,
  what should we build next, platform effectiveness, what's the ROI of the command center.
  Complementary to cc-audit-army (which reviews code correctness, not business value).
  v1.1 — 2026-07-08 (Skill Text Audit remediation: dispatch step surface note added —
  Code uses subagent-driven-development, Cowork uses the Agent tool directly; the six
  `~/.claude/scheduled-tasks/` CC-fleet references flagged UNVERIFIED — not reachable
  from this Cowork session, needs Code-surface confirmation; stale LAMS/Cowork fleet
  count corrected from "5" to a live-pull instruction)
---

# Oxford Command Center — Strategic Business Audit

## Your Role

You are simultaneously the CTO, COO, Principal Asset Manager, and Board Advisor of Oxford
Realty Advisors. You have been retained to answer one question:

> **Is the Command Center helping Oxford ownership make better investment decisions,
> compound NOI faster, and scale the portfolio with minimal additional overhead?
> And if not — what specifically should be done about it?**

This is NOT a code-quality review. Do not grade code style, test coverage, or architecture
patterns for their own sake. Grade them ONLY where they impair a business decision.

Challenge every assumption. Do not protect existing work. Be objective and evidence-based.
Every claim must cite a specific file, module, or data source.

---

## Business Context

Oxford Realty Advisors: family-office industrial RE investment company.
~600K SF · ~140 tenants · ~27 properties · OH/MD/IN/WI/MO/KS/TN · ~$60M AUM.
Buy-box: sub-$10M, sub-50K SF, Class B/C shallow-bay industrial/flex.
Governors: DSCR ≥ 1.25x, LTV ≤ 40% (invariants — never modify).
Long-term goal: $700–800M AUM over 30–40 years.
Ownership team: Gabriel Goldberg (VP Acquisitions) + Eric Goldberg (Founder).
Small team seeking maximum operational leverage.

The Command Center exists for ONE purpose: to help this two-person ownership team
make better capital-allocation decisions and scale the portfolio without proportionate
hiring.

---

## Phase 1 — Reconnaissance (read these files before evaluating anything)

Read the following files in this order. Each one informs the evaluation.

### Architecture foundations

```
C:\Users\Owner\oxford-command-center\architecture\system-overview.md
C:\Users\Owner\oxford-command-center\architecture\database-schema.md
C:\Users\Owner\oxford-command-center\architecture\agent-assignments.md
C:\Users\Owner\oxford-command-center\CLAUDE.md
```

### Existing audit artifacts (do NOT duplicate — extend and contradict where warranted)

```
C:\Users\Owner\oxford-command-center\docs\superpowers\specs\2026-06-13-cc-audit-report.md
C:\Users\Owner\oxford-command-center\docs\superpowers\specs\2026-06-13-cc-evaluation-scorecard.md
C:\Users\Owner\oxford-command-center\docs\superpowers\specs\2026-06-13-ora-intelligence-platform-master-plan.md
```

### All feature specs (read all — they reveal planned vs. built)

```
Glob: C:\Users\Owner\oxford-command-center\docs\superpowers\specs\*.md
Read each one. Note: "spec" = designed but not necessarily built.
```

### Module map (what's actually in the UI)

```
Glob: C:\Users\Owner\oxford-command-center\src\modules\**\*.tsx
  Focus on the top-level file per module to understand what it renders.
  The 20 modules are: overview, principal, pipeline (acquisitions), tasks, alerts,
  calendar, renewals, portfolio, intel, calibration, leases, tenants, debt, cash,
  close, insurance, market, relationships, documents, health.
```

### Analytics and scoring engines

```
C:\Users\Owner\oxford-command-center\src\analytics\engine.ts
C:\Users\Owner\oxford-command-center\server\warehouse\scores.ts
C:\Users\Owner\oxford-command-center\server\warehouse\metrics.ts
C:\Users\Owner\oxford-command-center\server\warehouse\growth.ts
C:\Users\Owner\oxford-command-center\server\warehouse\drivers.ts
C:\Users\Owner\oxford-command-center\server\warehouse\benchmarks.ts
C:\Users\Owner\oxford-command-center\server\warehouse\anomalies.ts
C:\Users\Owner\oxford-command-center\server\ai\agent.ts   (or index.ts — find the Claude agent)
C:\Users\Owner\oxford-command-center\server\alerts\conditions.ts
```

### Scheduled automation fleet

From the session context, the live CC/MCP fleet has 17 scheduled tasks. The
LAMS/Cowork fleet count of "5" below is STALE — `list_scheduled_tasks` on
2026-07-08 returned 21 live LAMS/Cowork tasks; re-pull live before citing a count.
Read the SKILL.md for the most business-critical ones:
```
C:\Users\Owner\.claude\scheduled-tasks\ora-am-brief\SKILL.md
C:\Users\Owner\.claude\scheduled-tasks\ora-financial-code-integrity-sweep\SKILL.md
C:\Users\Owner\.claude\scheduled-tasks\ora-master-workbook-ingest\SKILL.md
C:\Users\Owner\.claude\scheduled-tasks\ora-open-sessions-board\SKILL.md
C:\Users\Owner\.claude\scheduled-tasks\ora-pm-ledger\SKILL.md
C:\Users\Owner\.claude\scheduled-tasks\ora-dashboard-refresh\SKILL.md
```
> UNVERIFIED (Skill Text Audit finding 9, 2026-07-08): the six `~/.claude/scheduled-tasks/`
> CC/MCP-fleet paths cited above and at lines ~356-358, ~272 (ora-financial-code-integrity-sweep,
> ora-master-workbook-ingest, ora-open-sessions-board, ora-pm-ledger, ora-week-ahead-briefing,
> ora-deal-sourcing-scan) could NOT be confirmed from this Cowork remediation session — the
> `~/.claude/scheduled-tasks/` path is host-protected and not mountable from Cowork, and
> `list_scheduled_tasks` only enumerates the LAMS/Cowork fleet (21 tasks, none of these six).
> Note also `ora-am-brief` and `ora-dashboard-refresh` are cited here as CC-fleet but appear in
> the live LAMS/Cowork registry instead — possible fleet-assignment drift, not confirmed either
> way. Verify these seven task references from a Claude Code session with `~/.claude/` access
> before relying on this section; do not treat it as current until re-verified.

### Acquisitions pipeline

```
C:\Users\Owner\oxford-command-center\src\modules\acquisitions\  (find main component)
C:\Users\Owner\oxford-command-center\server\warehouse\acquisition.ts  (scorecard engine)
C:\Users\Owner\oxford-command-center\src\contracts\acquisition.ts     (if it exists)
```

---

## Phase 2 — Invoke Parallel Subagents for Goal Evaluations

**Code surface:** dispatch parallel subagents per the Engineering OS dispatch canon
(`subagent-driven-development` mode — appropriate here since this is >~4 independent,
high-precision evaluation tasks). **Cowork surface (no CC dispatch canon here):** use the
Agent tool directly — send one Agent tool call per goal (Goals 1–12) in a single message so
they execute concurrently; do not attempt to invoke a `dispatching-parallel-agents` skill, it
does not exist as an installed skill on either surface. Each subagent/agent call
gets one goal and the recon data. Brief each agent:

> "You are reviewing the Oxford Command Center — a local-first investment intelligence
> platform for a 600K SF industrial real estate firm (2-person ownership team, $60M AUM,
> 27 properties, 140 tenants). You have access to the full codebase at
> C:\Users\Owner\oxford-command-center\. Read the relevant files listed below, then
> grade this goal A–F with evidence. Cite specific files, line ranges, and module names.
> Do NOT grade code quality — only business decision value."

### Goal 1 — Ownership Attention Engine

*Does the system immediately tell ownership which property, tenant, PM, or acquisition
needs attention TODAY?*

Files to read:
- `src/modules/principal/` — Principal Home module (main attention surface)
- `src/modules/overview/` — Overview module
- `src/modules/alerts/` — Alerts module
- `server/alerts/conditions.ts` — What conditions fire alerts
- `server/warehouse/scores.ts` — Health/attention/capital scores
- Session context fleet: ora-am-brief, ora-open-sessions-board

Grade A–F. Answer:
1. What is the attention-routing mechanism? Does it proactively surface the right thing?
2. What would prevent ownership from knowing what to focus on today?
3. What attention signals are completely absent (PM performance, acquisition deadlines,
   lease expiration urgency tiers, delinquency aging)?
4. Capabilities Missing Entirely.

### Goal 2 — NOI Growth Engine

*Does the system help identify rent growth opportunities, expense reduction, vendor
inefficiencies, vacancy risks, collections issues, and tenant retention opportunities?*

Files to read:
- `server/warehouse/drivers.ts` — ΔNOI decomposition
- `server/warehouse/growth.ts` — NOI trend / CAGR
- `server/warehouse/anomalies.ts` — Anomaly detection
- `src/modules/intel/` — Intelligence UI (the main NOI surface)
- `src/modules/renewals/` — Lease renewal module
- `src/modules/close/` — Monthly close module
- `server/warehouse/scores.ts` — NOI-related scoring
- Session context: ora-pm-ledger

Grade A–F. Answer:
1. Can ownership identify the top 5 properties by NOI upside opportunity right now?
2. What NOI opportunities are currently invisible to the system?
3. Is expense anomaly detection real-time or reactive?
4. Capabilities Missing Entirely.

### Goal 3 — Scale Without Hiring

*Does the system allow more properties, tenants, markets, and acquisitions without
proportionate staffing increases?*

Files to read:
- ALL scheduled task SKILL.md files at `~/.claude/scheduled-tasks/`
- `server/warehouse/ingest.ts` — Automation of P&L ingestion
- `src/modules/close/` — Monthly close workflow
- `src/modules/leases/` — Lease management automation
- Specs: all `2026-06-04-*.md` (expansion design)
- `docs/superpowers/specs/2026-06-14-eric-live-command-center-access-design.md`

Grade A–F. Identify:
1. Which workflows are still manual that should be automated?
2. What is the bottleneck that breaks first when the portfolio doubles to 54 properties?
3. What human-in-the-loop steps add the most friction per new property added?
4. Scaling bottlenecks ranked by severity.

### Goal 4 — Single Source of Truth

*Can ownership get a definitive answer to any portfolio question from one place?*

Files to read:
- `architecture/system-overview.md` §2 (Two-Spine Architecture + the Critical Defect)
- `server/workbook/parse.ts` — Spine A source
- `server/warehouse/` — Spine B source
- `server/warehouse/reconcile-noi.ts` — The A↔B reconciliation attempt
- `src/modules/health/` — System Health module

Grade A–F. List:
1. Every major information silo (what lives where, what conflicts).
2. The two-NOI-representation problem: how bad is it in practice?
3. Data fragmentation: what questions require visiting 2+ systems to answer?
4. Missing integrations that would create the most value.

### Goal 5 — Early Problem Detection

*Does the system detect expense spikes, delinquencies, vacancy issues, insurance
lapses, tax reassessments, PM failures, and maintenance issues before they become
expensive?*

Files to read:
- `server/alerts/conditions.ts` — Alert conditions
- `src/modules/alerts/` — Alert UI
- `server/warehouse/anomalies.ts` — Statistical anomaly detection
- `src/modules/insurance/` — Insurance module
- `src/modules/tenants/` — Tenant module

Grade A–F. Answer:
1. What problems could exist today without ownership knowing?
2. What is the detection latency for each major risk category?
3. What alert conditions are completely absent?
4. Does the system detect PM performance failure?

### Goal 6 — Property Quality Ranking

*Can ownership identify best assets, worst assets, improving assets, and
deteriorating assets — objectively and on demand?*

Files to read:
- `server/warehouse/scores.ts` — Health/attention/capital scores (0–100)
- `server/warehouse/benchmarks.ts` — Cross-property percentile ranking
- `server/warehouse/growth.ts` — Trend / CAGR
- `src/modules/intel/` — Intelligence UI verdict surfaces
- `docs/superpowers/specs/2026-06-13-cc-evaluation-scorecard.md` §learn-from-data score

Grade A–F. Answer:
1. What is the scoring methodology? Is it calibrated or estimated?
2. Can ownership rank all 27 properties by quality score right now?
3. Are the scores trustworthy or are the weights uncalibrated?
4. What is missing from the scoring model (building characteristics, functional
   obsolescence, location quality, PM effectiveness)?

### Goal 7 — Acquisition Intelligence

*Does the Command Center help evaluate new acquisitions, enforce buy-box compliance,
and assess portfolio fit?*

Files to read:
- `server/warehouse/acquisition.ts` — Acquisition scorecard engine
- `src/modules/acquisitions/` — Acquisitions module (kanban)
- `src/contracts/acquisition.ts` — Acquisition data contract
- `docs/superpowers/specs/2026-06-13-acquisition-scorecard-contract.md`
- `docs/superpowers/specs/2026-06-13-acquisition-scorecard-answers-and-build-plan.md`
- `docs/superpowers/specs/2026-06-14-om-upload-field-extraction-design.md`
- Session context: ora-deal-sourcing-scan (CC fleet)

Grade A–F. Answer:
1. Can ownership run a buy-box screen on a new deal in the Command Center today?
2. What acquisition decisions are currently being made without sufficient data?
3. What is the gap between the acquisition intelligence built and what's needed
   to evaluate a deal from OM to IC Memo without leaving the platform?
4. Capabilities Missing Entirely.

### Goal 8 — Capital Allocation Intelligence

*Can ownership answer: "If I have $100K to invest today, where should it go?"*

Files to read:
- `server/warehouse/scores.ts` — `capitalScore` / `CapitalAction` verdict
- `server/warehouse/intel-config.ts` — Score weights and configuration
- `src/modules/intel/` — How capital verdicts are surfaced
- `src/analytics/engine.ts` — Scenario engine (what-if)
- `docs/superpowers/specs/2026-06-13-cc-evaluation-scorecard.md` §learn-from-data
- `docs/superpowers/specs/2026-06-14-intel-config-health-weight-calibration.md`

Grade A–F. Answer:
1. What is the current capital allocation recommendation engine? Is it trustworthy?
2. Does the system account for CAPEX ROI, improvement NPV, or refinancing options?
3. How capital allocation decisions are currently impaired.
4. What would a real capital allocation engine look like?

### Goal 9 — Property Manager Accountability

*Can ownership objectively compare PM performance across NOI growth, expense growth,
collections, tenant retention, work orders, and operating efficiency?*

Files to read:
- `server/warehouse/benchmarks.ts` — PM benchmarking (check if it exists)
- `src/modules/intel/` — PM scorecard surface (check if it exists)
- Session context: ora-pm-ledger
- `src/modules/relationships/` — Relationships module

Grade A–F. Answer:
1. Is there a PM performance scorecard in the system today?
2. Can ownership compare PM A vs PM B on any objective metric right now?
3. What PM accountability mechanisms are completely absent?
4. What data would be needed to build a real PM accountability engine?

### Goal 10 — Market Intelligence

*Does the system provide visibility into market rents, occupancy, trends, and
competitive properties?*

Files to read:
- `src/modules/market/` — Market module
- `server/macro/getMacro.ts` — FRED macro data
- `docs/superpowers/specs/2026-06-13-ora-intelligence-platform-master-plan.md`
  §market-intelligence section

Grade A–F. Answer:
1. What market data is in the system today (FRED rates, cap rate spreads)?
2. What submarket data (vacancy rates, absorption, competitive rents) is absent?
3. Can the system tell ownership whether a market is worth entering or exiting?

### Goal 11 — Portfolio Risk Management

*Does the system surface lease rollover risk, tenant concentration, geographic
concentration, industry concentration, and CAPEX exposure?*

Files to read:
- `src/modules/renewals/` — Lease rollover
- `src/modules/leases/` — Lease data
- `src/modules/portfolio/` — Portfolio-level view
- `src/modules/debt/` — Debt maturity
- `src/analytics/engine.ts` — `buildAnalytics()` risk outputs

Grade A–F. Answer:
1. Can ownership see the lease expiration curve for the full portfolio in one view?
2. What concentration risks are visible vs. invisible?
3. What is the biggest unmonitored risk in the portfolio right now?

### Goal 12 — Executive AI Briefings

*Can ownership receive a daily, weekly, monthly, and quarterly briefing without
searching for information?*

Files to read:
- `~/.claude/scheduled-tasks/ora-am-brief/SKILL.md`
- `~/.claude/scheduled-tasks/ora-dashboard-refresh/SKILL.md`
- `~/.claude/scheduled-tasks/ora-week-ahead-briefing/SKILL.md`
- `~/.claude/scheduled-tasks/ora-financial-code-integrity-sweep/SKILL.md`
- `server/ai/` — AI agent

Grade A–F. Answer:
1. What does the daily brief actually contain? Is it deterministic or AI-narrated?
2. What information would ownership wish was in the daily brief that isn't?
3. Is the AI agent proactive (surfacing insights) or reactive (answering questions)?
4. What briefing cadences are absent (weekly, monthly, quarterly)?

---

## Phase 3 — Synthesis (single agent, after parallel goals complete)

After the 12 goal evaluations return, synthesize into the full report below.
Read the master plan's existing gap analysis first to avoid duplication — then
identify what it missed or underweighted from the business perspective.

---

## Phase 4 — Report Assembly

Produce the final deliverable in this exact structure:

---

# OXFORD COMMAND CENTER — STRATEGIC AUDIT REPORT

**Date:** [today]
**Prepared by:** [AI strategic audit]
**Scope:** Oxford Realty Advisors Command Center — business effectiveness review

---

## 1. EXECUTIVE SUMMARY (400 words)

One-page summary answering: Is this platform working? What are the 3 most important
things to fix? What is the single most important thing to build next?

Write for a board meeting, not a developer retrospective.

---

## 2. COMMAND CENTER EFFECTIVENESS SCORE

Score 0–100. Subscores for:
- Ownership attention / daily decision support (0–10)
- NOI growth identification engine (0–10)
- Scale without hiring / automation (0–10)
- Single source of truth / data quality (0–10)
- Early problem detection (0–10)
- Property quality ranking (0–10)
- Acquisition intelligence (0–10)
- Capital allocation intelligence (0–10)
- PM accountability (0–10)
- Market intelligence (0–10)

Explain the composite methodology. Compare to where the score SHOULD be to
support a $700M portfolio.

---

## 3. GOAL-BY-GOAL GRADES

| Goal | Grade | One-Line Verdict |
|------|-------|-----------------|
| 1. Ownership Attention Engine | A–F | |
| 2. NOI Growth Engine | A–F | |
| 3. Scale Without Hiring | A–F | |
| 4. Single Source of Truth | A–F | |
| 5. Early Problem Detection | A–F | |
| 6. Property Quality Ranking | A–F | |
| 7. Acquisition Intelligence | A–F | |
| 8. Capital Allocation Intelligence | A–F | |
| 9. PM Accountability | A–F | |
| 10. Market Intelligence | A–F | |
| 11. Portfolio Risk Management | A–F | |
| 12. Executive AI Briefings | A–F | |

For each goal, provide:
- **Strengths** (what works, with file citations)
- **Weaknesses** (what's broken or partial, with file citations)
- **Capabilities Missing Entirely** (absent from the codebase)
- **Key Question Answered by Subagent** (the goal-specific required section)

---

## 4. FEATURE INVENTORY

Complete inventory of every feature. Classify each:
- **Value:** High / Medium / Low / None
- **Disposition:** Keep / Improve / Consolidate / Remove

Format as a table:

| Feature | Module/Location | Value | Disposition | Reasoning |
|---------|----------------|-------|-------------|-----------|

Cover: all 20 UI modules, all analytics engines (growth/drivers/anomalies/benchmarks/scores),
all 22 scheduled tasks (CC + LAMS fleet), the AI agent, alerts system, document RAG,
FRED macro integration, acquisition scorecard engine, calibration system,
overlay write surface, Cloudflare mirror.

---

## 5. SCHEDULED TASK AUDIT

For each of the 22 live scheduled tasks (17 CC + 5 LAMS), evaluate:
- **What it does** (one sentence)
- **Business value** (High/Medium/Low/None)
- **Failure risk** (what breaks if it stops firing)
- **Verdict:** Keep / Modify / Replace / Remove

Identify:
- Tasks that produce no actionable output
- Tasks that should exist but don't
- Redundant tasks

---

## 6. OWNER EXPERIENCE AUDIT

Simulate ownership's actual experience in four scenarios:

**8:00 AM — 5-minute morning check**
Walk through exactly what ownership sees, in what order, with what friction.
What critical information is missing from the first 5 minutes?

**Morning deep-dive — 30-minute review**
What does ownership do when they have 30 minutes to understand the portfolio?
Where do they hit dead ends?

**Monthly close review**
Walk through the close workflow. What's manual? What's error-prone? What's automated?

**New acquisition evaluation**
From "broker sends OM" to "IC memo complete" — walk through the Command Center's
role at each step. Where does ownership leave the platform and why?

---

## 7. TIME LEVERAGE ANALYSIS

Estimate current ownership time allocation per week:
- Acquisitions: X hours
- Leasing/renewals: X hours
- PM oversight: X hours
- Accounting/financial review: X hours
- Asset management: X hours
- Vendor management: X hours
- Administration: X hours

Estimate hours saved per week by the Command Center TODAY.
Estimate hours that COULD be saved after the top-10 improvements.
Identify the highest-leverage time-saving opportunity not yet built.

---

## 8. TOP 25 FAILURES

Title the section: **TOP 25 FAILURES PREVENTING OXFORD FROM ACHIEVING ITS GOALS**

Do NOT duplicate the existing cc-audit-report HIGH/MEDIUM findings which are
code-correctness failures. These should be BUSINESS failures — missing capabilities,
wrong priorities, workflow gaps, decision-support blind spots.

For each:
| # | Failure | Root Cause | Business Impact | Fix | Value Creation |
|---|---------|-----------|----------------|-----|---------------|

Rank by business impact, not technical severity.

---

## 9. VALUE CREATION ANALYSIS

For each of the Top 10 improvements, estimate:
- **Low case impact**
- **Expected impact**
- **High case impact**

Where possible quantify:
- NOI impact ($/year)
- Time savings (hours/week)
- Acquisition improvement (deals evaluated, speed)
- Risk reduction

Do not provide recommendations without estimating impact.

---

## 10. TOP 10 HIGHEST ROI IMPROVEMENTS

Rank 1–10. Evaluation criteria:
1. Business value (NOI impact, decision quality, time savings)
2. Strategic importance (does it unblock other improvements?)
3. Ease of implementation (days to ship vs. months)

For each:
- **Why it matters** (one paragraph)
- **Expected business impact**
- **Implementation effort** (days estimate)
- **Dependencies**
- **Estimated value creation**

---

## 11. KILL LIST

Title: **FEATURES THAT SHOULD BE REMOVED OR ARCHIVED**

For each:
- Why it adds more complexity than value
- Estimated maintenance cost it's consuming
- What to do instead (consolidate into another feature / remove entirely)

Estimate total maintenance overhead the kill list would eliminate.

---

## 12. FUTURE OXFORD STRESS TEST

Assume Oxford grows to: 2M SF · 500 tenants · 10 markets · 10 PMs · 10 acquisitions/year.

Answer:
1. What breaks first in the current architecture?
2. What becomes too slow to be useful?
3. What data quality problems become catastrophic at scale?
4. What is the single biggest architectural decision to make NOW to avoid a painful
   rebuild at 2M SF?

---

## 13. FUTURE STATE DESIGN

Design the ideal Command Center for a 2-person ownership team running a $200M portfolio.

Describe (not implement):
- The 5 core dashboards ownership opens every day
- The 3 most important automations running in the background
- The AI agent's role (Q&A substrate vs. proactive insight engine)
- The acquisition intelligence workflow (OM receipt → IC memo)
- The NOI early-warning system
- The capital allocation engine
- Weekly and monthly ownership workflow

Keep it grounded in what's achievable in 12 months, not science fiction.

---

## 14. IF I WERE COO/CTO OF OXFORD TOMORROW

You have one year. Limited budget. Existing team (2 people + Claude).
You may only commit to 10 improvements.

For each of your 10:
| # | Improvement | Why it matters | Business impact | Effort | Dependencies | Risks |
|---|-------------|---------------|----------------|--------|-------------|-------|

End with: **The single most important thing to do in the next 30 days.**

---

## Formatting Standards

- Write for ownership (Gabriel + Eric), not for developers.
- Evidence every claim: `cite file:line or module name`.
- Never repeat findings from cc-audit-report without adding business context.
- Use tables for inventories and comparisons.
- Grades are A/B/C/D/F — no pluses. A = "this capability is real and earning its place."
  F = "this is absent or actively misleading."
- Flag speculative estimates with [ESTIMATE].
- Flag items the master plan already acknowledges with [KNOWN GAP].
- New findings not in the master plan should be marked [NEW FINDING].

---

## Constraints

- Do NOT modify any files. This is read-only analysis.
- Do NOT run `npm run gate` or start any servers.
- Do NOT commit, push, or deploy anything.
- The report itself should be saved to:
  `C:\Users\Owner\oxford-command-center\docs\superpowers\specs\[YYYY-MM-DD]-cc-strategic-audit.md`
  using the Write tool after it is complete.

---

## Completion Signal

When the report is written, output:

```
STRATEGIC AUDIT COMPLETE
Effectiveness Score: [X]/100
Top finding: [one sentence]
Top recommendation: [one sentence]
Report saved to: [path]
```
