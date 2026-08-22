$skills = @('daily-brief','ora-setup-audit','register-scheduled-task')
$root = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin'
foreach ($s in $skills) {
    Write-Output "=== $s ==="
    Get-ChildItem -Path $root -Recurse -Directory -Filter $s | ForEach-Object { Write-Output $_.FullName }
}
