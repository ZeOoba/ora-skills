---
name: git-history-purge
description: Use when private data (deal figures, phone numbers, a notes or memory folder, a work email in commit authors, a leaked file) must be removed from the HISTORY of a GitHub repo, not just from its tip - especially a PUBLIC repo with many branches, a live local checkout that a scheduled task pushes from, or old pull requests that still show the data. Trigger on: purge history, rewrite history, scrub history, filter-repo, BFG, remove from all commits, force-push every branch, the data is still in old commits, old PRs still show it, old branches or worktrees still on pre-purge history, GitHub Support sensitive-data removal, refs/pull. NOT for removing data from the current tree only (a normal reviewed PR), NOT for rotating a leaked live secret (rotate first; a purge never un-leaks it), NOT for syncing a stale branch (branch-catchup) or triaging dirty trees (dirty-tree-triage).
license: ORA Internal
---

# Git history purge (v2.0)

Run for real on two public repos: a config repo (2026-11-20: 313 branches + 1 tag rewritten, then 2026-11-24 local cleanup to 0 changed commits) and ora-skills (2026-11-23). Every step below either ran or was learned from a failure.

**Principle: the purge changes history, never main's current tree.** Scrub the tip first with a normal reviewed PR; the purge then only rewrites what is no longer visible.

**Principle: nothing else may write to the remote between the backup and the push.** The freeze (Step 0) makes that true; `leased_push.py` (Step 4) proves it before pushing and refuses otherwise. Neither is enough alone.

**Principle: pushes are unfrozen only when no local ref can carry old history back.** Step 6 removes old history from every local checkout and proves it with an object-level count, instead of relying on a pre-push hook to stop it.

**"Old history" means: reaches a commit the purge CHANGED or DROPPED.** Not "root commit is in the backup" (a clean first commit keeps its SHA, so new branches share it) and not "no merge-base with main" (an unrelated orphan branch has none either).

**Gates (Hard Invariant 1 class, irreversible):** Gabriel's in-turn yes before the force-push, before any repo-setting change (rulesets, branch protection), before the Step 6 archive and gc, and before filing the Support request. Never change repo visibility or delete/recreate the repo to "fix" a purge; on ORA's six public repos visibility is ruled ("keep public, do not re-ask").

Scripts are stdlib Python in this skill's `scripts/` folder. Set `S` once to that folder: `~/.claude/skills/git-history-purge/scripts` when the skill is installed there, otherwise `<ora-skills checkout>/git-history-purge/scripts`. Call them as `python -I "$S/<script>"` from any directory. Each prints counts and ref names only, never values.

