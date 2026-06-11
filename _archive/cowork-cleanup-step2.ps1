$ErrorActionPreference = 'Continue'
$out  = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\583f08bc-0123-4111-8158-8fe3d927e350\local_e1460d82-7046-46bd-bf0d-ac5628773e96\outputs'
$cs   = 'C:\Users\Owner\ora-skills\cowork-settings'
Copy-Item "$out\20260611_ORA_CoworkGlobalSettings_v2_0.md" "$cs\versions\20260611_ORA_CoworkGlobalSettings_v2_0.md" -Force
Write-Output "--- copied md ---"
Set-Location $cs
python --version 2>&1
python "$cs\scripts\build_pdf.py" "$cs\versions\20260611_ORA_CoworkGlobalSettings_v2_0.md" --out "$cs\versions\20260611_ORA_CoworkGlobalSettings_v2_0.pdf" 2>&1
Write-Output "--- pdf exit: $LASTEXITCODE ---"
python "$cs\scripts\diff_versions.py" "$cs\versions\20260421_ORA_CoworkGlobalSettings_v1_0.md" "$cs\versions\20260611_ORA_CoworkGlobalSettings_v2_0.md" 2>&1
Write-Output "--- diff exit: $LASTEXITCODE ---"
Get-ChildItem "$cs\versions" | Select-Object Name,Length | Format-Table -AutoSize | Out-String -Width 150
