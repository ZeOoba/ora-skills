Set-Location C:\Users\Owner\ora-skills
$skills = @('document-assembly','exception-detection','package-and-stage-skill')
foreach ($s in $skills) {
  Write-Output "=== SKILL: $s ==="
  Write-Output ("plugin_of: " + (python -c "import sys;sys.path.insert(0,'tools');from package_skills import plugin_of;print(plugin_of('$s'))"))
  Write-Output "git-dirty:"
  git status --short -- "$s/"
}
$out = "C:\Users\Owner\ora-skills\_staging\2026-08-14"
New-Item -ItemType Directory -Force $out | Out-Null
Write-Output "=== PACKAGER ==="
python tools\package_skills.py $out document-assembly exception-detection package-and-stage-skill
Write-Output "EXIT: $LASTEXITCODE"
Write-Output "=== HASHES ==="
foreach ($s in $skills) {
  $f = Join-Path $out "$s.skill"
  Write-Output ("$s " + (Get-Item $f).Length + " " + (Get-FileHash $f -Algorithm SHA256).Hash)
}
Write-Output "=== COMBINED B64 ==="
$sb = [Text.StringBuilder]::new()
foreach ($s in $skills) {
  $f = Join-Path $out "$s.skill"
  [void]$sb.AppendLine("=====BEGIN $s=====")
  $b = [Convert]::ToBase64String([IO.File]::ReadAllBytes($f))
  for ($i = 0; $i -lt $b.Length; $i += 320) {
    [void]$sb.AppendLine($b.Substring($i, [Math]::Min(320, $b.Length - $i)))
  }
  [void]$sb.AppendLine("=====END $s=====")
}
[IO.File]::WriteAllText((Join-Path $out "batch3.b64"), $sb.ToString())
Write-Output ("B64_BYTES: " + (Get-Item (Join-Path $out "batch3.b64")).Length)
Write-Output "DONE"
