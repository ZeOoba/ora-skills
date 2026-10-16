# Registers (or re-registers) the "ORA Skill Cache Capture" Windows scheduled task, which runs
# tools/capture_runtime_cache.py from the PRIMARY ora-skills checkout every 10 minutes and at
# logon. Run once, interactively, after the PR adding the tool has merged and
# tools/catch_up_main.py has brought local main up to date:
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Owner\ora-skills\tools\register_capture_task.ps1
#
# Runs only while Gabriel is logged on (it needs his AppData runtime cache and his git/gh
# credentials). conhost --headless gives the run a hidden console that every child process
# (git, gh) shares, so nothing flashes on screen. To pause: Disable-ScheduledTask -TaskName
# 'ORA Skill Cache Capture'. Re-running this script replaces the task in place.
$ErrorActionPreference = 'Stop'
$name   = 'ORA Skill Cache Capture'
$repo   = 'C:\Users\Owner\ora-skills'
$script = Join-Path $repo 'tools\capture_runtime_cache.py'
$python = (Get-Command python -ErrorAction Stop).Source
if (-not (Test-Path $script)) { throw "capture tool not found at $script -- merge the PR and run tools\catch_up_main.py first" }

$action   = New-ScheduledTaskAction -Execute "$env:WINDIR\System32\conhost.exe" `
              -Argument "--headless `"$python`" `"$script`"" -WorkingDirectory $repo
$every10  = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 10)
$atLogon  = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $name -Action $action -Trigger @($every10, $atLogon) `
  -Settings $settings -Principal $principal -Force `
  -Description 'Commits Cowork runtime-cache-only skill content (CACHE-AHEAD / REPO-MISSING) verbatim to a capture/runtime-cache-* branch + DO-NOT-MERGE PR, so a Save-skill click reaches git within minutes. Log: ora-skills\_staging\runtime-capture\capture.log' | Out-Null

$t = Get-ScheduledTask -TaskName $name
"registered: $($t.TaskName) state=$($t.State) action=$($t.Actions[0].Execute) $($t.Actions[0].Arguments)"
