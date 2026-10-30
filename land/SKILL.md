---
name: land
description: Use when Gabriel says land this PR, merge this PR, merge-readiness, is this ready to merge, squash-merge it, or push and open a PR then merge. Thin readiness-to-merge-to-verified-pull chain for one PR in any ORA repo, with a checked-in allowlist of known external CI failures (Lighthouse billing). NOT for deciding review depth (adversarial-merge-gate), NOT for committing or opening the PR (isolated-commit), NOT for deploy post-verify (/ship).
license: ORA Internal
---

# Land (readiness, squash-merge, verified pull)

One PR, five steps. Reuses `isolated-commit` (PR creation), `adversarial-merge-gate` (review depth), `/ship` (deploy post-verify); this skill only owns the middle: is it ready, merge it, prove main moved, sync the checkout.

`$PR` = PR number, `$REPO` = OWNER/REPO. Scratch files go in the scratchpad.

## 1. Readiness
```
gh pr view $PR -R $REPO --json state,mergeable,reviewDecision,files > pr.json
gh pr checks $PR -R $REPO --json name,bucket,state,link > checks.json
python <skill-dir>/scripts/land_gate.py --repo $REPO --pr-json pr.json --checks-json checks.json
```
Exit 0 = GO, 1 = STOP, 2 = WAIT (checks pending: wait for the new head, never merge on the old one). `mergeable: UNKNOWN` stops once; re-query after a few seconds before reporting.

**Only** checks listed in `known-external-failures.json` for that repo are informational. Any other red check stops the run. Read its annotation first (`gh api repos/$REPO/check-runs/<job-id>/annotations`) before diagnosing; a zero-step red job is a billing block, not code. To add an allowlist entry you need evidence of a non-code cause and a dated `cause`; remove the entry when fixed.

The verdict also carries two flags:
- `adversarial_review_required` (blast-radius path touched): run `adversarial-merge-gate` and get a clean pass before merging. A bot check is never the review.
- `confirm_required` (deploy-on-merge repo, e.g. `ZeOoba/Website` = oxfordra.net, Invariant 2): name the repo, PR and what ships, and wait for Gabriel's in-turn yes. Approval for one PR does not carry to the next. Never enable auto-merge.

## 2. Merge
After GO and any required confirmation or review:
```
gh pr merge $PR -R $REPO --squash --delete-branch
```
If branch protection rejects it, that is a routing signal: report it, do not `--admin` or retry.

## 3. Confirm the merge
```
gh pr view $PR -R $REPO --json state,mergeCommit
```
Require `state: MERGED` and a non-null `mergeCommit.oid`. Anything else: report as not landed.

## 4. Fetch and safe pull
In the checkout for `$REPO` (`git remote -v` to match; never guess):
```
git fetch origin
git status --short
```
- Tree clean and on the default branch: `git pull --ff-only`.
- Tree dirty: do NOT stash, reset or checkout. Show `git status --short` and `git diff --stat origin/<default>...HEAD`, and ask whether to pull, work in a worktree, or leave it. Other sessions' files are often the cause.
- On another branch: report; `git fetch` already updated `origin/<default>`, which is enough to verify.

## 5. Report the verified SHA
`git rev-parse origin/<default>` (and `HEAD` if pulled). State landed only if the merge commit from step 3 is that SHA or an ancestor (`git merge-base --is-ancestor <oid> origin/<default>`). Report: PR, `mergeCommit.oid`, `origin/<default>` SHA, checkout state (pulled / skipped and why), informational checks that were red.

For deploy-on-merge repos, then run `/ship` After-step post-verify (Netlify deploy for that SHA, served asset); a merge is not a live deploy.

## Dry run
`gh pr merge` is the only mutating command. To rehearse, run step 1 and stop; the script's output is the transcript (see `tests/` and the PR description).
