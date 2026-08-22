$src = "C:\Users\Owner\ora-skills\_staging\2026-08-22_reimport-batch6\package-and-stage-skill.skill"
$dst = "C:\Users\Owner\ora-skills\_staging\2026-08-22_reimport-batch6\pkgstage_b64.txt"
$bytes = [IO.File]::ReadAllBytes($src)
[Convert]::ToBase64String($bytes) | Out-File -FilePath $dst -Encoding ascii -NoNewline
$hash = (Get-FileHash -Algorithm SHA256 -Path $src).Hash
Write-Output "SHA256: $hash"
Write-Output "Bytes: $($bytes.Length)"
