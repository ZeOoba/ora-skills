Set-Location 'C:\Users\Owner\ora-skills'
python -c "import sys;sys.path.insert(0,'tools');from package_skills import plugin_of;print('plugin_of lfq:',plugin_of('lease-form-qc'));print('plugin_of mjr:',plugin_of('masterlease-jurisdiction-rebase'))"
git add -- lease-form-qc/SKILL.md lease-form-qc/scripts/lease_qc.py lease-form-qc/tests/test_lease_qc.py masterlease-jurisdiction-rebase/SKILL.md masterlease-jurisdiction-rebase/config/properties.json masterlease-jurisdiction-rebase/scripts/rebase.py masterlease-jurisdiction-rebase/scripts/test_rebase.py masterlease-jurisdiction-rebase/scripts/fixtures/ORA_MasterLease_ShallowBayIndustrial_v2.7_TEMPLATE.docx
"--- cached before commit:"
git diff --cached --name-only
$msg = @"
lease-form-qc v2.9 + masterlease-jurisdiction-rebase v1.8: master lease v2.7 cycle

lease-form-qc: F19 (NOTICES (B) premises-only, HIGH), F20 (mandatory controlling rent
schedule, MED), F21 (late-signing commencement clause, MED); checks_run 57 -> 60.
Clean benchmark moves to the v2.7 master fixture; v2.6 fixture now fails exactly
F19-F21 (asserted). TestV27Standards added. 145 passed.

masterlease-jurisdiction-rebase: home_state path (build_rules_home) for OH properties
on the OH master, first user OH-MOR (384-420 Morrison Rd, parcel 010-208204); footer
fill walks every footer part (MD-COL printed [PREMISES ADDRESS] through v2.6) with
TestFooterFillAllParts; ZIPs MD-EAS 21601 / MO-RAY 64133; MD-SBY rebuilt on SDAT-verified
2203 Marvel Rd / 2205-2207 Northwood Dr; parity fixture v2.6 -> v2.7. 7 passed / 23 subtests.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019B1q7LHsDv5TTmdN1f19M1
"@
$msg | Out-File -Encoding utf8 '_staging\handoff\2026-10-06_lease-v27-skills\commitmsg.txt'
git commit -F '_staging\handoff\2026-10-06_lease-v27-skills\commitmsg.txt' -- lease-form-qc/SKILL.md lease-form-qc/scripts/lease_qc.py lease-form-qc/tests/test_lease_qc.py masterlease-jurisdiction-rebase/SKILL.md masterlease-jurisdiction-rebase/config/properties.json masterlease-jurisdiction-rebase/scripts/rebase.py masterlease-jurisdiction-rebase/scripts/test_rebase.py masterlease-jurisdiction-rebase/scripts/fixtures/ORA_MasterLease_ShallowBayIndustrial_v2.7_TEMPLATE.docx
"--- show:"
git show --stat --oneline HEAD
