---
name: merge-ready
description: Use when Gabriel asks whether a PR is ready to merge, to merge one or several PRs, to check merge readiness, or to clean up after a merge ("merge PR 123", "is this mergeable", "merge readiness check", "land these PRs", "clean up the worktree after merge"). Runs the same gate order every time from real git/gh state, classifies red checks as real or known-external, then merges only on Gabriel's in-turn yes and runs the post-merge verification itself. NOT the review itself (adversarial-merge-gate), NOT syncing a stale branch (branch-catchup), NOT landing your own commit in a shared checkout (isolated-commit).
license: ORA Internal
---

# Merge-ready (readiness check, merge, post-merge verify, cleanup)

Code surface only. Report from `gh`/`git` output, never from remembered or assumed state.

## Hard rules
- **Merge only on Gabriel's in-turn yes**, per PR. "Check" or "is it ready" is a readiness report, not a merge request.
- **`website-canonical` / oxfordra.net:** merging to `main` auto-deploys the live site. Treat the merge as a production deploy (CLAUDE.md invariant 2): explicit per-deploy confirmation, then verify the served asset.
- **Exit codes are evidence only when unpiped.** Run gates as `cmd > "<scratchpad>/out.txt" 2>&1; echo "EXIT: $?"`, then grep the file. Never cite a result from `| tail`/`| grep`/`| head` (memory `rules.md` section 26). Prefer a tool's last-line `RESULT_JSON` when it prints one.
- **Report a push or merge as done only after verifying it** (`git log origin/<branch> -1`, `gh pr view --json state,mergedAt`). A hook or gate that blocked it is reported as blocked.
- Never guess Notion page ids or other external ids; look them up.

## Gate order
Stop at the first hard failure and report it; do not skip ahead.

1. **State.** `gh pr view <n> --json state,isDraft,mergeable,mergeStateStatus,baseRefName,headRefName,headRefOid,statusCheckRollup,commits`. Not OPEN, draft, or CONFLICTING: stop.
2. **Stack / base.** If the base is another feature branch (stacked chain), the parent must merge first; after it lands, retarget or rebase before this one. Never merge a child into a dead parent branch.
3. **Overlap.** `gh pr list --state open --json number,title,headRefName,files` and compare file sets. Flag any open PR touching the same files, and any other session's PR that already covers the change (check `list_sessions` and the active-work claims) before duplicating or merging.
4. **Freshness.** `git rev-list --left-right --count origin/<base>...origin/<head>`. Behind and conflicting: hand off to `branch-catchup`. Do not resolve conflicts inline in a shared checkout.
5. **Checks.** Classify every non-green check:
   - REAL: reproduce locally, report; do not merge.
   - KNOWN-EXTERNAL: not caused by the diff. Lighthouse CI has been red from a GitHub billing block (reported 2026-07 to 2026-10; **re-verify it is still the billing error in the job annotation before waiving**). Mention it in one line; do not try to fix it.
   - FLAKY: rerun at most twice, then treat as REAL.
   A bot status check is never a review verdict.
6. **Review.** Blast-radius paths (`hooks/**`, `settings.json`, `CLAUDE.md`, governance config, scheduled-task registries, CSP/headers, financial-constant or governor files), financial or security-gate code, or a commit message asserting verification: require a recorded `adversarial-merge-gate` pass on the current `headRefOid`. A pass on an older SHA does not count. Where the repo enforces a `Refute-Reviewed` commit trailer (oxford-command-center financial source), check every commit carries it; merge commits without the trailer fail the check, so propose a single squashed replacement PR rather than rewriting history in place.
7. **Local verify.** Run the repo's own gate in an isolated worktree at the PR head (unpiped, per the rule above). Gates contend for the same resources: run one at a time, not concurrently with other sessions' gates.
8. **Prerequisites for the post-merge check.** Before asking for the go-ahead, list what the live check needs (preview-domain reCAPTCHA registration, env vars, deploy locks, Netlify permissions, logins) and say which need Gabriel. Clear the blockers that are his before merge, not after.

## Readiness report (end of the check, always)
One table per PR: gate, result, evidence (command or `gh` field). Then one line: READY / NOT READY and, if not, the single next action. Ask for the merge go-ahead as a recommended-first multiple-choice question.

## Merge
Only after the yes: `gh pr merge <n> --squash` (or the repo's convention; check `gh repo view --json squashMergeAllowed,mergeCommitAllowed`). Never enable auto-merge unless asked. Verify with `gh pr view <n> --json state,mergedAt,mergeCommit`.

## Post-merge verification (yours, not Gabriel's)
Run the documented live check yourself: hit the preview/production URL, submit the test form, run the probe, fetch the served asset and compare it to the built one. Do not hand manual testing back to Gabriel. If a blocker only he can clear remains, say exactly which and what you verified without it. State evidence; do not write "verified" for a step you did not run.

## Cleanup
Remove the PR's worktree and local branch only after the merge is confirmed and the worktree is clean (`git status --short` empty, nothing unpushed). Per CLAUDE.md invariant 6 nothing is deleted outright: unmerged or dirty worktrees are left in place and listed. For a stacked chain, repeat from gate 2 for the next PR.

## Batch (two or more PRs)
Order by dependency (parents first), run gates 1-6 for all up front, then one consolidated report, then merge one at a time with a re-check of gate 1 and 4 between merges. Final table: merged / blocked (reason) / needs Gabriel.