## Step 0 - inventory and freeze (before the backup)
- Remote: branch/tag count, fork count (`gh api repos/O/R --jq .forks_count`), PR count, default branch, branch protection and rulesets. Forks keep the data; say so.
- Local pushers: scheduled tasks (both fleets), CI that pushes, the live checkout and other sessions on it. Pause each via its supervised tool (`update_scheduled_task enabled:false`, never delete). Block the live checkout: `git config remote.origin.pushurl DISABLED-history-purge-<date>`.
- Local copies: every clone of this remote on the machine (dirty-tree-triage's clone discovery groups clones by `origin` URL), plus the live checkout's worktrees. Each needs Step 6.
- Remote lock (repo-setting change, its own yes): a temporary ruleset on all branches and tags restricting creation, update and deletion, with bypass for the repository admin role only. It stops every other account, app and bot, not pushes made with the owner's own credentials (covered by the local freeze and Step 4). Remove it after Step 5.

## Step 1 - backup outside every repo
`git clone --mirror <url> <B>/mirror.git`, `git bundle create <B>/all.bundle --all`, `git bundle verify`. `<B>` = `C:/Users/Owner/_archive/<repo>-prepurge-<date>/`. The backup holds the private data: local only, never pushed. **Never fetch into it afterwards**: it is the record of the old commits. If you need a newer copy (Step 4 exit 3), make a second backup directory.

## Step 2 - build rules from what is actually present
- Private values go in a config file OUTSIDE every repo (`~/.ora-private/purge/`). Never type them into a command, commit message, PR, chat or log. Set `"tip_ref"` if the default branch is not `refs/heads/main` (the scan refuses a missing one). Known phone numbers go in `"phone_numbers"` (10 digits): every written form is covered, including compact `6145550123`.
- Run `python -I "$S/purge_scan.py" scan <B>/mirror.git <config.json> <rules.txt>`. It checks every path a file was ever stored at, plus commit and tag messages, and writes a rule only for values present, in each written form (`123,457`, `123457`, `9,876.54`, `123,456.5`, negatives as `-123,457` or `(123,457)`). Rules are anchored so hashes, longer numbers and longer digit runs are untouched. Any rule that matches the tip is dropped (it would change the tip's tree). Report counts, never values or "masked samples".
- Read the `values skipped ... NOT searched` count: round thousands, whole numbers below `min_integer` (default 10000) and non-whole values below 1,000 are not searched, because replacing them would hit unrelated text. If one must go, remove its file by path or add an exact literal.
- A dropped rule means the value is still live at the tip: scrub it by PR first, or accept it stays.
- `literals found in file names` > 0: text rules never rename paths. Remove those paths with `--path-regex`/`--invert-paths`, or rename them.
- Work email in authors: GitHub REJECTS pushes of commits carrying a private email ("push declined due to email privacy restrictions"). Plan the mailmap now (`Name <ID+login@users.noreply.github.com> <work@email>`; ID = `gh api user --jq .id`).
- The rules rewrite text only (by content, as filter-repo decides). Binary files that hold the data (PDF, XLSX, images) must be removed by path in Step 3; find them with `git filter-repo --analyze` on a scratch copy. Verify searches binary blobs and file names too, so a missed one fails Step 3.

## Step 3 - rewrite a fresh copy, then prove it
```bash
python -I "$S/leased_push.py" prepare <B>/mirror.git <B>/work.git
git -C <B>/work.git filter-repo --force --invert-paths --path-regex '<removed-paths>' \
  --replace-text <rules.txt> --replace-message <rules.txt> --mailmap <mailmap.txt>
```
`prepare` makes a fresh copy holding only the backup's branches and tags (no `refs/pull/*`: those are never pushed, and GitHub Support handles them in Step 7) and records the backup's refs in `work.git/purge-backup-refs.txt`; it refuses an existing `work.git` (move it aside, never delete). A further filter-repo pass on the same copy is fine. filter-repo drops the `origin` remote; push by URL. Then all must hold, else stop:
- `git -C <B>/work.git rev-parse <default-branch>^{tree}` equals the backup's.
- `python -I "$S/purge_scan.py" verify <B>/work.git <config> <rules.txt>` exits 0. Besides re-applying the rules, verify searches EVERY object in the store (text blobs, binary blobs, file names in trees, commits and tags) for every configured value, phone and literal, independent of the rules. Values in the tip's files are reported as kept at the tip (accepted). A remaining value is either a scan miss (add an exact literal or a path removal, redo Step 3 from a new `prepare`) or a different number that contains it (e.g. `1,123,457`); confirm with `git -C <B>/work.git grep` locally, and proceed past a confirmed false alarm only with Gabriel's yes.
- `git -C <B>/work.git log --all --format='%ae%n%ce' | grep -ci <work-domain>` is 0.
- Ref count equals the backup's branches and tags, minus refs the rewrite deleted (Step 4 lists them).

## Step 4 - checked, leased push (after Gabriel's yes)
- Protected default branch or a ruleset that blocks force-push: loosening it is a repo-setting change (its own yes); restore it right after.
- `python -I "$S/leased_push.py" <B>/mirror.git <B>/work.git <url> --dry-run`, then without `--dry-run`. Before pushing anything it checks the chain: the backup still matches the refs recorded at `prepare`, every ref was rewritten from the backup's SHA, and the remote still has the backup's SHA. Every lease is against the backup, never against what the remote shows at push time. Batches of 40; the default branch (read from the remote's `HEAD`; `--main-ref` must agree) is pushed alone, last, and only if nothing else was rejected.
- Exit 2: bad path or URL, a copy not made with `prepare`, `STALE` (the backup changed after the copy), or a default branch that cannot be determined or disagrees. Redo Step 3 from a new `prepare`.
- Exit 3: `MOVED` refs (someone pushed after the backup, including a brand-new branch or tag); nothing was pushed. Find who (the freeze leaked). Make a NEW backup directory from the remote (Step 1), redo Steps 2-3 from it, and keep both backups for Step 6.
- Exit 4: `DELETED-BY-REWRITE` refs (every commit on them was purged, per the refs recorded at `prepare`) still hold the data on the remote; nothing was pushed. Confirm the list, then run again with `--delete-removed`.
- Exit 1: a partial push. Read each `REJECTED` / `HELD` line, fix the cause, run again as-is: refs already pushed are skipped, and anything that moved meanwhile stops the run (exit 3) instead of being overwritten. Never re-clone or `prepare` again to "refresh" after a partial push: the backup and the copy are the baseline the leases depend on.
- Hand-rolling it: `--force-with-lease=<ref>:<backup-sha>` and a refspec WITHOUT `+`. A `+<ref>:<ref>` refspec forces past its own lease. Never bare `--force`, `--prune` or `--mirror` (it hits `refs/pull/*`).

## Step 5 - verify from a fresh clone
`git clone --bare <url> <B>/verify.git` and re-run Step 3's checks there. A local check of `work.git` proves nothing about GitHub. Use `--bare`, not `--mirror`: a mirror clone also fetches GitHub's `refs/pull/*`, which still hold the old history until Step 7. Then remove the Step 0 ruleset.

## Step 6 - local copies: re-point, remove old history, prove it, then unfreeze
Do this for the live checkout and every other local clone from Step 0. Pushes stay frozen until it reaches 0.
1. `python -I "$S/local_cleanup.py" changed <B>/verify.git <B>/mirror.git [<B2>/mirror.git ...] --out <B>/old-commits.txt` records every commit the purge changed or dropped (exit 1 if none: stop and find out why).
2. Re-point the live branch onto the purged default branch with the SAME files. Pin the old tip as a SHA first, so the compare-and-swap can fail: `OLD=$(git rev-parse refs/heads/<branch>)`, `N=$(git commit-tree "$OLD^{tree}" -p <new-main> -m ...)`, `git update-ref refs/heads/<branch> "$N" "$OLD"`. A branch NAME as the old value resolves at swap time and always passes. Working files are untouched. In `~/.claude` this is a governance write: config-write token with Gabriel's quoted words.
3. `python -I "$S/local_cleanup.py" plan <repo> <B>/old-commits.txt --out <B>/cleanup-plan.json` (read-only). It checks EVERY ref in every namespace (branches, remote-tracking, tags, notes, `refs/original`, archives) and every stash entry, and every linked worktree. Old-history worktrees that are locked, or dirty with a change in the last 24 h, are skipped with the reason (their branches too). A main worktree still on old history is a BLOCKER: finish item 2 first. Report the counts and the skip list; dirty worktrees with a recent change belong to someone (dirty-tree-triage), so wait or ask.
4. After Gabriel's yes: `python -I "$S/local_cleanup.py" archive <repo> <B>/cleanup-plan.json <B>/local-cleanup-<n>`. It re-checks every item (anything changed since the plan is skipped), bundles every ref and stash entry and verifies the bundle, saves each worktree's staged-only content (index differs from both HEAD and the file), moves each worktree folder intact (ignored files included), prunes, and removes the refs in one leased transaction. Nothing is deleted. A locked worktree is included only with `--include-locked`, on its own yes.
5. `python -I "$S/local_cleanup.py" gc <repo> <B>/old-commits.txt` deletes only the reflog entries (stash included) that reach an old commit, leaving every other session's stash entries and recovery points alone (needs git 2.46+ for `git reflog list`; it refuses on older git), then runs gc with a 1-hour prune floor (objects other sessions are creating stay safe). Then `python -I "$S/local_cleanup.py" overlap <repo> <B>/old-commits.txt` must print 0 (it also counts purged files and trees when `changed` recorded them). If not: re-run `plan` (something still reaches them) or wait out the floor and re-run `gc`. If `plan` finds nothing old and `overlap` stays above 0, look at what `plan` does not list: `ORIG_HEAD`, `FETCH_HEAD` and per-worktree refs (`refs/bisect/*`, `refs/worktree/*`) in each worktree.
6. Before unfreezing, also run `python -I "$S/purge_scan.py" verify <repo> <config> <rules.txt>` on each local copy: `overlap` counts old objects by SHA, so a new commit that re-adds old content (e.g. someone kept working on an old branch) passes `overlap` but not `verify`. Both must pass.
7. Restore `pushurl`, re-enable paused tasks (re-date their `[MODEL:]` tag), confirm the first scheduled push lands, then re-run the Step 5 verify once more.

## Step 7 - what a force-push cannot reach
`refs/pull/*`, cached commit/diff views and direct SHA URLs still serve old content. Only GitHub Support can purge them (help.github.com > Support tickets, logged in as the owner; the ticket page is `/ticket/personal/0/<n>`). Use category Repositories > Repository features (NOT "Deletes", which is the delete-a-repository flow). Include: the repo URL, the PR count, the "First Changed Commit" from `<B>/work.git/filter-repo/first-changed-commits`, orphaned LFS objects (or "none"), and that no secrets are among the removed data (or which were rotated). Never paste removed data. Count progress with `git ls-remote <url> 'refs/pull/*/head'` against the backup. After Support confirms, open one old PR's "Files changed" and check a removed path is gone. Mirrors, forks and past clones cannot be recalled.

## Step 8 - record
Event-log entry via `append-event-log.py` (counts, SHAs, backup and archive paths, residuals, ticket number), with Gabriel's quoted decisions.

## Common mistakes
| Mistake | Fix |
|---|---|
| `git push --force --prune` or `--mirror` | `leased_push.py`; `--mirror` touches `refs/pull/*`, `--prune` deletes refs |
| `--force-with-lease=<ref>:<sha> +<ref>:<ref>` | The `+` overrides the lease; drop it |
| Lease read from `git ls-remote` at push time | Lease against the backup; a post-backup push otherwise vanishes |
| Fetching a moved ref into the backup | Never; make a second backup and pass both to `local_cleanup.py changed` |
| Hand-made `work.git` | `leased_push.py prepare`; push refuses a copy without its ref record |
| Re-cloning the backup after a partial push | Rerun as-is; the backup and copy are the baseline the leases depend on |
| `reflog expire --all` before gc in a shared checkout | `local_cleanup.py gc` deletes only reflog entries that reach old commits |
| Rules built from a guessed value list | `purge_scan.py scan` writes only rules for values present |
| A rule that matches the tip | Dropped by the scan; scrub the tip by PR first |
| Unfreezing with old-history refs or worktrees around | Step 6 to `overlap` = 0 first; a pre-push hook is not a substitute |
| "Old" = root commit in the backup, or no merge-base with main | "Old" = reaches a changed or dropped commit (`local_cleanup.py changed`) |
| Forgetting tags, stash entries, `refs/original`, remote-tracking refs | `plan` lists every namespace and every stash entry |
| `git worktree remove` on an old worktree | `archive` moves it intact and saves staged-only content first |
| `gc --prune=now` in a checkout other sessions use | `gc` keeps a 1-hour floor |
| Verifying from a `--mirror` clone | `--bare`: a mirror fetches `refs/pull/*` with the old history |
| `rm -rf` of a work, verify or worktree folder | Move it into `<B>/`; never delete |
| Calling it done after the push | Fresh-clone verify, local cleanup to 0, Support ticket, old-PR spot check |

## Changelog
- v2.0 (2026-11-24): redesign after the 4-round merge gate (PR 284, held; Gabriel: "Redesign PR 284 with the new fixes", "Remove it locally (Recommended)"). The pre-push guard is removed: Step 6 now removes old history from local copies (`local_cleanup.py`: changed / plan / archive / gc / overlap) and pushes are unfrozen only at 0, as done on the config repo on 2026-11-24. `leased_push.py prepare` records the backup's refs, so a stale copy can no longer turn a new branch into DELETED-BY-REWRITE; exit 3 makes a new backup instead of fetching into the old one; the default branch comes from the remote's HEAD. Verify also searches binary blobs and file names; negative figures and known phone numbers in every format are covered. Merge-gate round 1 (fresh 3-round gate, Gabriel): `archive` re-checks live worktree state (locking each worktree while it moves) and skips refs checked out anywhere; `gc` deletes only reflog entries that reach old commits (the `--all` expiry also wiped other sessions' stash entries); worktree-local refs are bundled; `prepare` copies branches and tags only; Step 6 runs `verify` on each local copy before unfreezing; the ref-count check and the no-re-clone rule from v1.0 are restored. No governor constants touched.
- v1.0 (2026-11-23): first version, from the config-repo purge of 2026-11-20, with merge-gate rounds 1-4. Full text: branch `skill/git-history-purge` (PR 284).
