---
name: acquisition-underwriting-eval-harness
description: "Use when a doctrine edit to acquisition-underwriting (a scorecard-weight amendment, a new QC-gate rule, a ruling/amendment, an RCT table revision) needs a regression check against the frozen SCREEN-mode golden set. Trigger on: eval harness, golden set, golden-set regression, replay the golden set, did the doctrine change move scores, rebaseline the goldens, harness run, scheduled-poll, doctrine skip gate. NOT a live deal-evaluation tool — never invoke this for an actual acquisition screen (that is acquisition-underwriting). PILOT — piloted on one skill only; runs as a daily-polling scheduled task."
---

# Acquisition-Underwriting Eval Harness (v1.2 — pilot)

Companion to `acquisition-underwriting/SKILL.md`, not a replacement for it. This skill answers
one question the firm previously had no way to answer: **after a doctrine edit, did the skill's
scoring actually change, and by how much?** It does not evaluate real deals and must never be
invoked for one — its inputs are deliberately frozen historical facts, not live research.

Built 2026-08-14 per Gabriel's ratified scope (`memory/reference_skill_eval_harness_gap_2026-08-14.md`): pilot on `acquisition-underwriting` only. Live as the CC/MCP scheduled task `ora-acquisition-underwriting-eval-harness` (daily poll) since 2026-08-14. **Build history, REFUTE-pass findings and the full data-quality narrative live in `references/findings-and-limitations.md`** — read it before rebaselining a golden, changing the tolerance, or trusting an unusual delta; this file carries the operating procedure.

## When to invoke

- After editing `acquisition-underwriting/SKILL.md` (a scorecard weight, a Stage 1 floor, a
  QC-gate rule, an RCT table revision) — run this BEFORE and AFTER the edit and compare the two
  dated snapshots in `runs/` to see what moved.
- Periodically, as a sanity check that the skill still reproduces its own documented scoring
  mechanics against known cases (catches an accidental doctrine regression even absent an
  intentional edit).

## What it is NOT

- Not a live deal-evaluation tool. Frozen replay subagents are explicitly forbidden from
  fetching live data (Notion, market-monitor, web, comp pulls) — see the replay prompt below.
- Not a judgment on whether a doctrine edit was "right." It only reports whether the score
  changed and by how much; whether that change is an improvement is Gabriel's call.
- Not a headless/standalone script. It IS wired into a scheduled task (CC/MCP fleet,
  `ora-acquisition-underwriting-eval-harness`, daily poll — live 2026-08-14), but that task still
  drives the Agent-tool orchestration below from inside an authenticated Claude Code session; a
  bare `claude -p` subprocess cannot run it. See LIMITATIONS.

## Data-quality findings (read before trusting any delta)

**Read `references/findings-and-limitations.md` (Data-quality findings 1–5, full text) before rebaselining any golden or interpreting a FLAG on an informational-only deal.** Operative consequences, in force today:

1. **RCT v03 date boundary.** All 6 golden deals were screened before the 2026-07-14 RCT v03 recalibration; `golden` in every file is therefore the replay's own output under current doctrine (`baselined_date`, `baselined_against_skill_sha`), never the archived pre-v03 Notion score (kept only as `archived_pre_v03_reference`, never diffed). The harness detects drift from **today's baseline forward only**.
   - **Construction-type multiplier (acquisition-underwriting v4.37).** Frozen golden fixtures are NOT edited. Tilt-up (`REDACTED-019`) and precast (`REDACTED-024`) replay at ×1.00. Only `REDACTED-020` (steel frame and masonry, mixed) carries a non-baseline type: its discount % moves (about 89.9%) but its Basis stays at the 25.0 cap and Combined does not move, so no score re-baseline is needed. Record the new `baselined_against_skill_sha` at the next harness run as usual.
