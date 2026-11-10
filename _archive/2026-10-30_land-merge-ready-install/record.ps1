Set-Location 'C:\Users\Owner\ora-skills'
python tools\reimport_correlate.py postclick land --clear-ledger
"LAND_EXIT=$LASTEXITCODE"
python tools\reimport_correlate.py postclick merge-ready
"MR_EXIT=$LASTEXITCODE"
"--- ledger now ---"
python tools\pending_reimport.py list 2>&1 | Select-String -Pattern 'land|merge-ready'
