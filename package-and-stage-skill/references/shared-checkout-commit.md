# Step 1 — commit by pathspec, claim, contested-file detail

Moved verbatim from `SKILL.md` (v1.36 core/reference split, no rule changed). `SKILL.md` keeps each rule's headline as a stub; this file holds the full wording. Read the relevant section BEFORE acting.

## Detail (was SKILL.md step 1 lines 62–74)

   **Commit by pathspec, never bare — the shared-index race (v1.25).** `ora-skills` is a shared checkout and **the git index is shared state between every concurrent session.** A bare `git commit -m "…"` commits whatever is in the index at that instant, so another session's `git add` landing between your `git status` and your `git commit` rides into your commit under your message. Always name the paths:

   ```
   git commit -m "<msg>" -- <skill>/SKILL.md <skill>/references/…
   ```

   A pathspec-limited commit ignores the rest of the index and is the only form safe in this repo. Corollaries: (a) `git status` is a **snapshot, not a lock** — re-check `git diff --cached --name-only` immediately before committing and confirm it contains only your paths; (b) if it does not, do NOT `git reset` the extra paths away — that is another session's live WIP; commit by pathspec and leave it untouched.

   **Verify after committing, always:** `git show --stat --oneline HEAD` must list only your files. If it lists more, the sweep already happened — `git reset --soft HEAD~1`, `git restore --staged` the foreign paths, and recommit by pathspec. **Concurrency is the mechanism, not the pre-commit hook** (`tools/hooks/pre-commit` contains no `git add`; do not "fix" it). Incident and the wrong-fix near-miss: `references/incident-history.md` § Shared-index race.

   **Claim before you edit, when the session will make more than one commit (v1.26).** Pathspec makes each commit safe, not two sessions editing the same `SKILL.md` minutes apart. On the Code surface, claim each target skill dir via `~/.claude/hooks/lib/claim_work.py` before the first edit of a multi-commit session; release at hand-off. From Cowork with no bridge the claim is unreachable — say so in the hand-off rather than implying serialization. A claim is a visible declaration, not a lock. Why nothing routes there by default: `references/incident-history.md` § Claim before edit.

   **When the contested file is the one you are editing.** If `git status` shows the target skill's own `SKILL.md` staged or modified by another session, STOP and report rather than editing — that is an in-flight doctrine batch, and an edit now races a version bump you cannot see. Route to `dirty-tree-triage` (attribution + two-pass mtime settle) and `isolated-commit` (claim, stage, push). Contested WIP is reported, never force-resolved.
