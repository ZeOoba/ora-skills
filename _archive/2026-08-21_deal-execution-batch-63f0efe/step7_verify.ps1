$root = "$env:APPDATA\Claude\local-agent-mode-sessions\skills-plugin"
$skills = @("deal-execution","document-assembly","estoppel-request-generation","lease-abstraction-pipeline","legal-intelligence","package-and-stage-skill")

Write-Output "Now: $(Get-Date)"
Write-Output ""
foreach ($s in $skills) {
    Write-Output "---- $s ----"
    $dirs = Get-ChildItem -Path $root -Recurse -Directory -Filter $s -ErrorAction SilentlyContinue
    foreach ($d in $dirs) {
        Write-Output "  Dir: $($d.FullName)"
        Write-Output "  CreationTime: $($d.CreationTime)"
        Write-Output "  LastWriteTime: $($d.LastWriteTime)"
        $files = Get-ChildItem -Path $d.FullName -Recurse -File
        Write-Output "  File count: $($files.Count)"
        foreach ($f in $files) {
            Write-Output "    $($f.FullName.Substring($d.FullName.Length+1))  CreationTime=$($f.CreationTime)"
        }
    }
}

Write-Output ""
Write-Output "=== main.log tail (re-check liveness) ==="
$mainlog = "$env:APPDATA\Claude\logs\main.log"
if (Test-Path $mainlog) {
    Write-Output "LastWriteTime: $((Get-Item $mainlog).LastWriteTime)"
    Get-Content $mainlog -Tail 15
}
