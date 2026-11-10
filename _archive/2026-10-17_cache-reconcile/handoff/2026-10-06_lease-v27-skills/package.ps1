Set-Location 'C:\Users\Owner\ora-skills'
$H = '_staging\handoff\2026-10-06_lease-v27-skills'
python -c "import pathlib;p=pathlib.Path(r'$H\commitmsg.txt');b=p.read_bytes();p.write_bytes(b[3:] if b[:3]==b'\xef\xbb\xbf' else b)"
$cached = git diff --cached --name-only
if ($cached) { "INDEX NOT EMPTY - skipping amend:"; $cached } else { git commit --amend -F "$H\commitmsg.txt" --only 2>&1 | Select-Object -Last 2 }
git show --stat --oneline HEAD | Select-Object -First 2
python tools\package_skills.py "$H" lease-form-qc masterlease-jurisdiction-rebase
python tools\stage_transfer.py emit "$H"
python tools\reimport_correlate.py baseline lease-form-qc masterlease-jurisdiction-rebase
