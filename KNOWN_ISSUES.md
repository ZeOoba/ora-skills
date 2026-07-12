# Known Issues — Cowork surface

Undocumented-until-now defects hit while editing this repo from a Cowork session (2026-07-12). Not ORA business issues — these are Cowork-platform/tooling defects. Add to as discovered; keep dateless entries tombstone-free per the standing doctrine (move stale ones to /archive/ rather than deleting).

## Bridged-mount git lock

Cowork's Linux sandbox reaches this repo through a Windows-host↔sandbox folder bridge. `.git\index.lock` can exist in a state where the sandbox owns the file (full rwx) but cannot unlink or overwrite it — `rm -f` returns "Operation not permitted," and `git checkout`/`add`/`commit` then fail with "File exists." Git *read* operations (status, diff, log) work fine through the bridge; only operations requiring atomic lock acquisition fail. Not a real competing git process — a bridge limitation.

**Workaround:** don't attempt git write operations against this repo from a Cowork sandbox. Use a Code-surface session (native filesystem access) for any `git add`/`commit`/`checkout` here. Cowork can still `Read`/`Write`/`Edit` files directly (those succeeded); only the git-level lock is affected.

## Outputs-path Write access revoked after mounting an additional folder

In a Cowork session, `Write` to the default scratchpad outputs path succeeded twice early in the session. After later calling `request_cowork_directory` to mount an additional folder (this repo), a subsequent `Write` to the *same, unchanged* outputs path failed: "is outside this session's connected folders." Mounting an additional folder should be additive to the connected-folder list, not revoke access to the default scratchpad.

**Workaround:** if you need both the default outputs scratchpad and a project folder in one Cowork session, mount the project folder first, before any Write calls, or expect to re-verify/re-request outputs access after mounting. If Write to outputs fails post-mount, don't retry blind — assume the connected-folder list changed underneath and route the file elsewhere (or present content inline in chat instead of as a file).
