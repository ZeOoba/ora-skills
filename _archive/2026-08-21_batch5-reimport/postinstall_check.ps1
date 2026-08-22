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
$skills = @('daily-brief','insurance-renewal-review','listing-agreement-qc','register-scheduled-task','settlement-basis-extraction')

$expectedEntries = @{
    'daily-brief' = @('references/incident-history.md','SKILL.md','target-markets.json')
    'insurance-renewal-review' = @('references/ocr-and-extraction-checklist.md','SKILL.md')
    'listing-agreement-qc' = @('references/cw-form-defect-register.md','references/deal-folder-checklist.md','references/standing-positions.md','scripts/build_excluded_prospects.py','scripts/listing_qc.py','scripts/ora_doc_qc.py','SKILL.md')
    'register-scheduled-task' = @('references/incident-history.md','SKILL.md')
    'settlement-basis-extraction' = @('references/charge-capitalization-taxonomy.md','SKILL.md')
}

foreach ($s in $skills) {
    Write-Output "`n===== $s ====="
    $cacheDir = Join-Path $cacheRoot $s
    $repoDir = Join-Path $repoRoot $s
    if (-not (Test-Path $cacheDir)) { Write-Output "CACHE DIR MISSING"; continue }
    $dirInfo = Get-Item $cacheDir
    Write-Output "Cache dir CreationTime: $($dirInfo.CreationTime)  LastWriteTime: $($dirInfo.LastWriteTime)"

    $cacheFiles = Get-ChildItem -Path $cacheDir -Recurse -File | Sort-Object FullName
    $relSet = @()
    foreach ($f in $cacheFiles) {
        $rel = $f.FullName.Substring($cacheDir.Length + 1) -replace '\\','/'
        $relSet += $rel
    }
    Write-Output "Cache file set ($($relSet.Count)): $($relSet -join ', ')"
    $expected = $expectedEntries[$s]
    $missing = $expected | Where-Object { $relSet -notcontains $_ }
    $extra = $relSet | Where-Object { $expected -notcontains $_ }
    Write-Output "Missing vs expected packaged set: $(if ($missing) {$missing -join ', '} else {'NONE'})"
    Write-Output "Extra vs expected packaged set: $(if ($extra) {$extra -join ', '} else {'NONE'})"
    Write-Output "All file creation times:"
    foreach ($f in $cacheFiles) {
        Write-Output "  $($f.Name) created:$($f.CreationTime)"
    }

    foreach ($f in $cacheFiles) {
        $rel = $f.FullName.Substring($cacheDir.Length + 1)
        $repoFile = Join-Path $repoDir $rel
        if (Test-Path $repoFile) {
            $h1 = Get-NormalizedHash $f.FullName
            $h2 = Get-NormalizedHash $repoFile
            Write-Output "  normalized-match $rel : $($h1 -eq $h2)"
        } else {
            Write-Output "  (no repo counterpart for $rel -- likely injected shared dep, checked separately)"
        }
    }
}
