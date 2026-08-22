Set-Location C:\Users\Owner\ora-skills
$out = "C:\Users\Owner\ora-skills\_staging\2026-08-14"
New-Item -ItemType Directory -Force $out | Out-Null
Write-Output "=== PACKAGER ==="
python tools\package_skills.py $out lease-addendum
Write-Output "EXIT: $LASTEXITCODE"
Write-Output "=== ARTIFACT ==="
$f = Join-Path $out "lease-addendum.skill"
if (Test-Path $f) {
  (Get-Item $f).Length
  (Get-FileHash $f -Algorithm SHA256).Hash
  Write-Output "=== ZIP ENTRIES ==="
  python -c "import zipfile;[print(i.filename, i.file_size) for i in zipfile.ZipFile(r'$($f)').infolist()]"
} else { Write-Output "MISSING ARTIFACT" }
Write-Output "=== DONE ==="
