$env:PYTHONIOENCODING = 'utf-8'
$cs = 'C:\Users\Owner\ora-skills\cowork-settings'
python "$cs\scripts\diff_versions.py" "$cs\versions\20260421_ORA_CoworkGlobalSettings_v1_0.md" "$cs\versions\20260611_ORA_CoworkGlobalSettings_v2_0.md" |
  Out-File -Encoding utf8 "$cs\versions\20260611_ORA_CoworkGlobalSettings_changelog_v1_0_to_v2_0.md"
Write-Output ("diff exit: " + $LASTEXITCODE)
(Get-Item "$cs\versions\20260611_ORA_CoworkGlobalSettings_changelog_v1_0_to_v2_0.md").Length
