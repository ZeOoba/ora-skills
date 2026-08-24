$out = "C:\Users\Owner\ora-skills\_staging\lint_out.txt"
$err = "C:\Users\Owner\ora-skills\_staging\lint_err.txt"
foreach ($f in @($out,$err)) { if (Test-Path $f) { Remove-Item $f -Force } }
Start-Process -FilePath "powershell.exe" `
  -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File","C:\Users\Owner\ora-skills\_staging\lint_inner.ps1") `
  -RedirectStandardOutput $out -RedirectStandardError $err -NoNewWindow
Write-Output "launched"
