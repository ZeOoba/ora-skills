Set-Location "C:\Users\Owner\.claude"
$patch = "C:\Users\Owner\ora-skills\_staging\2026-08-16\el_isolated_retargeted.patch"

Write-Output "=== git apply --cached --check ==="
git apply --cached --check $patch
Write-Output ("check exit: " + $LASTEXITCODE)

Write-Output "=== git apply --cached ==="
git apply --cached $patch
Write-Output ("apply exit: " + $LASTEXITCODE)

Write-Output "=== git diff --cached --stat ==="
git diff --cached --stat
