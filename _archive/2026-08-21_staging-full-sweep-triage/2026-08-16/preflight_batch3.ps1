Set-Location "C:\Users\Owner\ora-skills"
$skills = @("insurance-renewal-review","package-and-stage-skill","register-scheduled-task")

Write-Output "=== CANDIDATES (ledger UNION fresh sweep) ==="
python tools\pending_reimport.py candidates

foreach ($s in $skills) {
    Write-Output "`n=== $s : plugin_of ==="
    python -c "import sys; sys.path.insert(0,'tools'); from package_skills import plugin_of; print('PLUGIN_OF_RESULT:', plugin_of('$s'))"

    Write-Output "=== $s : git status --short ==="
    git status --short -- "$s/"

    Write-Output "=== $s : git log -1 ==="
    git log -1 --format="COMMIT=%H DATE=%ad SUBJECT=%s" -- "$s/"

    Write-Output "=== $s : repo dir listing ==="
    Get-ChildItem -Path "$s" -Recurse -File | ForEach-Object { Write-Output ("REPOFILE: " + $_.FullName.Substring((Get-Item $s).FullName.Length+1)) }
}
