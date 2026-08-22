Select-String -LiteralPath 'C:\Users\Owner\.claude\maintenance\append-event-log.py' -Pattern 'HEADER|startswith|re\.compile|encoding=|utf-8|def main|argparse' |
  Select-Object -First 40 |
  ForEach-Object { Write-Output ($_.LineNumber.ToString() + ': ' + $_.Line) }
