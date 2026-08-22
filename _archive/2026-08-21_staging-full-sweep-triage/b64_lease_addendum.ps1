$src = 'C:\Users\Owner\ora-skills\_staging\2026-08-14\lease-addendum.skill'
$dst = 'C:\Users\Owner\ora-skills\_staging\2026-08-14\lease-addendum.skill.b64'
$b = [Convert]::ToBase64String([IO.File]::ReadAllBytes($src))
$sb = [Text.StringBuilder]::new()
for ($i = 0; $i -lt $b.Length; $i += 320) {
  [void]$sb.AppendLine($b.Substring($i, [Math]::Min(320, $b.Length - $i)))
}
[IO.File]::WriteAllText($dst, $sb.ToString())
Write-Output ("B64_BYTES: " + (Get-Item $dst).Length)
Write-Output ("B64_LINES: " + (Get-Content $dst | Measure-Object -Line).Lines)
Write-Output "DONE"
