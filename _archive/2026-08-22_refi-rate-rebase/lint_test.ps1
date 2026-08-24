$script = "C:\Users\Owner\ora-skills\model-bulk-edit\scripts\cached_value_lint.py"
$root   = "C:\Users\Owner\OneDrive - Oxford Capital Partners\Business"
$args   = '"{0}" "{1}" --quiet' -f $script, $root      # quote BOTH -- spaces split otherwise
$job = Start-Process -FilePath "python" -ArgumentList $args `
  -RedirectStandardOutput "C:\Users\Owner\ora-skills\_staging\lint2_out.txt" `
  -RedirectStandardError  "C:\Users\Owner\ora-skills\_staging\lint2_err.txt" -NoNewWindow -PassThru
$peak = 0
while (-not $job.HasExited) {
  Start-Sleep -Milliseconds 700
  try { $job.Refresh(); $m = [math]::Round($job.WorkingSet64/1MB); if ($m -gt $peak) { $peak = $m } } catch { break }
  if ($peak -gt 1500) { Write-Output "ABORTED - exceeded 1500 MB guard"; $job.Kill(); break }
}
Write-Output "peak working set: $peak MB"
Get-Content "C:\Users\Owner\ora-skills\_staging\lint2_out.txt" -ErrorAction SilentlyContinue | Select-Object -Last 30
Get-Content "C:\Users\Owner\ora-skills\_staging\lint2_err.txt" -ErrorAction SilentlyContinue | Select-Object -First 5
