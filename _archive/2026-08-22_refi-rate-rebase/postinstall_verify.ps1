Set-Location C:\Users\Owner\ora-skills
$base = "$env:APPDATA\Claude\local-agent-mode-sessions\skills-plugin"
Write-Output "=== CACHE STATE (baselines: acq-uw 17:50:08, pkg-stage 17:58:05, model-bulk-edit none) ==="
foreach ($s in @('acquisition-underwriting','package-and-stage-skill','model-bulk-edit')) {
  $d = Get-ChildItem -Path $base -Recurse -Directory -Filter $s -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $d) { Write-Output "$s : NO CACHE DIR"; continue }
  $files = Get-ChildItem -Path $d.FullName -Recurse -File
  Write-Output ("{0} : CreationTime={1}  files={2}" -f $s, $d.CreationTime.ToString('yyyy-MM-dd HH:mm:ss'), $files.Count)
  $files | ForEach-Object { "      " + $_.FullName.Substring($d.FullName.Length+1) }
}
Write-Output "=== VERSION TOKENS IN CACHE ==="
foreach ($s in @('acquisition-underwriting','package-and-stage-skill','model-bulk-edit')) {
  $d = Get-ChildItem -Path $base -Recurse -Directory -Filter $s -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($d) {
    $f = Join-Path $d.FullName "SKILL.md"
    if (Test-Path $f) { (Select-String -Path $f -Pattern 'Oxford Realty Advisors \(v4\.\d+|^# model-bulk-edit|v1\.26' | Select-Object -First 1).Line }
  }
}
Write-Output "=== LOCAL main.log recent SkillsPlugin ==="
$loc = "$env:LOCALAPPDATA\Claude\Logs\main.log"
if (Test-Path $loc) { Get-Content $loc -Tail 600 | Select-String 'SkillsPlugin' | Select-Object -Last 8 | ForEach-Object { $_.Line } }
Write-Output "=== LINT SWEEP ==="
if (Get-Process python -ErrorAction SilentlyContinue) { Write-Output "STILL RUNNING" } else { Write-Output "FINISHED" }
Get-Content _staging\lint_out.txt -ErrorAction SilentlyContinue | Select-Object -Last 25
