$ErrorActionPreference = 'SilentlyContinue'
$root = 'C:\Users\Owner\AppData\Roaming\Claude'
# Search small config/cache files only; exclude session transcripts (they contain the block from this chat)
Get-ChildItem $root -File -Recurse -Depth 3 |
  Where-Object { $_.FullName -notmatch 'local-agent-mode-sessions|Cache|GPUCache|blob_storage|Code Cache|DawnCache' -and $_.Length -lt 20MB } |
  Select-String -Pattern 'VP Acquisitions at Oxford|SCHEDULER \(dual-fleet' -List |
  ForEach-Object { $_.Path }
Write-Output '=== END ==='
