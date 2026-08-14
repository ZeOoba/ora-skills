---
name: acquisition-underwriting-eval-harness
description: "Golden-set regression harness for the acquisition-underwriting skill — replays a frozen set of 6 past SCREEN-mode deals against CURRENT SKILL.md doctrine, diffs the resulting Combined score against a re-baselined golden snapshot, flags deltas beyond tolerance, and writes a dated re-runnable snapshot. Use after any material doctrine edit to acquisition-underwriting (a scorecard-weight amendment, a new QC-gate rule, a ruling/amendment) to check whether the change actually moved scores and by how much — not a live deal-evaluation tool, never invoke this for an actual acquisition screen. PILOT — one skill only, no scheduled-task registration yet."
---

# Acquisition-Underwriting Eval Harness (pilot, v1.0 — 2026-08-14)

Companion to `acquisition-underwriting/SKILL.md`, not a replacement for it. This skill answers
one question the firm previously had no way to answer: **after a doctrine edit, did the skill's
scoring actually change, and by how much?** It does not evaluate real deals and must never be
invoked for one — its inputs are deliberately frozen historical facts, not live research.

Built 2026-08-14 per Gabriel's ratified scope (`memory/reference_skill_eval_harness_gap_2026-08-14.md`):
pilot on `acquisition-underwriting` only, harness-only (no scheduled-task registration, no
extension to other skills this pass).

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
- Not wired into any scheduled task. Re-running it today requires a Claude Code session to
  drive the Agent-tool orchestration below — see LIMITATIONS.

## Data-quality findings (read before trusting any delta)

