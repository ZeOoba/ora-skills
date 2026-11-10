Set-Location 'C:\Users\Owner\ora-skills'
"=== verify (no append yet) ==="
python tools\reimport_correlate.py postclick land --no-append
"LAND_VERIFY_EXIT=$LASTEXITCODE"
python tools\reimport_correlate.py postclick merge-ready --no-append
"MR_VERIFY_EXIT=$LASTEXITCODE"
"=== installed cache vs package ==="
python tools\verify_installed_cache.py land merge-ready
"CACHE_EXIT=$LASTEXITCODE"
