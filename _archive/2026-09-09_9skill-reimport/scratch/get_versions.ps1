Set-Location C:\Users\Owner\ora-skills
$skills = @('annual-cycle','cash-position-monitor','debt-management','disposition-analysis',
            'lease-form-qc','lease-generation','lease-renewal-pipeline','parcel-data-recovery',
            'security-and-hardening')
foreach ($s in $skills) {
    $line = Select-String -Path "$s\SKILL.md" -Pattern "^v?\d+\.\d+" -SimpleMatch:$false | Select-Object -First 3
    $desc = Get-Content "$s\SKILL.md" -TotalCount 40 | Select-String "^description:"
    Write-Output "=== $s ==="
    $desc
}
