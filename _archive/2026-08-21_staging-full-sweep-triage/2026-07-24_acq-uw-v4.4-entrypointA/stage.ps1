$ErrorActionPreference = 'Stop'
$src = 'C:\Users\Owner\ora-skills\_staging\2026-07-24_acq-uw-v4.4-entrypointA\acquisition-underwriting.skill'
$dst = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\583f08bc-0123-4111-8158-8fe3d927e350\local_1e08e32a-602d-4f90-8aec-9ab051d736b4\outputs\acquisition-underwriting.skill'

Copy-Item $src $dst -Force
Write-Output ('COPIED_EXISTS: ' + (Test-Path $dst))
Write-Output ('COPIED_SHA256: ' + (Get-FileHash $dst -Algorithm SHA256).Hash)

Remove-Item 'C:\Users\Owner\ora-skills\_staging\2026-07-24_acq-uw-v4.4-entrypointA\verify.ps1' -Force -ErrorAction SilentlyContinue
Remove-Item 'C:\Users\Owner\ora-skills\_staging\2026-07-24_acq-uw-v4.4-entrypointA\verify2.ps1' -Force -ErrorAction SilentlyContinue
Remove-Item 'C:\Users\Owner\ora-skills\_staging\_verify_extract' -Recurse -Force -ErrorAction SilentlyContinue
Write-Output 'CLEANUP_DONE'
