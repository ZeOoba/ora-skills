foreach ($s in @('document-assembly','exception-detection')) {
  Write-Output "=== $s ==="
  $p = "C:\Users\Owner\ora-skills\$s\SKILL.md"
  Select-String -Path $p -Pattern 'v[0-9]+\.[0-9]+' |
    Select-Object -First 4 |
    ForEach-Object { ('L' + $_.LineNumber + ': ' + $_.Line.Trim().Substring(0, [Math]::Min(140, $_.Line.Trim().Length))) }
}
