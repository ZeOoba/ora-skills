$cachePath = Join-Path $env:APPDATA "Claude\local-agent-mode-sessions\skills-plugin"
Get-ChildItem -Path $cachePath -Recurse -Directory -Filter "register-scheduled-task" -ErrorAction SilentlyContinue |
    Select-Object FullName, CreationTime | Format-List
