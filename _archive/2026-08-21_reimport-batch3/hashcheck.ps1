$files = @("deal-execution.skill","debt-management.skill","document-assembly.skill","estoppel-request-generation.skill","lease-abstraction-pipeline.skill","legal-intelligence.skill")
$dir = "C:\Users\Owner\ora-skills\_staging\2026-08-21_reimport-batch3"
foreach ($f in $files) {
    $h = Get-FileHash -Algorithm SHA256 (Join-Path $dir $f)
    Write-Output "$f : $($h.Hash.ToLower())"
}
