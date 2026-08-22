$dest = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\583f08bc-0123-4111-8158-8fe3d927e350\local_40d17f7f-9aa4-46f7-9a9f-ec54d68e835a\outputs'
Write-Host "dest exists: $(Test-Path $dest)"
$src = 'C:\Users\Owner\ora-skills\_staging\2026-07-21_index-unregistered-batch'
$skills = @('acquisition-underwriting','census-acs-extract','communication-intelligence','conversation-archival','deal-comparison','document-assembly','file-reconciliation','fleet-advisory-remediation','graph-app-registration','legal-intelligence','orphaned-task-forensics','portfolio-growth','portfolio-reporting','rent-comp','tenant-intelligence')
foreach ($s in $skills) {
  $f = Join-Path $src ($s + '.skill')
  Copy-Item -Path $f -Destination $dest -Force
  Write-Host "copied $s"
}
Get-ChildItem $dest -Filter *.skill | Select-Object Name, Length
