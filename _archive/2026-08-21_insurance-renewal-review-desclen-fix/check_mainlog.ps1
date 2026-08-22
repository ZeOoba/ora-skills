$logPath = "$env:APPDATA\Claude\logs\main.log"
if (Test-Path $logPath) {
    $fi = Get-Item $logPath
    Write-Output "MAIN_LOG_LASTWRITE: $($fi.LastWriteTime)"
    Write-Output "NOW: $(Get-Date)"
    Write-Output "---TAIL---"
    Get-Content $logPath -Tail 20
    Write-Output "---SKILLSPLUGIN GREP---"
    Select-String -Path $logPath -Pattern "insurance-renewal-review" | Select-Object -Last 10
} else {
    Write-Output "MAIN_LOG_NOT_FOUND"
}
