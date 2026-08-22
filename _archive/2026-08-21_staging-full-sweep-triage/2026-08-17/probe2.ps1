$ErrorActionPreference = 'Continue'
$paths = Get-ChildItem -Path 'C:\Users\Owner\AppData\Roaming\Claude\claude-code-sessions','C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions' -Recurse -Filter 'scheduled-tasks.json' -File -ErrorAction SilentlyContinue
foreach ($p in $paths) {
  Write-Output ("=== " + $p.FullName + "  (" + $p.Length + " bytes, mtime " + $p.LastWriteTime + ")")
  $j = Get-Content $p.FullName -Raw | ConvertFrom-Json
  $tasks = if ($j.tasks) { $j.tasks } else { $j }
  foreach ($t in $tasks) {
    $id = $t.id; if (-not $id) { $id = $t.name }
    Write-Output ("  {0,-46} enabled={1,-6} cron='{2}' next={3}" -f $id, $t.enabled, $t.cronExpression, $t.nextRunAt)
  }
}
