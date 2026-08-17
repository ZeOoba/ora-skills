Set-Location "C:\Users\Owner\.claude"
Write-Output "=== pre-commit safety: diff --cached --stat ==="
git diff --cached --stat

Write-Output "=== committing (bare, no pathspec) ==="
git commit -F "C:\Users\Owner\ora-skills\_staging\2026-08-16\commit_msg.txt"
Write-Output ("commit exit: " + $LASTEXITCODE)

Write-Output "=== post-commit: git log -1 ==="
git log -1 --format="COMMIT=%H DATE=%ad SUBJECT=%s"

Write-Output "=== post-commit: git status --short (working tree should be untouched, still showing others' dirty files + event_log.md reverted-looking staged) ==="
git status --short
