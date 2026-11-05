# Skill Improvement Plan — 2026-11-05

Scope: all 90 skills in `ora-skills` at `919e67df`. Lens: `superpowers:writing-skills` (SDO, token efficiency, test-first edits) plus the repo's own `CLAUDE.md` rules. Investigation only; nothing has been edited.

## Evidence base

| Check | Result |
|---|---|
| `skill_ci_gates.py frontmatter` | 90 skills, 0 errors |
| Routing baseline: 16 ambiguous prompts, 3 independent Sonnet routers, descriptions only | 15/16 unanimous and correct; Q5 "submarket analysis" split 2:1 market-monitor / submarket-spatial-analysis |
| Body size | 224K words total; 8 bodies over 5K words (acquisition-underwriting 14.6K) |
| Inline changelogs | 25K words (11% of corpus); 6 skills have 26–35% of their body in changelog |
| H1 `(vX.Y)` per CLAUDE.md | 21 skills missing |
| Description starts "Use when" | 7 do not (exhibit-package-builder, municipal-permit-portal-recon, lease-form-qc, lease-generation, estoppel-request-generation, listing-enrichment-gate, branch-catchup, artifact-to-docx-report) |
| Referenced scheduled tasks vs live CC fleet roster | 3 skills cite tasks not on the live fleet |

**Conclusion that bounds the plan:** routing works. The suspected collisions (tax-appeal / millage, legal-intelligence / lease-abstraction, document-assembly / tenant-email, acquisition-underwriting / deal-comparison) did not misroute in the baseline. Per the writing-skills rule ("if the control doesn't exhibit the failure, there is nothing to fix"), those descriptions are left alone. The work is staleness, conformance, and token cost.

## Phase 1 — Stale facts (correctness; low risk)

| Skill | Defect | Fix |
|---|---|---|
| cash-position-monitor | Description and body line 29 say it "powers ora-cash-position-snapshot" (Mon 6:30). That task is not on the live fleet; its work was folded into ora-am-brief. | Repoint to ora-am-brief, or retire the skill. This is open ask F7 from the 10-30 catalog review, so Gabriel decides. |
| ora-flood-zoning-dd | Cites "Buy Box v1.0" three times, including in the description. Doctrine is v1.1 plus Amendment H. | Remove the version from the description. Re-verify the T2 WATCH cap against acquisition-underwriting STAGE 2.5 and cite the current revision in the body. |
| parcel-data-recovery | Says its endpoints are "live-monitored quarterly by ora-gis-endpoint-liveping". That task is not on the CC fleet, and the LAMS fleet is dark by design. | Strike the monitoring claim, or re-register the task through register-scheduled-task. |
| package-and-stage-skill | Calls itself the "companion to ora-skill-store-drift-check". That task is not on the CC fleet. | Same choice: strike the claim or re-register the task. |
| acquisition-underwriting | The description hard-codes the 11 market names from target-markets.json (in sync at v1.14 today, but it will drift) and claims "industrial/flex market research", which the CLAUDE.md tie-break gives to market-monitor. | Replace the names with "any target market in target-markets.json" and drop the market-research claim. Gate: eval-harness golden set plus a re-run of the routing baseline. |

### Phase 1 outcome (2026-11-05)

- **Done:** ora-flood-zoning-dd v1.7, cash-position-monitor v1.1, parcel-data-recovery v1.11, package-and-stage-skill v1.37, automation-health-monitor v1.16, insurance-climate-risk-comparison v1.1.
- **Found during verification:**
  - ora-flood-zoning-dd called building-pad SFHA a "GATE KILL", contradicting acquisition-underwriting STAGE 0 item 5 and Ruling 5 (flag, never kill). insurance-climate-risk-comparison repeated the error. Both now say gate flag.
  - cash-position-monitor emailed "Gabriel + Eric", which breaks the scheduled-output routing rule. It now emails Gabriel only.
  - automation-health-monitor's "weekday 11:00 AM" became false when the task was ported to CC with a Monday-only cron (`5 11 * * 1`).
  - The two monitoring tasks (ora-gis-endpoint-liveping, ora-skill-store-drift-check) are not missing. They are on the LAMS fleet, which has been dark since 2026-10-30 by Gabriel's ruling. The text now says so instead of claiming live monitoring.
