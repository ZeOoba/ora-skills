$targets = @('annual-cycle','cash-position-monitor','security-and-hardening','lease-generation')
$root = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin'
Get-ChildItem -Path $root -Recurse -Directory -ErrorAction SilentlyContinue |
    Where-Object { $targets -contains $_.Name } |
    ForEach-Object { Write-Output "$($_.Name) => $($_.FullName)  Created=$($_.CreationTime)" }
