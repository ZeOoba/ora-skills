$local = "$env:LOCALAPPDATA\Claude\Logs\main.log"
$roaming = "$env:APPDATA\Claude\logs\main.log"
Write-Output "Now: $(Get-Date)"
if (Test-Path $local) {
    $i = Get-Item $local
    Write-Output "LOCAL main.log LastWriteTime: $($i.LastWriteTime)"
} else { Write-Output "LOCAL main.log not found" }
if (Test-Path $roaming) {
    $i = Get-Item $roaming
    Write-Output "ROAMING main.log LastWriteTime: $($i.LastWriteTime)"
} else { Write-Output "ROAMING main.log not found" }