- **Dropped:** the acquisition-underwriting description edit. A RED probe (8 prompts × 3 routers) came back 24/24 correct, so there was nothing to fix.
- **Lint correction for Phase 2:** the "missing H1 version" count includes false positives. For example, acquisition-underwriting's H1 is `(v4.41 — Buy Box & Scorecard v1.1)`, which the strict `(vX.Y)` regex missed. Recount with a looser pattern before editing.

## Phase 2 — Conformance, then automate it

1. Add `(vX.Y)` to the H1 of 21 skills: adversarial-merge-gate, acquisition-underwriting, acquisition-underwriting-eval-harness, lease-form-qc, security-and-hardening, isolated-commit, cost-seg-tax-layer, exhibit-package-builder, branch-catchup, notion-quota-fallback, retail-underwrite-lens, merge-ready, municipal-permit-portal-recon, pm-portal-pnl-export, artifact-to-docx-report, land, evidence-dossier-drafting, external-artifact-intake, and the others in the lint output. Several of these are runtime-cache-mirrored in `~/.claude/skills`, so check for drift before editing.
2. Rewrite the 8 descriptions so they open with "Use when…" and keep their triggers. Strip versions and dates from descriptions (ora-flood-zoning-dd, acquisition-underwriting "rev 1.1", graph-app-registration "~2028").
3. Add three mechanical gates to `skill_ci_gates.py`: H1 version present, description starts with "Use", no `vN.N` or ISO date in the description. These are regex-checkable, so they belong in CI, not in prose. Use TDD: write the failing `unittest` cases first.

## Phase 3 — Workflow summaries in descriptions (test first)

The writing-skills SDO finding: when a description summarizes the procedure, agents follow the description and skip the body. Candidates:

- **disposition-analysis** (highest risk): its description states the decision doctrine itself ("Defaults to HOLD + cash-out refi… taxable sale is the rare exception").
- estoppel-request-generation, merge-ready, ora-open-decisions, branch-catchup, municipal-permit-portal-recon, exhibit-package-builder.

Procedure for each: micro-test first (no-guidance control vs. current description vs. triggers-only rewrite, 5 reps, every output read by hand). Rewrite only where the control shows the agent shortcutting the body.

## Phase 4 — Token cost (no behavior change)

1. Move inline changelogs to `versions/CHANGELOG.md`, the pattern acquisition-underwriting v4.35 already uses, in the skills where the changelog is 20% or more of the body: listing-agreement-qc (35%), county-sales-monitor (30%), package-and-stage-skill (29%), register-scheduled-task (28%), ora-setup-audit (27%), parcel-data-recovery (26%), dirty-tree-triage (26%), fleet-advisory-remediation (24%), deal-comparison, communication-intelligence, market-monitor (about 20% each). Estimated saving is about 10K words, roughly 13K tokens across loads. Verify that `package_skills.py` ships `versions/` and that the CHANGELOG-in-body rule in CLAUDE.md still holds (keep a one-row version index inline).
2. Split acquisition-underwriting (14.6K words, about 19K tokens per invocation) into per-mode references with progressive disclosure: SCREEN core inline; RCT, reassessment matrix and submarket intel in `references/`. Regression gate: acquisition-underwriting-eval-harness golden set, zero score movement. Governor constants are untouched. Then do the same for lease-form-qc (8K words) and automation-health-monitor (7K words).

## Phase 5 — Small routing fix (RED already observed)

- market-monitor ↔ submarket-spatial-analysis: both claim "submarket analysis", and the baseline split 2:1. Add reciprocal NOT-clauses: conditions/trends → market-monitor; drive-time, demographics, location score → submarket-spatial-analysis. Re-run the 3-router baseline; it should converge to 3/3.
- Commit the 16-prompt routing set plus expected answers (for example `tools/routing_golden.md`) as the RED harness for every future description edit.

## Carried forward from the 2026-10-30 catalog review (not re-litigated)

- 10 store-only skills are still absent from the repo: morning, ora-brand-fonts, pm-portal-delinquency-export, seller-ca-generation, setup-claude, street-listing-roster, tenant-consent-request, tenant-prospect-qa, underwrite-research-ingest, vacancy-status-gate.
- Open asks F6 (acquisition-proposal-generation vs. the LOI short form), F7 (cash-position-monitor), F8 (monthly-close, personal-portfolio).

## Explicitly not doing

- Rewriting descriptions the baseline shows route correctly.
- Trimming tombstones for retired skills (rent-comp, re-operations, maintenance-analytics, census-acs-extract). They are correct per CLAUDE.md, and the Phase 4 changelog move absorbs most of them anyway.
- Any governor or scorecard constant change.
