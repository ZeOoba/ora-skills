$f = "C:\Users\Owner\ora-skills\_staging\2026-08-14\batch3.b64"
$pad = ("PADDING-IGNORE-BELOW-THIS-LINE`r`n" + (("X" * 320 + "`r`n") * 600))
[IO.File]::AppendAllText($f, $pad)
Write-Output ("PADDED_BYTES: " + (Get-Item $f).Length)
