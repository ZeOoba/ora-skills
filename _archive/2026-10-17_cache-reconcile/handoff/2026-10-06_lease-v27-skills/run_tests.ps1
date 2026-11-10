Set-Location 'C:\Users\Owner\ora-skills'
git status --short -- lease-form-qc/ masterlease-jurisdiction-rebase/
python -m pytest -q lease-form-qc/tests/test_lease_qc.py 2>&1 | Select-Object -Last 6
python -m pytest -q masterlease-jurisdiction-rebase/scripts/test_rebase.py 2>&1 | Select-Object -Last 3
python tools/description_budget.py lease-form-qc masterlease-jurisdiction-rebase
python tools/script_resource_lint.py lease-form-qc
python tools/script_resource_lint.py masterlease-jurisdiction-rebase
