$ErrorActionPreference = 'Stop'
$cacheDir = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills\acquisition-underwriting'
$cacheSkillMd = Join-Path $cacheDir 'SKILL.md'
$cacheTM = Join-Path $cacheDir 'target-markets.json'

Write-Output ('CACHE_DIR_EXISTS: ' + (Test-Path $cacheDir))
Write-Output 'CACHE_DIR_CONTENTS:'
Get-ChildItem $cacheDir -Force | ForEach-Object { Write-Output ('  ' + $_.Name + ' | ' + $_.Length + ' bytes | ' + $_.LastWriteTime) }

function NormHash($p) {
    $raw = Get-Content -Raw $p
    $norm = $raw -replace "`r`n", "`n"
    $norm = $norm.TrimEnd()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($norm)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $hash = $sha.ComputeHash($bytes)
    return [BitConverter]::ToString($hash) -replace '-', ''
}

Write-Output ('CACHE_SKILLMD_RAW:  ' + (Get-FileHash $cacheSkillMd -Algorithm SHA256).Hash)
Write-Output ('CACHE_SKILLMD_NORM: ' + (NormHash $cacheSkillMd))
Write-Output ('CACHE_TM_RAW:  ' + (Get-FileHash $cacheTM -Algorithm SHA256).Hash)
Write-Output ('CACHE_TM_NORM: ' + (NormHash $cacheTM))

Write-Output 'CACHE_FRONTMATTER_TITLE:'
Select-String -Path $cacheSkillMd -Pattern '^# Acquisition Underwriting' | Select-Object -First 1 Line

Write-Output 'CACHE_STAGE_2_8_GREP:'
Select-String -Path $cacheSkillMd -Pattern 'STAGE 2\.8|FORG v1\.0' | Select-Object -First 5 LineNumber, Line

Write-Output 'CACHE_V4_3_CHECK (should be empty if upgraded):'
Select-String -Path $cacheSkillMd -Pattern 'v4\.3' | Select-Object -First 5 LineNumber, Line
