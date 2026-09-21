$roaming = "C:\Users\Owner\AppData\Roaming\Claude\logs\main.log"
$local = "C:\Users\Owner\AppData\Local\Claude\Logs\main.log"
Write-Output ("Now: " + (Get-Date))
if (Test-Path $roaming) {
    $r = Get-Item $roaming
    Write-Output ("Roaming main.log LastWriteTime: " + $r.LastWriteTime)
} else {
    Write-Output "Roaming main.log NOT FOUND"
}
if (Test-Path $local) {
    $l = Get-Item $local
    Write-Output ("Local main.log LastWriteTime: " + $l.LastWriteTime)
} else {
    Write-Output "Local main.log NOT FOUND"
}
