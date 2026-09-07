<#
.SYNOPSIS
  package-and-stage-skill Entry Point B, step 7 (post-click verification), mechanized.

.DESCRIPTION
  WHY THIS EXISTS (2026-09-07, Automation Audit systematization candidate from the
  county-parcel-screen / county-sales-monitor first-install session): the post-
  Save-skill-click verification (cache file count vs the packaged manifest, the
  CreationTime discriminator between a real re-import and a mirror-sync overwrite,
  and Local main.log Delta/Sync-complete correlation to the second) was being
  re-derived by hand into a fresh ad hoc .ps1 every session. This is that check,
  generalized: it consumes the <skill>.precheck.json manifest(s) written by
  tools/entry_b_precheck.py's step 4 (stage + baseline), so the expected file set,
  expected hashes, and pre-click CreationTime baseline are never re-typed or
  re-guessed -- only ever read from what the pre-check actually verified.

  Per manifest, in order:
    1. Cache directory exists (package-and-stage-skill step 7's first check --
       if absent, the install has not landed at all).
    2. File count under the cache dir matches expected_count. Anything short is
       most likely the desktop-Settings subfolder-drop bug (2026-07-11) -- a
       multi-file skill must be reinstalled via the Cowork Save-skill button,
       not Settings -> Capabilities -> Skills.
    3. Every file's SHA256 matches the PACKAGED bytes recorded in the manifest
       (not the repo file -- see entry_b_precheck.py's check_freshness note).
    4. CreationTime discriminator: sync_appdata_mirror.py's in-place overwrite
       (pre-commit Check 4) rewrites file bytes but leaves the cache directory's
       own CreationTime untouched; a genuine Save-skill install tears the
       directory down and recreates it, so CreationTime moves to (approximately)
       the click time. Baseline "absent" -> any directory existing now is
       first-hand install evidence, the cleanest possible case. Baseline "present
       at T0" -> CreationTime must have MOVED past T0, or this is exactly the
       hash-match-by-construction case package-and-stage-skill v1.13 documents
       (content matches because the mirror-sync hook copied it, not because
       Gabriel clicked Save skill).
    5. Local main.log ($env:LOCALAPPDATA\Claude\Logs\main.log -- NOT the Roaming
       copy, which goes quiet for a day or more between app restarts) correlation:
       a [SkillsPlugin] "Sync complete: N downloaded, 0 failed" line whose
       timestamp lands within -ToleranceSeconds of the cache directory's
       CreationTime is skill-specific, first-hand confirmation (the log itself
       never names a skill, so this timestamp match is what makes it
       attributable). No match is reported, not treated as failure -- the
       CreationTime discriminator alone is still meaningful per package-and-
       stage-skill's own doctrine, and main.log can be stale (checked via
       -MainLogLivenessMinutes) for reasons unrelated to whether the install
       happened.

  Per-skill verdict is PASS / FAIL / AMBIGUOUS, never averaged into a silent
  batch summary. FAIL = cache dir absent, file count wrong, or any hash
  mismatch. AMBIGUOUS = content is correct but CreationTime did not move past
  a present baseline (the mirror-sync-only case) -- content correctness is
  NOT proof of a real click. PASS requires both content correctness and a
  moved-or-absent-baseline CreationTime.

  IMPLEMENTATION NOTE: all per-manifest diagnostic lines are written via
  Write-Host, deliberately -- Test-OneManifest's return value (the bare verdict
  string) travels down the PowerShell success-output pipeline, and anything
  else written to that same stream inside the function (Write-Output) becomes
  PART of that return value once collected into an array, silently corrupting
  $results[$p] into a multi-line array instead of a single verdict string
  (caught in testing 2026-09-07: a single-manifest PASS run reported
  "OVERALL: 10/1" because every diagnostic line got counted). Write-Host goes
  straight to the console and never enters the object pipeline, so it cannot
  contaminate a function's return value -- this is a general PowerShell
  function-design rule, not specific to this script.

.PARAMETER ManifestPath
  One or more explicit .precheck.json manifest paths.