**1. RCT v03 date-boundary finding (the important one — discovered running the first baseline
2026-08-14).** All 6 golden deals were screened 2026-06-09/06-20, **before** the 2026-07-14
RCT v03 replacement-cost recalibration — a deliberate, ratified, large tightening of the Basis
floor (old RCT v02 + 30%/25% ramp → RCT v03 + 65%/60% ramp; SKILL.md's own text: the old ramp
"would have set the Columbus floor at a price at which every candidate in the buy-box
clears"). The first replay attempt diffed today's doctrine directly against each deal's
pre-recalibration archived Notion score and got large "deltas" on every scored deal (e.g. Port
Sheldon's Basis went from clearing comfortably pre-v03 to breaching post-v03, at an unchanged
price/SF) — all of them the already-ratified v03 effect, not a regression. **Comparing across a
known doctrine-version boundary defeats the purpose of a regression harness.** Fixed by
re-baselining: **`golden` in every file is now the 2026-08-14 replay's own output under current
doctrine** (`baselined_date`, `baselined_against_skill_sha`), not the archived pre-v03 Notion
score. The original archived score is preserved under the sibling key `archived_pre_v03_reference`
for historical context only and is never read by `diff_verdict.py`. **Practical consequence:**
this harness cannot yet detect a *regression that happened between 2026-06-09 and today* (it
never had a doctrine-consistent baseline to compare that period against) — it can only detect
drift from **today's baseline forward**. That is the correct and only honest scope for a first
run; a golden set assembled from deals screened after 2026-07-14 would not have this limitation,
and none exist yet in the Deal Sourcing Log (confirmed via a dedicated research pass, 2026-08-14).

**2. Archived pre-v03 tier/arithmetic inconsistencies (historical context only, no longer
diffed against).** 3 of the 6 deals' `archived_pre_v03_reference` blocks show a Notion-recorded
verdict tier that doesn't match what VERDICT BANDS + the STAGE 2.5 DD-Critical-ceiling rule would
predict from the archived Combined score, and 2 of those also show archived Quality + Economics
not summing to the archived Combined. Cause not determinable from the archive. Irrelevant to
today's pass/fail (see finding 1 — that block is never diffed), but kept because it's a real,
otherwise-undocumented gap in the Deal Sourcing Log's own internal consistency.

**3. Frozen-input-packet incompleteness.** Even against the re-baselined golden values, 4 of 6
baseline replays left 2-3 of the 7 scorecard categories `null` (Product & Physical, Seller &
Motivation, Tenancy & Lease most often) because the input packet — reconstructed from Notion's
*structured* fields — doesn't capture the physical/site/comp detail the *original* live-tooled
screens evidently had. Only 2196 Port Sheldon and Liberty Office Park resolved cleanly (zero
nulls); those are `confidence: HIGH` and the ones most worth watching for a future doctrine-edit
delta. The other 4 are `confidence: LOW`, run and report, but are `scored: false` /
`informational_only: true` — excluded from the strict pass/fail tally until their input packets
can be enriched. **Because of both findings above, the harness's primary and only pass/fail-gating
signal is the Combined-score delta — never the tier label** (see `golden_set/SCHEMA.md` and each
deal's `diff_policy`).

## Golden set

`golden_set/*.json` — 6 frozen deals, schema documented in `golden_set/SCHEMA.md`. `golden` =
the 2026-08-14 re-baseline (finding 1 above); confidence reflects how many of that replay's 7
scorecard categories are null (finding 3):

| Deal | Confidence | Scored (gates PASS/FLAG)? | Golden Combined | 3-run range |
|---|---|---|---|---|
| 2196 Port Sheldon St, Jenison MI | HIGH (0 nulls) | Yes | 29.33 (mean of 3) | 4.5 pts |
| Liberty Office Park, West Chester OH | HIGH (0 nulls) | Yes | 28.67 (mean of 3) | 1.0 pt |
| E Fulton St Portfolio, Columbus OH | LOW (2 nulls) | No — informational only | 47.0 (1 run) | n/a |
| 11850 Hamilton Ave, Cincinnati OH | LOW (2 nulls, no ask/NOI) | No — informational only | 22.4 (1 run) | n/a |
| 1333 Research Rd, Gahanna OH | LOW (3 nulls) | No — informational only | 9.0 (1 run) | n/a |
| 470 McCormick Blvd, Columbus OH | LOW (3 nulls, Quality fully null) | No — informational only | 0.0 (1 run) | n/a |

`golden.combined` for the 2 HIGH deals is the mean of 3 independent replays (see "Limitations" —
the repeatability check that produced these ranges is why the tolerance is 5.0 pts, not 3.0). The
4 LOW deals are single-run values, run and reported for completeness but excluded from strict
pass/fail regardless of any future repeatability finding.

First snapshot: `runs/2026-08-14T205042Z_baseline-rebaselined.json` (2 scored deals, both PASS by
construction — golden values are drawn from this same repeatability-corrected set; the next real
run, after any doctrine edit, is the first one to diff against it and produce a non-trivial
result).

## Procedure

**Step 0 — provenance.** Capture the current `acquisition-underwriting/SKILL.md` git commit hash
(the hash of the most recent commit that touched this file, not a git blob hash) so the
snapshot can be attributed to an exact doctrine revision:
```
git -C <ora-skills repo root> log -1 --format=%H -- acquisition-underwriting/SKILL.md
```

**Step 1 — for each `golden_set/*.json` file**, spawn one subagent (Agent tool,
`model: "fable"` — this replays scored/financial logic and must never run below the Fable
floor) with a prompt built from this template:

```
You are running a FROZEN REPLAY of the acquisition-underwriting skill's SCREEN mode, for a
regression-test harness — NOT a real deal evaluation.

Read the skill's scoring mechanics from: <path to acquisition-underwriting/SKILL.md>
(STAGE -1 through STAGE 2.2 govern SCREEN mode; VERDICT BANDS defines tier labels;
UNDERWRITING CONVENTIONS + the Replacement Cost Table supply RCT v03 figures.)

Apply SCREEN mode's Stage -1 through Stage 2.2 mechanics to ONLY the frozen facts below.
Do NOT fetch live data of any kind — no Notion query, no market-monitor query, no web search,
no comp pull, no county/GIS lookup. Where the documented procedure calls for a live check you
cannot perform in frozen-replay mode (e.g. Stage 2.1 bear-mode via market-monitor, Stage 2.3
concentration check via live portfolio composition), apply the skill's own DOCUMENTED FALLBACK
for that case (e.g. "If BOTH sources are unavailable: record bear-mode state as UNKNOWN,
proceed with bear-mode OFF for scoring... cap the screen at T2 WATCH") and state which fallback
you used in `notes`. Do not invent a value a live check would have supplied.

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

**Step 2 — parse.** Extract the single fenced `json` block from each subagent's final response.
If a response contains zero or more than one fenced json block, that deal's replay FAILED —
report it as an error, do not guess which block was intended.

**Step 3 — diff.** For each parsed observed result, call
`lib.diff_verdict.diff_verdict(golden_json, observed_json)`.

**Step 4 — snapshot.** Collect all `diff_verdict()` results into a list and call
`lib.record_run.record_run(results, run_dir="runs/", skill_sha=<Step 0 hash>, run_label=<your
choice, e.g. "baseline" or "post-<doctrine-change>">)`.

**Step 5 — report.** Print a summary table (deal_id, status, scored, combined_golden,
combined_observed, combined_delta) and call out any `status == "FLAG"` among `scored: true`
rows prominently — that is the harness's actual regression signal. `informational_only` rows
are shown for completeness but are not evidence of a regression by themselves (see Data-quality
finding above).

## Self-test (regression-detection proof)

Never run this against a real `golden_set/*.json` file — always against a copy in `fixtures/`.

`fixtures/regression_test_mutation.json` (mutated copy of the Port Sheldon golden file,
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
4. Confirm `combined_delta` from `diff_verdict()` exceeds the 3.0-pt tolerance and `status ==
   "FLAG"`. This proves the load → replay → diff → flag pipeline works end to end.

**Caught in this build:** running this self-test surfaced a real bug — a 2026-08-14 golden-set
rebaseline renamed the tier key from `archived_verdict_tier` to `verdict_tier`, but
`diff_verdict.py` (and its own unit-test fixture) still read the old name, so `archived_tier`
silently came back `None` for every real file. The unit suite didn't catch it because its
synthetic fixture had drifted to match the same stale key; the self-test did, because it ran
against a REAL golden file. Fixed, and a dedicated regression test added
(`test_reads_golden_verdict_tier_key_not_archived_verdict_tier`) so a future key rename can't
silently reintroduce the same desync. This is itself evidence the self-test mechanism works,
not just its designed-in mutation case.

This test perturbs an INPUT, not doctrine — by design (frozen inputs never change between real
re-runs of the actual golden set). The mechanism that isolates skill-logic drift from
external-data drift is the freezing discipline itself (the same `golden_set/*.json` fed every
time), not anything the diff engine infers — the diff engine only needs to catch an output
delta given an IDENTICAL input, which is exactly what a real doctrine edit produces.

## Limitations / follow-ups (not built this pass)

Found by a mandatory adversarial REFUTE pass (2026-08-14, Fable-pinned) run against this build
before it was called done — listed here rather than silently fixed where fixing would have
meant fabricating data this harness doesn't actually have:

- **Replay nondeterminism is real and now measured, not assumed.** A 3-run repeatability check
  on the 2 HIGH-confidence deals (identical frozen inputs, identical doctrine, 3 independent
  subagent replays each) found a 4.5-point Combined-score range on Port Sheldon and a 1.0-point
  range on Liberty — see each deal's `repeatability` block in `golden_set/*.json`. The original
  3.0-pt tolerance would have produced false FLAGs from LLM run-to-run noise alone. Tolerance
  widened to 5.0 pts harness-wide as a direct, cited response (not an arbitrary round number —
  see `diff_policy.tolerance_rationale` in each file). **Only 3 samples per deal exist; this is
  a first estimate, not a converged one.** More repeat runs (ideally 5–10 per HIGH-confidence
  deal) would tighten the tolerance and increase confidence that a future FLAG is real doctrine
  drift rather than residual noise. `golden.combined` for both HIGH deals is now the mean of the
  3 samples, not a single run.
- **SKILL.md-citation leakage on named-example deals.** Port Sheldon is cited by address in
  SKILL.md's own text as the worked validation example for the price-watch trigger. One of the 3
  repeatability runs appears to have drawn on that citation (awarding Seller & Motivation points
  for an owner-user-vacating characterization not present in the frozen `inputs`); two independent
  re-runs correctly declined to. This is a narrow, real, and only partially mitigable risk for any
  future golden deal that also happens to be named in SKILL.md's own worked examples — a frozen
  replay reading the full skill file sees its own answer key for that one input. No golden deal in
  this set other than Port Sheldon is currently affected (checked: none of the others are cited by
  address in SKILL.md).
- **The strict-scoring gate cannot currently see an Economics-side doctrine edit.** Both HIGH
  deals (Port Sheldon, Liberty) breach both the Basis and Yield floors, pinning Economics at 0.0
  in every run. A future edit to the Basis linear scale, the Yield slope, or the RCT top-of-scale
  would move neither scored deal unless it happened to flip a floor from breach to clear — the
  exact class of edit (a replacement-cost/floor recalibration) that motivated this whole build in
  the first place. Only the LOW-confidence (unscored) rows currently exercise nonzero Economics
  (E Fulton: Basis 25.0; Hamilton: Basis 7.4, assumption-contingent). Enriching one nonzero-Economics
  deal's input packet to HIGH confidence — or sourcing a 7th golden deal that clears at least one
  floor — would close this gap; not done in this pass because it would require facts not
  currently available (see "frozen-input-packet incompleteness" above), and inventing them would
  violate the no-fabrication constraint this whole harness exists to uphold.
- **No unattended re-run path.** Re-running today requires a Claude Code session to drive the
  Agent-tool orchestration in Steps 1–2. A headless `claude -p` CLI script would remove that
  dependency but was descoped for this pilot (flagged, not built).
- **No scheduled-task registration.** Per ratified scope — needs its own Gabriel-gated
  registration via `register-scheduled-task` if this pattern proves out.
- **Not extended to other skills.** Piloted on `acquisition-underwriting` only.
- **4 of 6 golden deals are LOW-confidence / informational-only** (input-packet incompleteness —
  2-3 of 7 scorecard categories null in the replay) — a 3rd-4th HIGH-confidence golden deal would
  strengthen the strict-scoring set beyond its current 2 rows; none of the remaining candidates in
  the Deal Sourcing Log currently have complete enough facts (confirmed via a dedicated research
  pass, 2026-08-14).
- **The re-baselined golden values are themselves unverified LLM judgment**, not ground truth —
  the numeric floor/YoC/discount components were independently recomputed and verified correct
  during the REFUTE pass, but the judgment-scored categories (Product & Physical, Market &
  Location, Value-Add) are enshrined as the harness's reference point without independent
  human sign-off. Acceptable for a pilot establishing the pattern; worth flagging explicitly
  rather than implying more certainty than exists.
