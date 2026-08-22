Set-Location 'C:\Users\Owner\.claude'
$patch = 'C:\Users\Owner\ora-skills\_staging\2026-08-15\isolated_event_log.patch'
Write-Host '--- check ---'
git apply --cached --check --whitespace=nowarn $patch
Write-Host "check exit: $LASTEXITCODE"
if ($LASTEXITCODE -eq 0) {
    git apply --cached --whitespace=nowarn $patch
    Write-Host "apply exit: $LASTEXITCODE"
}
Write-Host '--- diff --cached --stat ---'
git diff --cached --stat
