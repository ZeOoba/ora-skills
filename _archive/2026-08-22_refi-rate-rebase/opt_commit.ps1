Set-Location C:\Users\Owner\ora-skills
Write-Output "=== FRONTMATTER GATE ==="
python _staging\fm_gate.py package-and-stage-skill
Write-Output "GATE EXIT: $LASTEXITCODE"
if ($LASTEXITCODE -ne 0) { Write-Output "ABORT"; exit 1 }
Write-Output "=== INDEX IMMEDIATELY PRE-COMMIT (snapshot, not a lock) ==="
git diff --cached --name-only
Write-Output "=== COMMIT BY PATHSPEC ==="
git commit -m "docs(package-and-stage-skill): v1.25 - commit by pathspec, the shared-index race" -- package-and-stage-skill/SKILL.md
Write-Output "COMMIT EXIT: $LASTEXITCODE"
Write-Output "=== POST-COMMIT VERIFY (must list ONLY my file) ==="
git show --stat --oneline HEAD
Write-Output "=== TREE AFTER (foreign staged work must be untouched) ==="
git status -sb
