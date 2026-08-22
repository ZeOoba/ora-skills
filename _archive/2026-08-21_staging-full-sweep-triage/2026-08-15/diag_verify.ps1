$ErrorActionPreference = 'Continue'
Write-Output "=== locating local-agent-mode-sessions cache root ==="
Get-ChildItem -Path "$env:APPDATA" -Directory -Filter "local-agent-mode-sessions" -Recurse -Depth 3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
Get-ChildItem -Path "$env:LOCALAPPDATA" -Directory -Filter "local-agent-mode-sessions" -Recurse -Depth 3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
