Set-Location 'C:\Users\Owner\ora-skills'
python tools\reimport_correlate.py postclick lease-form-qc --version 2.9 --no-append 2>&1 | Select-Object -Last 15
python tools\reimport_correlate.py postclick masterlease-jurisdiction-rebase --version 1.8 --no-append 2>&1 | Select-Object -Last 15
$c = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills'
"--- content markers"
(Select-String -Path "$c\lease-form-qc\scripts\lease_qc.py" -Pattern '"F21"' -Quiet)
(Select-String -Path "$c\lease-form-qc\SKILL.md" -Pattern 'v2.9' -Quiet)
if (Test-Path "$c\masterlease-jurisdiction-rebase") {
  (Select-String -Path "$c\masterlease-jurisdiction-rebase\scripts\rebase.py" -Pattern 'def build_rules_home' -Quiet)
  (Test-Path "$c\masterlease-jurisdiction-rebase\scripts\fixtures\ORA_MasterLease_ShallowBayIndustrial_v2.7_TEMPLATE.docx")
  Get-ChildItem -Recurse -File "$c\masterlease-jurisdiction-rebase" | Select-Object Name, CreationTime
} else { "mjr cache dir NOT at expected path" }
Get-Item "$c\lease-form-qc" | Select-Object Name, CreationTime
python tools\verify_installed_cache.py lease-form-qc masterlease-jurisdiction-rebase 2>&1 | Select-Object -Last 10