2. **Archived tier/arithmetic inconsistencies** in 3 of 6 `archived_pre_v03_reference` blocks — historical context only, never diffed.
3. **Frozen-input-packet incompleteness.** Deals whose replays leave 2–3 scorecard categories null are `confidence: LOW`, `scored: false` / `informational_only: true` — run and reported, excluded from the strict pass/fail tally. **The harness's only pass/fail-gating signal is the Combined-score delta — never the tier label** (`golden_set/SCHEMA.md`, each deal's `diff_policy`).
4. **REDACTED-156 enrichment** closed the Economics blind spot: it is the only scored deal with nonzero Economics (Basis 25.0/25); its Tenancy & Lease null is irreducible by the frozen-snapshot discipline, not a research gap.
5. **One replay agent can emit two conflicting completions** under one task-id — handled by Step 1.5 (wait for all completions; differing blocks from one task-id = failed replay; identical answers from different task-ids are NOT a failure).

## Golden set

`golden_set/*.json` — 6 frozen deals, schema in `golden_set/SCHEMA.md`. `golden` = the 2026-08-15 re-baseline (Hamilton rebaselined 2026-09-12 under the v4.21 no-price-no-NOI rule); confidence reflects how many of a replay's 7 scorecard categories are null (finding 3), except where a null is structurally irreducible (finding 4). Every `golden.combined` is a repeatability-checked mean, never a single run; each file's `known_gaps` records which samples were excluded and why, and its `repeatability` block is the tracked evidence trail.

