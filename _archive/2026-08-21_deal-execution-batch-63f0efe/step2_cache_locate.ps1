$root = "$env:APPDATA\Claude\local-agent-mode-sessions\skills-plugin"
Write-Output "Cache root: $root"
if (-not (Test-Path $root)) { Write-Output "ROOT NOT FOUND"; exit }

$skills = @("deal-execution","document-assembly","estoppel-request-generation","lease-abstraction-pipeline","legal-intelligence","package-and-stage-skill")

foreach ($s in $skills) {
    Write-Output "---- $s ----"
    $dirs = Get-ChildItem -Path $root -Recurse -Directory -Filter $s -ErrorAction SilentlyContinue
    if ($dirs) {
        foreach ($d in $dirs) {
            Write-Output "FOUND: $($d.FullName)"
            Write-Output "  CreationTime: $($d.CreationTime)"
            Write-Output "  LastWriteTime: $($d.LastWriteTime)"
        }
    } else {
        Write-Output "NOT FOUND in cache"
    }
}
