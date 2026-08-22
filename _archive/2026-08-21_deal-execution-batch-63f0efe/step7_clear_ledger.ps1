Set-Location "C:\Users\Owner\ora-skills"
$skills = @("deal-execution","document-assembly","estoppel-request-generation","lease-abstraction-pipeline","legal-intelligence","package-and-stage-skill")
foreach ($s in $skills) {
    Write-Output "-- clear $s --"
    python tools\pending_reimport.py clear $s
}
Write-Output ""
Write-Output "=== post-clear ledger list ==="
python tools\pending_reimport.py list
