$root = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills'
$skills = @('acquisition-underwriting','census-acs-extract','communication-intelligence','conversation-archival','deal-comparison','document-assembly','file-reconciliation','fleet-advisory-remediation','graph-app-registration','legal-intelligence','orphaned-task-forensics','portfolio-growth','portfolio-reporting','rent-comp','tenant-intelligence')
foreach ($s in $skills) {
  $p = Join-Path $root ($s + '\SKILL.md')
  if (Test-Path $p) {
    $i = Get-Item $p
    Write-Host ($s + ' : ' + $i.LastWriteTime)
  } else {
    Write-Host ($s + ' : MISSING')
  }
}