irreducible rather than a research gap (finding 4 — REDACTED-156's Tenancy & Lease):

| Deal | Confidence | Scored (gates PASS/FLAG)? | Golden Combined | Observed range |
|---|---|---|---|---|
| REDACTED-023 | HIGH (0 nulls) | Yes | 26.81 (mean of 8, leaked run excluded) | 3.5 pts (n=8 clean) |
| REDACTED-069, West Chester OH | HIGH (0 nulls) | Yes | 28.11 (mean of 9) | 2.0 pts (n=9) |
| REDACTED-059, Columbus OH | MEDIUM (1 null, irreducible — see finding 4) | Yes | 56.79 (mean of 7) | 4.0 pts (n=7) |
| REDACTED-102 Ave, Cincinnati OH | LOW (Basis null by v4.21 rule; 1-3 Quality nulls) | No — informational only | 17.0 (mean of 3 under v4.21, rebaselined 2026-09-12; all pre-v4.21 runs excluded) | **7.0 pts (n=3) — exceeds tolerance** |
| REDACTED-113 Rd, Gahanna OH | LOW (3 nulls) | No — informational only | 11.75 (mean of 4) | **6.0 pts (n=4) — exceeds tolerance** |

**Every run gates on the MEAN of 3 replays per deal, never a single draw** (Steps 1–3 below) — a single replay is not a stable measurement (REDACTED-119's clean single-draw range is 3.5 pts against a 5.0-pt tolerance; it measured 7.0 before the leakage fix). Widening the tolerance instead of averaging was explicitly rejected.

**`runs/` is git-ignored** — snapshots are machine-local run state, still written and still the durable local record, just not versioned (a daily fire into a tracked directory manufactured a false "uncommitted work" signal in the single-writer checkout). Every snapshot before `2026-08-14T215119Z_scheduled-poll.json` passed by construction (golden-vs-itself) and is not evidence the harness works; that scheduled-poll was the first genuine replay-to-golden diff, and its values are single replays diffed against pre-rebaseline goldens — not an example of current procedure.

## Procedure

**Step -1 — patch-time skip gate (added 2026-10-23, v4.35 session).** Every session that edits `acquisition-underwriting/SKILL.md` runs the gate BEFORE reporting done, against the pre-edit backup it took when it checked the base hash (v4.8 stamp rule):
```
python lib/doctrine_skip_gate.py --prior <pre-edit backup> --current <acquisition-underwriting>/SKILL.md
```
Exit 0 = SKIP: state "harness skipped: change confined to the changelog/intro" in the hand-off. Exit 10 = RUN: either run Steps 0-5 now or record "harness RUN pending" in the hand-off so the scheduled poll's hash check picks it up. A reporting-only line placed in the body still returns RUN (v4.35 did); the gate is never overridden by judgment. Put reporting-only additions in a `references/` file where possible, not under a `## ` heading of SKILL.md.

**Step 0 — provenance.** Capture the current `acquisition-underwriting/SKILL.md` git commit hash
(the hash of the most recent commit that touched this file, not a git blob hash) so the
snapshot can be attributed to an exact doctrine revision:
```
git -C <ora-skills repo root> log -1 --format=%H -- acquisition-underwriting/SKILL.md
```

**Step 1 — for each `golden_set/*.json` file**, spawn **3 independent subagents** (Agent tool,
`model: "opus"` (Opus 5.5) — this replays scored/financial logic and must never run below the
Opus 5.5 floor (Fable retired from dispatch 2026-10-05)), each with the SAME prompt built from the template below. Three, not one: a single replay
is not a stable measurement (n=6 finding — REDACTED-119's single-draw range was 7.0 pts at the
time against a 5.0-pt tolerance, since partly attributable to leakage now fixed — see
Limitations), and the gate compares the mean of the 3 in Step 3.

Send all 3 in one message so they run concurrently, and do NOT vary the prompt between them —
identical prompts are what make them samples of one distribution rather than three different
questions. For a 6-deal set that is 18 agents per run.

Prompt template (used verbatim for every replay of every deal, substituting only the frozen
facts):

```
You are running a FROZEN REPLAY of the acquisition-underwriting skill's SCREEN mode, for a
regression-test harness — NOT a real deal evaluation.

Read the skill's scoring mechanics from: <path to acquisition-underwriting/SKILL.md>
(STAGE -1 through STAGE 2.2 govern SCREEN mode; VERDICT BANDS defines tier labels;
UNDERWRITING CONVENTIONS + the Replacement Cost Table supply RCT v03 figures.)

Apply SCREEN mode's Stage -1 through Stage 2.2 mechanics to ONLY the frozen facts below.
Do NOT fetch live data of any kind — no Notion query, no market-monitor query, no web search,
no comp pull, no county/GIS lookup, and no read of ANY file under `memory/` or any other
session-context/memory store (this specifically includes `memory/deal-decision-ledger.md` and
any Notion-mirrored deal-decision or event log — these can record this exact deal's actual
historical outcome, which is an answer key, not a live-data source, but is exactly as
contaminating). Stage -1 item 5's "ledger precedent check" is NOT PERFORMABLE in frozen-replay
mode for this reason — skip it and say so in `notes`; do not read the ledger to answer it. Where
the documented procedure calls for a live check you cannot perform in frozen-replay mode (e.g.
Stage 2.1 bear-mode via market-monitor, Stage 2.3 concentration check via live portfolio
composition), apply the skill's own DOCUMENTED FALLBACK for that case (e.g. "If BOTH sources are
unavailable: record bear-mode state as UNKNOWN, proceed with bear-mode OFF for scoring... cap the
screen at T2 WATCH") and state which fallback you used in `notes`. Do not invent a value a live
check would have supplied.

If the SKILL.md text you just read discusses THIS EXACT property (by street address) anywhere
outside the frozen facts below — e.g. as a worked example, a validation case for a rule, or a
price-watch/re-engage citation — you MUST disregard that discussion entirely for scoring
purposes. Score using ONLY the frozen facts below; do not award points, assumptions, or
characterizations (e.g. seller motivation, occupancy status, condition) that come from SKILL.md's
own narrative text about this address rather than from the frozen facts. If you noticed such a
citation and excluded it, say so explicitly in `notes`; if you are not sure whether something you
used came from the frozen facts or from SKILL.md's own text about this address, treat it as
inadmissible and drop it.

FROZEN FACTS:
<paste the golden file's "inputs" block verbatim>

Compute Quality, Economics, Combined (=Quality+Economics), Expected Score (=Combined x P(exec)),
P(exec) %, the verdict tier per VERDICT BANDS, the Floor Result, and a category_breakdown
(Basis/Yield/Product & Physical/Market & Location/Seller & Motivation/Tenancy & Lease/Value-Add
Optionality) if you can derive each component from the frozen facts (use null for any component
you cannot support from the given facts alone — never guess).

End your response with EXACTLY ONE fenced json block, no other json blocks anywhere in your
response, matching this shape:
```json
{"combined": <float>, "quality": <float|null>, "economics": <float|null>,
 "expected_score": <float|null>, "p_exec_pct": <float|null>, "verdict_tier": "<string>",
 "floor_result": "<string>", "category_breakdown": {<string>: <float>, ...} | null,
 "notes": "<one paragraph: fallbacks used, assumptions made, anything the frozen facts left
 genuinely unresolvable>"}
```
```

**Step 1.5 — completion attribution + multi-completion check (2026-09-12 — see Data-quality
finding 5).** With up to 18 agents dispatched concurrently, completions arrive out of order, and a
single agent can emit MORE THAN ONE completion notification (same task-id, later notification).
1. **Attribute by task-id, never by arrival order.** Match every completion to its own spawn
   (task-id / agentId + description) from Step 1; never assign a completion to "the next open slot."
2. **Do not finalize any slot until every agent in the run has completed.** Record each completion
   as provisional, keyed by task-id. A slot is final only once all dispatched agents have reported
   and no further notification for that task-id arrived after its first one.
3. **Two or more completions from ONE task-id:** extract the fenced json block from each. If the
   parsed blocks are identical (a re-notification of the same answer), accept it once. If they
   DIFFER in any field, that replay FAILED — treat it under Step 2's failure rule; never pick the
   first, the last, or the more plausible one.
4. **Identical answers from DIFFERENT task-ids are NOT a failure.** SCREEN scores are coarse integer
   judgments and independent replays legitimately agree: the 2026-09-12 run produced
   byte-identical `combined` + `category_breakdown` pairs for REDACTED-119 r2/r3 (29.0) and REDACTED-156
   r2/r3 (55.0) from separate agents. Rejecting agreement would have cut both scored deals to n=1.
   Only a task-id mismatch (a completion whose description names a different deal/slot than its
   spawn) indicates mis-attribution.
State in the Step 5 report every task-id that emitted more than one completion, and whether the
blocks matched.

**Steps 2–4 in one command (2026-09-13 — use this; never hand-copy scores into a driver script).**
Once every agent in Step 1 has completed, run from the harness root:
```
python lib/parse_replays.py --subagents-dir <~/.claude/projects/<project>/<session-id>/subagents> \
    --agent-ids <the 18 task-ids from Step 1> [--failed-agent-ids <ids flagged in Step 1.5>] \
    --record --skill-sha <Step 0 hash> --run-label <label>
```
It reads each agent's on-disk transcript (`agent-<id>.jsonl`), applies the Step 2 one-block rule
below, fails any agent whose transcript shows more than one completion with differing blocks, and
attributes each replay to its golden deal by the FROZEN FACTS block in its own prompt (never by
description or arrival order), then aggregates, diffs and snapshots.
- **Always pass `--agent-ids`.** Without it every replay transcript in the session is pooled — a
  session that also ran rebaseline replays silently inflates `n` (09-12 session: Hamilton n=5).
- **The transcript cannot see every Step 1.5 failure.** A differing earlier completion notification
  can leave no trace on disk (09-12 Hamilton r3: the 15.0 block exists only in the notification).
  Keep watching notifications per Step 1.5 and pass any such task-id via `--failed-agent-ids`.
- **Completion is inferred from transcript structure, not `stop_reason`** — ~5% of real completed
  replays carry no `end_turn` stamp (09-12 REDACTED-156 r2).
- **Exit codes:** **0** = every deal has ≥1 parsed replay, none failed. **4** = every deal has ≥1
  parsed replay but ≥1 replay failed (degraded `n`, listed per deal; snapshot still recorded; the
  scheduled task's deal-level Step 4 rule may still advance). **3** = a deal has no result or could
  not be aggregated, a requested agent-id has no transcript, or a requested agent could not be
  attributed — nothing recorded, do not advance state.

Verified 2026-09-13 against that day's 18 real transcripts: identical `combined_observed`,
`category_deltas` and status to the hand-copied run (exit 0); and against the 09-12 session, where
it recovers the no-`end_turn` REDACTED-156 replay (n=3, 54.67, matching the recorded run).

**Step 2 — parse.** Extract the single fenced `json` block from each subagent's final response.
If a response contains zero or more than one fenced json block, that replay FAILED — report it
as an error, do not guess which block was intended. A failed replay is **never** silently
dropped from its deal's sample set: report it, and if fewer than 3 replays parsed for a deal,
say so explicitly in Step 5 (`aggregate.n` records what actually went into the mean).

**Step 2.5 — aggregate.** For each deal, pass its list of parsed replays to
`lib.aggregate_replays.aggregate_replays(replays)`. This returns ONE observed dict whose
`combined` is the **mean** across replays, plus an `aggregate` block carrying `n`,
`combined_samples`, `combined_stdev`, `combined_sem`, `combined_range`, and
`category_null_counts`. It also normalizes the replay prompt's display-name category keys
("Product & Physical") to the golden files' snake_case ("product_physical") — without that,
`diff_verdict`'s per-category deltas silently return `None` on every real replay.

**Step 3 — diff.** For each deal's aggregated observed result, call
`lib.diff_verdict.diff_verdict(golden_json, observed_json)`. The gate compares the 3-replay mean
against `golden.combined` — never a single draw.

If a deal's own `aggregate.combined_range` exceeds its `diff_policy.tolerance_combined_pts`,
report that alongside the verdict: the replays disagreed with each other by more than the gate's
own width, so that deal's PASS/FLAG is weakly supported this run regardless of which way it
landed. REDACTED-119 had a range of 7.0 vs the 5.0 tolerance at n=6 (partly a leakage artifact,
fixed 2026-08-15 — clean range is now 3.5, see Limitations). As of the fix, a >5.0-pt range on
REDACTED-119 in a single 3-replay run is NOT expected to be routine — treat it as worth
investigating, not as the known-noisy row it used to be.

**Step 4 — snapshot.** Collect all `diff_verdict()` results into a list and call
`lib.record_run.record_run(results, run_dir="runs/", skill_sha=<Step 0 hash>, run_label=<your
choice, e.g. "baseline" or "post-<doctrine-change>">)`.

**Step 5 — report.** Print a summary table (deal_id, status, scored, combined_golden,
combined_observed, combined_delta, plus `n` and `combined_range` from the aggregate block) and
call out any `status == "FLAG"` among `scored: true` rows prominently — that is the harness's
actual regression signal. `informational_only` rows are shown for completeness but are not
evidence of a regression by themselves (see Data-quality finding above). Also report any deal
where fewer than 3 replays parsed, or where `combined_range` exceeded tolerance.

**Before treating any FLAG as doctrine drift, check Step 0's SHA against the previous run's.**
If the doctrine SHA is UNCHANGED, a FLAG cannot be a regression by construction — it is noise, a
golden-set edit, or an input-packet change. Check `git log` on the golden file before escalating.

## Self-test (regression-detection proof)

Never run this against a real `golden_set/*.json` file — always against a copy in `fixtures/`.

`fixtures/regression_test_mutation.json` (mutated copy of the REDACTED-119 golden file,
`asking_price` cut ~50%, $1,995,000 → $995,000) and `fixtures/self_test_result.py` are kept as
permanent, re-runnable self-test assets — not scratch output. Re-run anytime with
`python fixtures/self_test_result.py` (no live calls; it re-derives the diff from a
already-captured mutated-replay result and asserts `status == "FLAG"`). Nothing under
`fixtures/` is ever written to `runs/` — the two stay clearly separated.

To reproduce the full self-test from scratch (e.g. after changing `diff_verdict.py`):
1. Copy a `golden_set/*.json` file to `fixtures/regression_test_mutation.json` and mutate ONE
   frozen input meaningfully.
2. Run Steps 1–2 above against the mutated fixture only (skip Steps 4/5 — a fixture run must
   never land in `runs/`).
3. Diff the mutated replay's result against the REAL (unmutated) golden file's `golden` block
   — not against the mutated fixture's own `golden` block, which is a straight copy and would
   trivially self-match.
4. Confirm `combined_delta` from `diff_verdict()` exceeds the 5.0-pt tolerance and `status ==
   "FLAG"`. This proves the load → replay → diff → flag pipeline works end to end.


This test perturbs an INPUT, not doctrine — by design: the freezing discipline (the same `golden_set/*.json` fed every time) is what isolates skill-logic drift from external-data drift; the diff engine only needs to catch an output delta given an identical input, which is exactly what a real doctrine edit produces. The real bug this self-test caught in the original build (a silently stale `verdict_tier` key) and the regression test that guards it: `references/findings-and-limitations.md`.

## Limitations / follow-ups

- **Baseline model (2026-10-05):** the golden baselines are means of Fable replays; replays now run on Opus 5.5. Expect model-driven drift against those baselines; before trusting a FLAG, re-baseline once on opus (3 replays per deal) rather than reading it as a doctrine regression.

Standing limitations, each in force today. **Read `references/findings-and-limitations.md` for the four REFUTE passes (2026-08-14/15, 2026-09-12) behind them before changing any of them.**

- **Concurrency hazard (observed live):** a golden rebaselined mid-run diffs stale replays against a new golden and produces a pure-artifact FLAG. Re-check `git log`/mtimes on `golden_set/` immediately before Step 4 and discard any deal whose golden moved mid-run — do not record or alert on it. `ora-skills` is a single-writer checkout; prefer an isolated worktree for any harness edit.
- **Answer-key leakage is guarded by the prompt, not eliminated.** The replay prompt bars `memory/` (the deal-decision ledger records real outcomes) and instructs replays to disregard SKILL.md's own narrative about the exact frozen address (REDACTED-119 is cited there as a price-watch example). Leaked samples were excluded from the goldens; the failure mode was probabilistic (~1-in-6), so a clean 3-sample run is not proof the guard works.
- **Economics-side coverage is thin.** Only REDACTED-156 scores nonzero Economics; a moderate Basis-scale/RCT recalibration might not move it either (its discount sits well above the ≥76% top-of-scale). A 4th scored deal nearer its own floor boundary would help; none of the three LOW-confidence candidates have recoverable enough facts (Hamilton and 470 REDACTED-148 lack any NOI/price basis; REDACTED-113 Rd carries an archive arithmetic inconsistency).
- **No headless re-run path.** A nested `claude -p` subprocess has no persisted auth in this environment (confirmed by direct test). The unattended path is the registered scheduled task, which drives Steps 0–5 from inside an authenticated session; state (`last_checked_hash`, `last_checked_skill.md`) lives in the task's own folder under `~/.claude/scheduled-tasks/`, never in this repo. It polls a `git hash-object` content hash (catches uncommitted edits), advances state only on a fully clean run or a Step 1A skip, and posts to Notion on any scored FLAG **or** any parse failure — an all-error run must never look like a healthy no-op.
- **Not extended to other skills** (Gabriel, 2026-08-14): stay pilot-only until a few real doctrine-edit cycles have been observed.
- **3 of 6 golden deals are LOW-confidence / informational-only**; their >5.0-pt observed ranges are recorded, not smoothed over, and gate nothing.
- **The re-baselined golden values are themselves unverified LLM judgment**, not ground truth — numeric floor/YoC/discount components were independently recomputed; the judgment-scored categories carry no independent human sign-off. Acceptable for a pilot; do not imply more certainty than exists.

## Changelog

- **v1.2 (2026-10-27):** note on the `acquisition-underwriting` v4.37 construction-type multiplier added to the golden-set limitations (only REDACTED-044 carries a non-baseline type; its Basis and Combined do not move). No fixture, replay or diff logic changed.
- **v1.1 (2026-09-22):** Progressive-disclosure split — data-quality narrative, golden-set history, REFUTE-pass findings and the self-test's caught-bug story moved verbatim to `references/findings-and-limitations.md`; Procedure Steps 0–5 (incl. Step 1.5 and the Steps 2–4 command), the Self-test procedure and every standing limitation kept inline. Description rewritten as a routing surface ("Use when…", dates and pilot registration date dropped, trigger vocabulary added); version marker moved to the H1. No procedure, tolerance, golden value or lib/ code changed (lib tests: 137 passed; self-test: FLAG as expected).
- **v1.0 (2026-08-14):** Original 6-deal build, two same-day REFUTE passes, REDACTED-156 enrichment, scheduled-task registration (`ora-acquisition-underwriting-eval-harness`, CC/MCP fleet, daily poll). 2026-08-15 fourth pass: ledger/SKILL.md leakage guards + full rebaseline. 2026-09-12/13: Step 1.5 completion attribution, `lib/parse_replays.py` one-command Steps 2–4, Hamilton rebaselined under acquisition-underwriting v4.21.
