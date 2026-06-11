$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\Owner\ora-skills'
$out  = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\583f08bc-0123-4111-8158-8fe3d927e350\local_e1460d82-7046-46bd-bf0d-ac5628773e96\outputs'
$stage = Join-Path $env:TEMP ("ora-skill-stage-" + (Get-Date -Format 'yyyyMMddHHmmss'))
New-Item -ItemType Directory -Force -Path $stage | Out-Null
$skills = @('register-scheduled-task','daily-brief','legal-intelligence','automation-health-monitor','lease-abstraction-pipeline','loi-generation','lease-renewal-pipeline','exception-detection')
foreach ($s in $skills) {
  Copy-Item (Join-Path $repo $s) (Join-Path $stage $s) -Recurse -Force
  $zip = Join-Path $out "$s.zip"
  $skl = Join-Path $out "$s.skill"
  if (Test-Path $zip) { Remove-Item $zip -Force }
  if (Test-Path $skl) { Remove-Item $skl -Force }
  Compress-Archive -Path (Join-Path $stage $s) -DestinationPath $zip -Force
  Rename-Item $zip $skl
}
Get-ChildItem $out -Filter *.skill | Select-Object Name,Length | Format-Table -AutoSize | Out-String -Width 120
