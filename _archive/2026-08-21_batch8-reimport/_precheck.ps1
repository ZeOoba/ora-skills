Set-Location C:\Users\Owner\ora-skills

$skills = @(
  "automation-health-monitor",
  "deal-execution",
  "debt-management",
  "document-assembly",
  "estoppel-request-generation",
  "lease-abstraction-pipeline",
  "legal-intelligence",
  "repo-architecture-review"
)

Write-Output "=== GIT STATUS (dirty check) ==="
git status --short

Write-Output ""
Write-Output "=== PER-SKILL: last 3 commits touching dir, HEAD SHA, frontmatter version ==="
foreach ($s in $skills) {
  Write-Output "--- $s ---"
  git log -3 --pretty=format:"%h %ad %s" --date=short -- "$s/"
  Write-Output ""
  $md = Get-Content "$s\SKILL.md" -Raw -ErrorAction SilentlyContinue
  if ($md) {
    if ($md -match '(?m)^name:\s*(\S+)\s*$') { Write-Output ("name: " + $Matches[1]) }
    if ($md -match '(?m)"?\bv(\d+\.\d+(\.\d+)?[a-z]?)\b"?\s*\.?"?\s*(,|\}|$)') {}
  }
  # pull last vX.Y token from description line at end of file's frontmatter approx
  $verMatches = [regex]::Matches($md, 'v\d+\.\d+(\.\d+)?[a-z]?')
  if ($verMatches.Count -gt 0) {
    Write-Output ("last version token in SKILL.md: " + $verMatches[$verMatches.Count-1].Value)
  }
}

Write-Output ""
Write-Output "=== plugin_of() check for each skill ==="
foreach ($s in $skills) {
  python -c "import sys;sys.path.insert(0,'tools');from package_skills import plugin_of;print('$s ->', plugin_of('$s'))"
}
