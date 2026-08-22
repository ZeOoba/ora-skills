$cacheRoot = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills'
$repoRoot = 'C:\Users\Owner\ora-skills'
$h1 = (Get-FileHash -Path (Join-Path $repoRoot 'target-markets.json') -Algorithm SHA256).Hash
$h2 = (Get-FileHash -Path (Join-Path $cacheRoot 'daily-brief\target-markets.json') -Algorithm SHA256).Hash
Write-Output "target-markets.json repo:$h1 cache:$h2 match:$($h1 -eq $h2)"
$h3 = (Get-FileHash -Path (Join-Path $repoRoot 'tools\ora_doc_qc.py') -Algorithm SHA256).Hash
$h4 = (Get-FileHash -Path (Join-Path $cacheRoot 'listing-agreement-qc\scripts\ora_doc_qc.py') -Algorithm SHA256).Hash
Write-Output "ora_doc_qc.py repo:$h3 cache:$h4 match:$($h3 -eq $h4)"
