$ErrorActionPreference = 'Stop'
function Get-NormalizedHash($path) {
    $raw = [System.IO.File]::ReadAllText($path)
    $norm = $raw -replace "`r`n", "`n" -replace "`r", "`n"
    $norm = ($norm -split "`n" | ForEach-Object { $_.TrimEnd() }) -join "`n"
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($norm)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $hash = $sha.ComputeHash($bytes)
    return ([BitConverter]::ToString($hash) -replace '-','')
}

$cacheRoot = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills'
$repoRoot = 'C:\Users\Owner\ora-skills'

$pairs = @(
    @{label='insurance-renewal-review/SKILL.md'; a=(Join-Path $cacheRoot 'insurance-renewal-review\SKILL.md'); b=(Join-Path $repoRoot 'insurance-renewal-review\SKILL.md')},
    @{label='register-scheduled-task/SKILL.md'; a=(Join-Path $cacheRoot 'register-scheduled-task\SKILL.md'); b=(Join-Path $repoRoot 'register-scheduled-task\SKILL.md')},
    @{label='settlement-basis-extraction/SKILL.md'; a=(Join-Path $cacheRoot 'settlement-basis-extraction\SKILL.md'); b=(Join-Path $repoRoot 'settlement-basis-extraction\SKILL.md')},
    @{label='listing-agreement-qc scripts/ora_doc_qc.py (cache) vs repo tools/ora_doc_qc.py'; a=(Join-Path $cacheRoot 'listing-agreement-qc\scripts\ora_doc_qc.py'); b=(Join-Path $repoRoot 'tools\ora_doc_qc.py')}
)

foreach ($p in $pairs) {
    Write-Output "`n===== $($p.label) ====="
    if (-not (Test-Path $p.a)) { Write-Output "MISSING: $($p.a)"; continue }
    if (-not (Test-Path $p.b)) { Write-Output "MISSING: $($p.b)"; continue }
    $ha = Get-NormalizedHash $p.a
    $hb = Get-NormalizedHash $p.b
    Write-Output "normalized cache/a: $ha"
    Write-Output "normalized repo/b : $hb"
    Write-Output "normalized match   : $($ha -eq $hb)"
}
