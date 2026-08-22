$ErrorActionPreference = 'Stop'
$roots = @(
  'C:\Users\Owner\AppData\Roaming\Claude\claude-code-sessions',
  'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions'
)
foreach ($r in $roots) {
  Write-Output "=== ROOT: $r"
  Get-ChildItem -Path $r -Filter '*.json' -File -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Output ("  FILE: " + $_.Name + "  " + $_.Length + " bytes  " + $_.LastWriteTime) }
  Get-ChildItem -Path $r -Directory -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Output ("  DIR : " + $_.Name) }
}
