Set-Location C:\Users\Owner\ora-skills
$base = "$env:APPDATA\Claude\local-agent-mode-sessions\skills-plugin"
$d = Get-ChildItem -Path $base -Recurse -Directory -Filter 'model-bulk-edit' -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $d) { Write-Output "NO CACHE DIR"; exit 1 }
Write-Output "CreationTime=$($d.CreationTime.ToString('yyyy-MM-dd HH:mm:ss'))  (v1.0 baseline was 20:41:28)"
$files = Get-ChildItem -Path $d.FullName -Recurse -File
Write-Output "files=$($files.Count)  (packaged .skill has 2 entries)"
$files | ForEach-Object { "   " + $_.FullName.Substring($d.FullName.Length+1) }
Write-Output "--- v1.1 marker in cached script ---"
$s = Join-Path $d.FullName "scripts\cached_value_lint.py"
if (Test-Path $s) {
  (Select-String -Path $s -SimpleMatch -Pattern 'read_only=True' | Measure-Object).Count.ToString() + " occurrence(s) of read_only=True"
} else { Write-Output "scripts/cached_value_lint.py MISSING FROM CACHE" }
Write-Output "--- v1.1 marker in cached SKILL.md ---"
Select-String -Path (Join-Path $d.FullName "SKILL.md") -SimpleMatch -Pattern 'v1.1 (2026-08-22' | ForEach-Object { "changelog v1.1 present at line $($_.LineNumber)" }
Write-Output "--- hash vs repo (EOL-normalized) ---"
python -c "import hashlib,io;n=lambda p:hashlib.sha256(io.open(p,'rb').read().replace(b'\r\n',b'\n')).hexdigest();a=n(r'model-bulk-edit\scripts\cached_value_lint.py');b=n(r'$($d.FullName)\scripts\cached_value_lint.py');print('MATCH' if a==b else 'MISMATCH',a[:16])"
Write-Output "--- local main.log ---"
Get-Content "$env:LOCALAPPDATA\Claude\Logs\main.log" -Tail 400 | Select-String 'SkillsPlugin' | Select-Object -Last 6 | ForEach-Object { $_.Line }
