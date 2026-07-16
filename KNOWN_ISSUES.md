# Known Issues — Cowork surface

Undocumented-until-now defects hit while editing this repo from a Cowork session (2026-07-12). Not ORA business issues — these are Cowork-platform/tooling defects. Add to as discovered; keep dateless entries tombstone-free per the standing doctrine (move stale ones to /archive/ rather than deleting).

## Bridged-mount git lock

Cowork's Linux sandbox reaches this repo through a Windows-host↔sandbox folder bridge. `.git\index.lock` can exist in a state where the sandbox owns the file (full rwx) but cannot unlink or overwrite it — `rm -f` returns "Operation not permitted," and `git checkout`/`add`/`commit` then fail with "File exists." Git *read* operations (status, diff, log) work fine through the bridge; only operations requiring atomic lock acquisition fail. Not a real competing git process — a bridge limitation.

**Workaround:** don't attempt git write operations against this repo from a Cowork sandbox. Use a Code-surface session (native filesystem access) for any `git add`/`commit`/`checkout` here. Cowork can still `Read`/`Write`/`Edit` files directly (those succeeded); only the git-level lock is affected.

## Outputs-path Write access revoked after mounting an additional folder

In a Cowork session, `Write` to the default scratchpad outputs path succeeded twice early in the session. After later calling `request_cowork_directory` to mount an additional folder (this repo), a subsequent `Write` to the *same, unchanged* outputs path failed: "is outside this session's connected folders." Mounting an additional folder should be additive to the connected-folder list, not revoke access to the default scratchpad.

**Workaround:** if you need both the default outputs scratchpad and a project folder in one Cowork session, mount the project folder first, before any Write calls, or expect to re-verify/re-request outputs access after mounting. If Write to outputs fails post-mount, don't retry blind — assume the connected-folder list changed underneath and route the file elsewhere (or present content inline in chat instead of as a file).

## Desktop Commander `start_process` silently drops leading `$variable=` assignments

Hit 2026-07-14 verifying the acquisition-underwriting v3.9 reinstall. A PowerShell command string passed to Desktop Commander's `start_process` containing `$cache='...'; ... $cache\daily-brief\SKILL.md` came back with the `$cache=` assignment token stripped entirely — PowerShell received a bare `='...'` and errored "not recognized as the name of a cmdlet," and later references to `$cache` inside double-quoted paths resolved to empty string (`\SKILL.md` instead of `C:\...\skills\daily-brief\SKILL.md`). This reproduced across a `foreach ($s in ...)` loop too — `$s` vanished the same way, breaking the loop variable. Read-only commands with no `$name=` assignment (plain `fc.exe /A 'path1' 'path2'`) are unaffected.

**Workaround:** don't rely on PowerShell variable assignment inside a single `start_process` command string for multi-path comparisons. Either (a) write one fully-literal command per file pair (no `$var=`, no `foreach`), issued as separate `start_process` calls, or (b) if a loop is unavoidable, use `cmd.exe /c` with `%var%`-style substitution instead of PowerShell `$var`. Verified working: four separate literal `fc.exe /A 'repo\path' 'cache\path'` calls, one per skill.

## Concurrent-writer collisions (two live sessions committing to ora-skills at once)

Hit three times on 2026-07-16 within the same ~40-minute window: (1) a PR #19 squash-merge landed on origin/main while a local session held unpushed commits and a feature branch, which the remote actor then deleted; (2) another actor's WIP sat *staged* in the index and was swept into an unrelated commit by a second session (caught by `git show --stat`, split via soft reset); (3) a push race — the backlog this session meant to push was pushed by the other actor between this session's `fetch` and its `push` ("Everything up-to-date"). None corrupted anything, but each cost a full verification pass to untangle who-did-what.

**Workaround (pre-commit habit, applies regardless of ownership policy):** before any commit batch against this repo, run `git fetch origin` + `git status -sb` and inspect the staged index (`git diff --cached --stat`) — never `git add` broad globs or `git commit -a` when another session may be active; stage explicit paths only. Split any commit whose `--stat` shows files you didn't touch. If a fixed writer-ownership rule is designated for a working session, record it here and in `memory/rules.md`.
