$mainlog = "$env:APPDATA\Claude\logs\main.log"
Write-Output "main.log path: $mainlog"
if (Test-Path $mainlog) {
    $fi = Get-Item $mainlog
    Write-Output "main.log LastWriteTime: $($fi.LastWriteTime)"
    Write-Output "Now: $(Get-Date)"
    Write-Output ""
    Write-Output "=== last 40 lines of main.log ==="
    Get-Content $mainlog -Tail 40
} else {
    Write-Output "main.log NOT FOUND at that path"
}