.PARAMETER ManifestDir
  Directory to scan for *.precheck.json (default: current directory). Ignored
  when -ManifestPath is given.

.PARAMETER ToleranceSeconds
  Max seconds between a cache directory's CreationTime and a main.log
  Sync-complete timestamp to count as a correlated match. Default 5 (observed
  live matches have been 1-2s apart; desktop log timestamps have 1-second
  resolution).

.PARAMETER MainLogLivenessMinutes
  If the Local main.log's own mtime is older than this many minutes, it is
  reported as STALE and log-correlation is skipped rather than misread as "no
  sync happened around then". Default 30.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\verify_install.ps1 -ManifestDir _staging\2026-09-07

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\verify_install.ps1 -ManifestPath _staging\2026-09-07\county-parcel-screen.precheck.json
#>
param(
    [string[]]$ManifestPath,
    [string]$ManifestDir = '.',
    [string]$LocalMainLog = "$env:LOCALAPPDATA\Claude\Logs\main.log",
    [int]$ToleranceSeconds = 5,
    [int]$MainLogLivenessMinutes = 30
)
$ErrorActionPreference = 'Stop'


function Get-SyncCompleteEvents {
    param([string]$LogPath)
    # Returns @{ Live = $bool; Reason = 'text'; Events = @([datetime], ...) }. Never
    # throws -- an absent or unreadable log is reported as not-live, not a script
    # error, since main.log liveness is itself a documented, expected failure mode
    # (the desktop build can go quiet between app restarts).
    if (-not (Test-Path $LogPath)) {
        return @{ Live = $false; Reason = "not found: $LogPath"; Events = @() }
    }
    $li = Get-Item $LogPath
    $ageMin = ((Get-Date) - $li.LastWriteTime).TotalMinutes
    $live = $ageMin -le $MainLogLivenessMinutes
    $events = @()
    if ($live) {
        $lines = Get-Content $LogPath -Tail 20000 | Where-Object {
            $_ -match 'SkillsPlugin' -and $_ -match 'Sync complete: (\d+) downloaded, 0 failed'
        }
        foreach ($ln in $lines) {
            if ($ln -match '^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})') {
                $events += [datetime]::ParseExact($Matches[1], 'yyyy-MM-dd HH:mm:ss', $null)
            }
        }
    }
    return @{ Live = $live; Reason = "mtime=$($li.LastWriteTime.ToString('s')) age=$([math]::Round($ageMin,1))min"; Events = $events }
}


