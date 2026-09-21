$ErrorActionPreference = "Continue"
Set-Location "C:\Users\Owner\ora-skills"

Write-Output "=== plugin_of checks ==="
foreach ($s in @("daily-brief","pma-qc","vendor-management")) {
    $cmd = "import sys;sys.path.insert(0,'tools');from package_skills import plugin_of;print('$s ->', plugin_of('$s'))"
    python -c $cmd
}

Write-Output "=== pending_reimport candidates ==="
python tools\pending_reimport.py candidates

Write-Output "=== pending_reimport shared-deps ==="
python tools\pending_reimport.py shared-deps
