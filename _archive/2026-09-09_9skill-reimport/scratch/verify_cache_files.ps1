$targets = @('debt-management','disposition-analysis','lease-form-qc','lease-generation','lease-renewal-pipeline','parcel-data-recovery')
$root = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin'
Get-ChildItem -Path $root -Recurse -Directory -ErrorAction SilentlyContinue |
    Where-Object { $targets -contains $_.Name } |
    ForEach-Object {
        Write-Output "$($_.Name) => Created=$($_.CreationTime.ToString('yyyy-MM-ddTHH:mm:ss.ffffff'))"
        Get-ChildItem $_.FullName -Recurse -File | ForEach-Object { Write-Output "    file: $($_.FullName.Substring($_.FullName.IndexOf('skills\') ))" }
    }
