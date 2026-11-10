Set-Location 'C:\Users\Owner\ora-skills'
python tools\reimport_correlate.py postclick lease-form-qc --version 2.9 --clear-ledger 2>&1 | Select-Object -Last 6
"exit lfq: $LASTEXITCODE"
python tools\reimport_correlate.py postclick masterlease-jurisdiction-rebase --version 1.8 --clear-ledger 2>&1 | Select-Object -Last 6
"exit mjr: $LASTEXITCODE"
python tools\pending_reimport.py list 2>&1 | Select-String -Pattern 'lease-form-qc|masterlease-jurisdiction-rebase'
"--- closing sweep"
python tools\repo_first_check.py 2>&1 | Select-Object -Last 3
python tools\frontmatter_sweep.py 2>&1 | Select-Object -Last 2
