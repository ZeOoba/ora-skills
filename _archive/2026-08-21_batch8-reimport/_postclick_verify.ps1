Write-Output ("Now: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"))
$root = "C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills"
$targets = @("automation-health-monitor","repo-architecture-review","debt-management")
foreach ($s in $targets) {
  $p = Join-Path $root $s
  $di = Get-Item $p
  Write-Output "--- $s ---"
  Write-Output ("dir CreationTime: " + $di.CreationTime.ToString("yyyy-MM-dd HH:mm:ss.fff"))
  Get-ChildItem -Recurse -File $p | ForEach-Object {
    Write-Output ("  " + $_.FullName.Substring($p.Length+1) + "  created=" + $_.CreationTime.ToString("HH:mm:ss.fff") + "  size=" + $_.Length)
  }
}
