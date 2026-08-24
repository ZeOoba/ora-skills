$out = "C:\Users\Owner\ora-skills\_staging\lint_out.txt"
$err = "C:\Users\Owner\ora-skills\_staging\lint_err.txt"
if (Get-Process python -ErrorAction SilentlyContinue) { Write-Output "STILL RUNNING" } else { Write-Output "FINISHED" }
Write-Output "--- stdout ---"
if (Test-Path $out) { Get-Content $out } else { Write-Output "(no output yet)" }
Write-Output "--- stderr ---"
if (Test-Path $err) { Get-Content $err | Select-Object -First 5 }
