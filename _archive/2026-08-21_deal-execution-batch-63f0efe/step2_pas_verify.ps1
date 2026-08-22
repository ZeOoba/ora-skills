Set-Location "C:\Users\Owner\ora-skills"
Write-Output "=== git show --stat for package-and-stage-skill in 63f0efe ==="
git show --stat 63f0efe -- package-and-stage-skill/

Write-Output ""
Write-Output "=== git diff (previous commit -> 63f0efe) for package-and-stage-skill/SKILL.md ==="
git diff 63f0efe^ 63f0efe -- package-and-stage-skill/SKILL.md | Select-Object -First 60

Write-Output ""
Write-Output "=== repo file hash ==="
Get-FileHash "package-and-stage-skill\SKILL.md" -Algorithm SHA256

Write-Output ""
Write-Output "=== cache file hash ==="
$cache = "$env:APPDATA\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills\package-and-stage-skill\SKILL.md"
Get-FileHash $cache -Algorithm SHA256

Write-Output ""
Write-Output "=== raw byte size compare ==="
Write-Output "repo size: $((Get-Item 'package-and-stage-skill\SKILL.md').Length)"
Write-Output "cache size: $((Get-Item $cache).Length)"
