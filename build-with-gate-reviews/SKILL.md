---
name: build-with-gate-reviews
description: Use when building a non-trivial multi-file subsystem or tool from a written design — new coordination/locking/state-machine logic, financial-decision code, or anything where a subtle concurrency or edge-case bug would be expensive to ship — before writing any implementation code.
---

# Build With Gate Reviews

## Overview

A five-step cycle for building something correctness-sensitive: **design → TDD implementation → independent adversarial review with real fault-injection → fix → independent re-verification.** Repeat per logical phase (milestone-sized chunk of the build); each phase closes with a Gate that must PASS before the next phase starts. The core insight: fresh eyes, deliberately trying to break the thing rather than just reading it, catch bugs that the implementer's own review and a green test suite both miss.

Validated 2026-07-10 against the AAOS v1.0 build (six phases/gates): the adversarial-review step found and fixed a Critical concurrency or correctness bug in 4 of 5 implementation phases — bugs a green test suite and the implementer's own read-through had both already passed.

## When to Use

- Building a new subsystem with concurrency, locking, state transitions, or money math — anywhere a race condition, off-by-one, or wrong edge case is expensive to discover in production.
- A multi-phase build (schemas → shared library → CLI tools → integration) where later phases depend on earlier ones being actually correct, not just "tests pass."
- Not for: one-file scripts, throwaway/prototype code, config changes, or anything where a bug is cheap to notice and fix immediately. Use plain TDD for those.

## The Cycle

| Step | Who / what | Deliverable |
|---|---|---|
| 1. Design | A strong-reasoning pass over the phase's scope: interfaces, data shapes, failure modes, explicit non-goals | A short design doc — not code |
| 2. TDD implementation | Tests written first (they should fail before the code exists), then the minimal code to pass them | Working code + passing tests |
| 3. Independent adversarial review | A **fresh context** (different session/subagent, no memory of writing the code) reviews the *whole diff*, not a summary of it, and is explicitly instructed to try to break it — race conditions, malformed input, partial failure, concurrent writers — not just check style | A findings list, each with a concrete repro or failure scenario, rated by severity |
| 4. Fix | Address every finding — Critical and Important at minimum | Updated code + tests |
| 5. Independent re-verification | The reviewer (or another fresh context) re-checks that each finding is actually fixed, re-runs the fault-injection repro, and confirms the full suite is still green — **not** a re-read of the fixer's own report | PASS/FAIL verdict with evidence |

A phase's Gate is the record of steps 3–5: findings, resolutions, and re-verification evidence. Don't declare a phase done on step 2 alone — a green suite proves the code does what the tests say, not that the tests covered the right things.

For a small, single-phase build (roughly: one tool, one file, no multi-milestone dependency chain), collapse to one Gate at the end rather than per-milestone — the cycle still applies, just once.

## Why Step 3 Must Be a Fresh Context

The implementer (even you, later in the same session) has already anchored on their own mental model of the code and will re-read what they *meant* to write, not what's actually there. A subagent or session with **no prior involvement in writing the code**, given the full diff and told explicitly to find ways it breaks — not "does this look reasonable" — surfaces a different class of bug: the one that's invisible from inside the implementation's own assumptions.

Confirmed by direct comparison: asked to plan a build without this skill, an agent's "review" step was self-review of its own diff, with no independent pass at all. The same agent, given this skill, added an explicit fresh-context adversarial reviewer step and an independent re-verification step that re-runs the repro rather than trusting the fixer's report — unprompted, because the skill named the specific failure mode (TOCTOU gaps, non-atomic state transitions, idempotency under a crash mid-operation) the fresh reviewer should hunt for.

## Common Mistakes

| Mistake | Why it fails |
|---|---|
| "I already tested it, self-review is enough" | Self-review inherits the implementer's blind spots — it's the same context that missed the bug while writing it. |
| Review reads a summary/description of the change instead of the actual diff | Findings from a paraphrase are findings about the paraphrase, not the code. |
| Review checks style/naming and calls it done | Style review isn't adversarial review — it doesn't try to break anything. |
| Skipping step 5 ("the fixer said it's fixed") | A fixer's own report of a fix is not independent verification of the fix — re-run the actual repro. |
| Treating "tests pass" as the Gate | Tests only prove what they were written to check; adversarial review is what catches what the tests didn't think to check. |

## Quick Reference

Design (strong reasoning) → Tests-first → Code → **independent** adversarial review (real repro, not a read-through) → fix → **independent** re-verify (re-run the repro, don't trust the fix report) → next phase.