function Test-OneManifest {
    param([string]$Path, [object]$LogInfo)
    $m = Get-Content $Path -Raw | ConvertFrom-Json
    $skill = $m.skill
    $cacheDir = $m.baseline.cache_dir
    Write-Host "=== $skill ==="
    Write-Host "  manifest: $Path"
    $fail = @()
    $ambiguous = @()

    if (-not (Test-Path $cacheDir)) {
        Write-Host "  CACHE DIR: ABSENT -- install has not landed at $cacheDir"
        Write-Host "  VERDICT: FAIL"
        return 'FAIL'
    }
    $dirItem = Get-Item $cacheDir
    $files = Get-ChildItem $cacheDir -Recurse -File
    Write-Host "  cache_dir: $cacheDir"
    Write-Host "  CreationTime: local=$($dirItem.CreationTime.ToString('s')) utc=$($dirItem.CreationTimeUtc.ToString('s'))"

    if ($files.Count -ne $m.expected_count) {
        $fail += "file count $($files.Count) != expected $($m.expected_count) -- likely the desktop-Settings subfolder-drop bug (2026-07-11); reinstall via Cowork Save skill"
    }
    Write-Host "  FILE COUNT: $($files.Count) / expected $($m.expected_count)"


    foreach ($pf in $m.per_file) {
        $actual = Join-Path $cacheDir ($pf.rel -replace '/', '\')
        if (-not (Test-Path $actual)) {
            $fail += "MISSING in cache: $($pf.rel)"
            Write-Host "    $($pf.rel): MISSING"
            continue
        }
        $h = (Get-FileHash $actual -Algorithm SHA256).Hash.ToLower()
        if ($h -eq $pf.sha256) {
            Write-Host "    $($pf.rel): MATCH"
        } else {
            $fail += "HASH MISMATCH: $($pf.rel) expected $($pf.sha256.Substring(0,12)) got $($h.Substring(0,12))"
            Write-Host "    $($pf.rel): MISMATCH expected=$($pf.sha256.Substring(0,12)) actual=$($h.Substring(0,12))"
        }
    }

    $baselineCT = $m.baseline.creation_time
    if ($null -eq $baselineCT -or $baselineCT -eq '') {
        Write-Host "  CREATIONTIME DISCRIMINATOR: baseline was ABSENT -- directory now existing is first-hand install evidence -> REAL INSTALL"
    } else {
        $baseDt = [datetimeoffset]::Parse($baselineCT).UtcDateTime
        if ($dirItem.CreationTimeUtc -gt $baseDt.AddSeconds(1)) {
            Write-Host "  CREATIONTIME DISCRIMINATOR: moved ($($baseDt.ToString('s')) -> $($dirItem.CreationTimeUtc.ToString('s'))) -> REAL INSTALL"
        } else {
            $ambiguous += "CreationTime unchanged since baseline ($($baseDt.ToString('s'))) -- possibly a mirror-sync overwrite (sync_appdata_mirror.py), not a confirmed Save-skill click"
            Write-Host "  CREATIONTIME DISCRIMINATOR: UNCHANGED since baseline -- AMBIGUOUS (content match alone is not proof of a real click; see package-and-stage-skill v1.13)"
        }
    }


    if (-not $LogInfo.Live) {
        Write-Host "  MAIN.LOG: STALE or absent ($($LogInfo.Reason)) -- treated as unavailable; CreationTime discriminator above is primary evidence"
    } else {
        $match = $LogInfo.Events | Where-Object {
            [math]::Abs((New-TimeSpan -Start $_ -End $dirItem.CreationTime).TotalSeconds) -le $ToleranceSeconds
        } | Select-Object -First 1
        if ($match) {
            $delta = [math]::Round((New-TimeSpan -Start $match -End $dirItem.CreationTime).TotalSeconds, 1)
            Write-Host "  MAIN.LOG: Sync-complete at $($match.ToString('s')) matches CreationTime (delta ${delta}s) -- skill-specific first-hand confirmation"
        } else {
            Write-Host "  MAIN.LOG: live ($($LogInfo.Reason)) but no Sync-complete within ${ToleranceSeconds}s of CreationTime -- circumstantial only, not a failure by itself"
        }
    }

    if ($fail.Count -gt 0) {
        Write-Host "  VERDICT: FAIL -- $($fail -join '; ')"
        return 'FAIL'
    }
    if ($ambiguous.Count -gt 0) {
        Write-Host "  VERDICT: AMBIGUOUS -- $($ambiguous -join '; ')"
        return 'AMBIGUOUS'
    }
    Write-Host "  VERDICT: PASS"
    return 'PASS'
}


if ($ManifestPath) {
    $paths = $ManifestPath
} else {
    $paths = Get-ChildItem $ManifestDir -Filter '*.precheck.json' | ForEach-Object { $_.FullName }
}
if (-not $paths -or $paths.Count -eq 0) {
    Write-Host "verify_install: no *.precheck.json manifests found (checked: $(if ($ManifestPath) { $ManifestPath -join ', ' } else { $ManifestDir }))"
    exit 1
}

$logInfo = Get-SyncCompleteEvents -LogPath $LocalMainLog
Write-Host "Local main.log: $($logInfo.Reason)"
Write-Host ''

$results = @{}
foreach ($p in $paths) {
    $results[$p] = Test-OneManifest -Path $p -LogInfo $logInfo
    Write-Host ''
}

$passCount = 0
foreach ($v in $results.Values) { if ($v -eq 'PASS') { $passCount++ } }
Write-Host "OVERALL: $passCount/$($results.Count) PASS"
foreach ($p in $paths) {
    Write-Host "  $([System.IO.Path]::GetFileName($p)): $($results[$p])"
}
if ($passCount -eq $results.Count) { exit 0 } else { exit 1 }
