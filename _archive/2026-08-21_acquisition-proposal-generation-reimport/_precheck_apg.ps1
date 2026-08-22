$ErrorActionPreference = 'Continue'
$pkg  = 'C:\Users\Owner\ora-skills\_staging\2026-08-21_acquisition-proposal-generation-reimport\acquisition-proposal-generation.skill'
$repo = 'C:\Users\Owner\ora-skills\acquisition-proposal-generation'
$want = '1105ff284549d99fd378a3f3c3165610c0791a666f620f3530ded6b9609bd4d6'

Write-Output "=== ITEM 1: EXISTS ==="
if (Test-Path -LiteralPath $pkg) {
    $fi = Get-Item -LiteralPath $pkg
    Write-Output ("PKG_EXISTS=YES bytes={0} mtime={1:yyyy-MM-dd HH:mm:ss}" -f $fi.Length, $fi.LastWriteTime)
    $h = (Get-FileHash -LiteralPath $pkg -Algorithm SHA256).Hash.ToLower()
    Write-Output ("PKG_SHA256=" + $h)
    if ($h -eq $want) { Write-Output "SHA_MATCH=YES" } else { Write-Output ("SHA_MATCH=NO expected=" + $want) }
} else {
    Write-Output "PKG_EXISTS=NO"
}

Write-Output ""
Write-Output "=== STAGING DIR CONTENTS ==="
Get-ChildItem -LiteralPath (Split-Path -Parent $pkg) -Recurse -File |
    ForEach-Object { Write-Output ("{0}`t{1}`t{2:yyyy-MM-dd HH:mm:ss}" -f $_.FullName.Substring((Split-Path -Parent $pkg).Length+1), $_.Length, $_.LastWriteTime) }

Write-Output ""
Write-Output "=== ITEM 2: ZIP ENTRIES ==="
Add-Type -AssemblyName System.IO.Compression.FileSystem
if (Test-Path -LiteralPath $pkg) {
    $zip = [System.IO.Compression.ZipFile]::OpenRead($pkg)
    foreach ($e in $zip.Entries) {
        $bs = if ($e.FullName -match '\\') { 'BACKSLASH' } else { 'ok' }
        Write-Output ("ENTRY`t{0}`t{1}`t{2}" -f $e.FullName, $e.Length, $bs)
    }
    Write-Output ("ENTRY_COUNT=" + $zip.Entries.Count)
    $zip.Dispose()
}

Write-Output ""
Write-Output "=== ITEM 3: REPO COPY ==="
if (Test-Path -LiteralPath $repo) {
    Get-ChildItem -LiteralPath $repo -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($repo.Length+1).Replace('\','/')
        $rh  = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower()
        Write-Output ("REPO`t{0}`t{1}`t{2}" -f $rel, $_.Length, $rh)
    }
} else {
    Write-Output "REPO_DIR_MISSING"
}
