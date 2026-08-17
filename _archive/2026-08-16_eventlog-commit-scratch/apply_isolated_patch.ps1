$scratch = "C:\Users\Owner\ora-skills\_staging\2026-08-16"
Set-Location $scratch

Write-Output "=== building no-index diff ==="
git diff --no-index -- "$scratch\el_base.md" "$scratch\el_base_plus_mine.md" > "$scratch\el_isolated.patch"
Write-Output ("diff exit: " + $LASTEXITCODE)

$relpath = "projects/C--Users-Owner-OneDrive---Oxford-Capital-Partners/memory/event_log.md"
$patchContent = Get-Content -Raw "$scratch\el_isolated.patch"
$patchContent = $patchContent -replace [regex]::Escape("a/$scratch\el_base.md".Replace('\','/')), "a/$relpath"
$patchContent = $patchContent -replace [regex]::Escape("b/$scratch\el_base_plus_mine.md".Replace('\','/')), "b/$relpath"
$patchContent = $patchContent -replace [regex]::Escape("--- $scratch\el_base.md".Replace('\','/')), "--- a/$relpath"
$patchContent = $patchContent -replace [regex]::Escape("+++ $scratch\el_base_plus_mine.md".Replace('\','/')), "+++ b/$relpath"
Set-Content -Path "$scratch\el_isolated_retargeted.patch" -Value $patchContent -NoNewline

Write-Output "=== retargeted patch head ==="
Get-Content "$scratch\el_isolated_retargeted.patch" -TotalCount 10
