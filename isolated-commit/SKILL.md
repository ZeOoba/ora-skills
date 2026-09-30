---
name: isolated-commit
description: Use when landing your own reviewed, ready-to-commit change in a shared ORA git checkout (~/.claude, ora-skills, website-canonical, oxford-command-center) that other Claude Code sessions may be concurrently editing — claiming/staging/pushing a change you just finished writing, not triaging someone else's ambient dirty files.
license: ORA Internal
---

# Isolated Commit

## Overview

One command for landing a change you just finished writing in a shared ORA checkout — claim, pathspec-scoped stage+verify, an independent review pass, commit, push with gate-flake-vs-regression triage, then PR. Complements `dirty-tree-triage` (which triages OTHER sessions' ambient dirty files with no claim on their content) — this is for YOUR OWN finished work.

## When to Use

- You've written and tested a change in `~/.claude`, `ora-skills`, `website-canonical`, or `oxford-command-center` and need to land it.
- NOT for cleaning up a pile of pre-existing uncommitted files you didn't write — use `dirty-tree-triage` instead.
- **Mixed ownership: you are about to edit, or already edited, a file another session wrote and never committed.** It is untracked on every branch, and another session's `touched-files.txt` lists it. This is not purely your own work, so apply "Foreign untracked files" below BEFORE your first edit. If you already edited without a snapshot, say so to the user and review the whole file as if it were all new, since your delta can no longer be separated.
- NOT a substitute for the mandatory Fable/Opus independent review gate on anything `eos-review-gate.py` gates (path classes listed in step 4) — this skill's own review step (4) is the SAME requirement generalized to repos/files that gate doesn't cover.

## Workflow

1. **Claim.** `python hooks/lib/claim_work.py claim <slug> "<what/why>" --paths <target files>` (repo-appropriate slug; `ora-skills` additionally needs `git log --oneline -1` + `git status` per its own single-writer rule). Absent/stale claim data reads as "cannot prove disjoint" — never skip this to save a round-trip.

2. **Isolate.** Blast-radius paths (`hooks/**`, `settings.json`, governor/financial constants, CLAUDE.md) go in a fresh `git worktree` off `main` — never edited live in the shared checkout. Lower-risk paths may be edited in place once step 1 confirms they're disjoint from any other session's dirty set (`git status --short -- <paths>` must come back empty before you start).

3. **Stage + verify.** `git add -- <exact paths>` — never `-A`/`.`/`-a`. Then `git diff --cached --name-only` and abort if anything you didn't intend appears.

4. **Independent review.** Dispatch a review agent with NO knowledge of your reasoning — diff and repo access only — to (a) re-derive every numeric/factual claim your commit message is about to make from the actual repo state, and (b) confirm the diff matches exactly the pathspec from step 3. For anything `eos-review-gate.py` gates, this IS its mandatory pass. That covers `hooks/**`, `CLAUDE.md`, `settings.json`, `*.env*`/credentials, `confidential-terms.json`, scheduled-task registries, CSP/headers, `~/.claude` config, and financial-decision/governor code. Pin the reviewer model and re-review if the diff changes afterward; a stale verdict does not carry over an edit. For everything else, spawn the same shape of review anyway; do not skip it just because no gate enforces it mechanically.

   **4a. Record the verdict before committing (gated paths).** The gate blocks the commit until the verdict is recorded, even if a review already ran. Record it once, in the same session that will run the commit (artifacts are stored per session), from the root of the checkout or worktree you will commit from, with the exact step-5 invocation as `--cmd`:
   `python "$HOME/.claude/hooks/eos-review-gate.py" --record --verdict approved --model <pinned-model-id> --notes-file <scratch-notes> --cmd "git commit -F <message-file> -- <paths>"`
   - `--cmd` scopes the key to just this commit's paths. Without it, other sessions' dirty risk files in a shared checkout get scored in and the key never matches.
   - `--notes-file` keeps the prose out of the command line, where an ASCII arrow reads as a redirect and trips `config-write-guard`.
   - Run `--key` with the same `--cmd` first if you want the exact path list to hand the reviewer.
   - The artifact is keyed to content: edit after recording and you must re-review, then record the new verdict. Never re-record without re-reviewing.
   - Never mint `allow-unreviewed-commit` in place of recording a review that actually ran.

5. **Commit.** Bare `git commit -F <message-file> -- <paths>` (a message file, not `-m`/a heredoc, sidesteps quoting fragility — see rules.md §24). Every claim in the message must trace to a command you actually ran this session.

6. **Push, triage don't retry-blind.** On a pre-push gate timeout, this repo's own gates already retry once at doubled budget — that's not a flake for you to react to. On a genuine test *failure*: run that one failing test directly, outside the gate, against the unmodified base branch. Confirms pre-existing and unrelated → say so explicitly and get the user's authorization before minting any override token (never mint one un-prompted, never force-push). Confirms caused by your diff → fix it, don't override it.
   - **Pushing straight to an existing branch** (e.g. `main`, where that repo's branch policy allows a direct push): use `python "$HOME/.claude/maintenance/safe-push.py" --to <branch> --repo <checkout>` instead of a bare `git push`. It is built for the case where another session lands on that branch during the long pre-push gate, so git rejects the push (`cannot lock ref … but expected`, `fetch first`, `incorrect old value provided`). It catches up by rebase and retries a bounded number of times. It refuses instead of guessing on a dirty tree, an in-progress operation, merge or already-pushed commits in range, or a conflict. Exit 0 means the push landed and was confirmed. Any other exit is a stop-and-report: read its `RESULT_JSON` line. A race is not a gate failure, so never mint an override token for one.
   - **A new PR branch** (the step-7 path): a plain `git push -u origin <branch>` is correct. `safe-push` only targets branches that already exist on the remote.

7. **PR.** Open with a summary + test plan that cites the review verdict from step 4.

## Foreign untracked files

An untracked file that another session wrote is that session's work, even after you add to it. Committing it brings their whole file into git under your commit. This section runs before your first edit and overrides Workflow step 2's "`git status --short -- <paths>` must be empty" precondition: a foreign untracked file always shows `??`, so that precondition can never pass, and these steps take its place.

1. **Attribute with evidence, not a guess.** `git log --all --oneline -- <path>` returning empty means it was never committed anywhere. Find every session listing the path in `hooks/sessions/<id>/touched-files.txt`. Each line is `<path>\t<epoch-seconds>` (fractional), the last time that session touched it. Paths are stored lowercased with backslashes, so match case-insensitively with normalized slashes, or a grep silently misses. Those lines record touches, not authorship, and several sessions (yours included, once you edit) can list the same file. Treat the session with the EARLIEST touch as the author, and every other non-you session that lists the path as a co-owner to name alongside it. A live claim (`hooks/active-work/*.json`) on the path, or any non-you touch within the last 2h, means STOP: contact that session, or leave the file alone.
2. **Snapshot before you edit.** Copy the pristine files to your scratchpad (`cp -p`) before the first edit, so your delta can be diffed out, reviewed, or reverted on its own.
3. **Get the user's explicit in-turn authorization to commit it.** Surface the file, its author session, how long ago that session last touched it, and the size of your delta (lines against the snapshot). Use `dirty-tree-triage`'s evidence standard for the attribution. On a yes, the commit happens HERE through Workflow steps 1 and 3-7 (claim, then stage, review, commit, push, PR); there is no hand-off. Without a yes, leave the file uncommitted.
4. **Commit it honestly.** Untracked paths need `git add -- <paths>` before `git commit -F <msg> -- <paths>`, since a pathspec commit rejects a path git has never seen. The message credits the author session for the base file and describes your delta separately. The Workflow step 4 review covers the WHOLE file, not only your delta, because all of it is entering git.

## Quick Reference

| Step | Never do | Do instead |
|---|---|---|
| Stage | `git add -A` / `git add .` / `git commit -a` | `git add -- <exact paths>`, verify with `git diff --cached --name-only` |
| Review | Skip it because "it's a small diff" | Independent agent re-derives claims + checks pathspec, every time |
| Gated commit | Commit right after the review and hit the block | `eos-review-gate.py --record ... --notes-file ... --cmd "<exact commit>"` first (step 4a) |
| Gate failure | Retry blindly or override immediately | Run the failing test directly first; distinguish flake/pre-existing from real regression |
| Override token | Mint it yourself on a hunch | Only after the user's explicit in-turn authorization, one confirmed reason |
| Commit message | Inline `-m`/heredoc for anything nontrivial | A message file via `-F` |
| Another session's untracked file | Fold it into your commit silently | Attribute it, snapshot first, get the user's yes, credit the author, review the whole file |

## Common Mistakes

- Claiming a slug but not passing `--paths`, which reads as "cannot prove disjoint" and defeats the point of claiming.
- Treating a gate's own timeout-retry as evidence of a flake worth overriding — it already self-resolved; nothing to do.
- Recording an independent review verdict, then editing the files again before committing — the verdict is keyed to exact content; re-review, don't re-use.
- Recording the verdict from the wrong directory. `eos-review-gate.py --record` takes the repo from `--repo`, falling back to the current directory, and ignores the `-C` inside `--cmd`. A verdict recorded from `~/.claude` while you commit with `git -C <worktree> commit` produces a different key and the gate blocks ("none matching the current content"). `cd` into the worktree (or pass `--repo <worktree>`), record there, and commit there with plain `git commit` and the same `--cmd`; the key changes only when a reviewed file's content or the path list changes, not when the message file changes.
- Committing in an `ora-skills` worktree before merge. The post-commit hook syncs the local mirror (`~/.claude/skills/<skill>`) from the unmerged branch and records the skill in `_staging/PENDING_REIMPORT.md` without checking the branch, while the pre-commit hook (`sync_appdata_mirror.py --check-staged`) skips the AppData runtime cache (it only writes on main in the primary checkout). Expect the local mirror to carry unmerged content until the PR lands, and re-import to the claude.ai store after merge.
- Leaving a used override token in `hooks/sessions/<id>/overrides/`. A 60-minute `allow-hook-test-failure` can mask whether the next push passes the gate on its own. Move it to an archive folder once used (never delete), then push; if the gate passes without it, say so in the PR.
- Reading a red check without its annotation. A red ORA Actions check with `steps: []` and a 404 log is usually an Actions billing block, not a test failure; `gh api repos/<owner>/<repo>/check-runs/<job-id>/annotations` says which. Run the suite locally before concluding anything about the change.
- Silently swapping a review model when the pinned one is unavailable (for example a Fable monthly spend limit). The gate accepts claude-fable-5-1, claude-opus-5-5 or claude-opus-5, but governor, financial and confidential code is never-below-Fable by doctrine: ask the user before using Opus, and say in the PR that the Fable review was unavailable.
