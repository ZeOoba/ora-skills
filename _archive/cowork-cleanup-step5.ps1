$ErrorActionPreference = 'Continue'
$cs  = 'C:\Users\Owner\ora-skills\cowork-settings\versions'
$out = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\583f08bc-0123-4111-8158-8fe3d927e350\local_e1460d82-7046-46bd-bf0d-ac5628773e96\outputs'
Copy-Item "$cs\20260611_ORA_CoworkGlobalSettings_v2_0.pdf" $out -Force
Copy-Item "$cs\20260611_ORA_CoworkGlobalSettings_changelog_v1_0_to_v2_0.md" $out -Force
Set-Location 'C:\Users\Owner\ora-skills'
git add -A
git commit -m "Cowork-surface cleanup 2026-06-11: settings v2.0 (ratified routing/COM-only/dual-fleet/3-schemas/VP title; 5 dead skill refs stripped); register-scheduled-task v2.0 (MCP-only, splice prohibited); daily-brief v2.5 + legal-intelligence v1.1 + lease-abstraction v2.1 + automation-health-monitor v1.1 + loi-generation Composio purge; monthly-close repo sync to v2.0"
git log --oneline -1
Write-Output '=== DONE ==='
