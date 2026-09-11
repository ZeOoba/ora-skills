Set-Location C:\Users\Owner\ora-skills
$skills = @('annual-cycle','cash-position-monitor','debt-management','disposition-analysis',
            'lease-form-qc','lease-generation','lease-renewal-pipeline','parcel-data-recovery',
            'security-and-hardening')
foreach ($s in $skills) {
    Write-Output "=== $s ==="
    git status --short -- "$s/"
    Write-Output "--- last commit ---"
    git log -1 --format="%H %ci %s" -- "$s/"
    Write-Output ""
}
