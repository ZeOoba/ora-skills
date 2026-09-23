#!/usr/bin/env bash
# Runs every tools/test_*.py and enforces the zero-skip baseline.
# Single source for README step 7 (local) and .github/workflows/tools-tests.yml (CI).
#
# Fails on any failing test file AND on any skipped test: a skip is exactly how the
# rent-comp retirement breakage hid (2026-08-05). A genuinely-needed skip goes in
# ALLOWED_SKIPS as an exact-count `path=N` entry with a reason -- that file may report
# exactly skipped=N, no more, so a missing dependency (e.g. PyMuPDF -> census
# skipped=7) still fails.
#
# Usage: bash tools/run_suite.sh   (from the repo root; needs `pip install pymupdf`)
# Writes a markdown table to $GITHUB_STEP_SUMMARY when set (CI).

cd "$(dirname "$0")/.." || exit 2

ALLOWED_SKIPS=''
if [ "${OS:-}" != "Windows_NT" ]; then
  # test_path_over_260_characters is skipUnless(os.name == "nt"); it cannot run
  # off Windows. On Windows the baseline stays zero.
  ALLOWED_SKIPS='tools/test_package_census.py=1'
fi

summary_file=${GITHUB_STEP_SUMMARY:-/dev/null}
failed=()
skipped=()
{
  echo '| Test file | Result |'
  echo '|---|---|'
} >> "$summary_file"

for f in tools/test_*.py; do
  [ -n "${GITHUB_ACTIONS:-}" ] && echo "::group::$f"
  out=$(python "$f" 2>&1)
  rc=$?
  [ -n "${GITHUB_ACTIONS:-}" ] && { printf '%s\n' "$out"; echo "::endgroup::"; }
  summary=$(printf '%s\n' "$out" | grep -E '^(Ran [0-9]+ tests? in|OK|FAILED|all checks passed)' | tr '\n' ' ')
  skip=$(printf '%s\n' "$out" | grep -o 'skipped=[0-9]*' | head -1)
  if [ "$rc" -ne 0 ]; then
    failed+=("$f")
    echo "FAIL $f (exit $rc) $summary"
    [ -n "${GITHUB_ACTIONS:-}" ] && echo "::error file=$f::exit $rc -- $summary"
    echo "| \`$f\` | FAIL (exit $rc) $summary |" >> "$summary_file"
  elif [ -n "$skip" ] && [[ " $ALLOWED_SKIPS " != *" $f=${skip#skipped=} "* ]]; then
    skipped+=("$f")
    echo "SKIP $f $skip -- the skip baseline is zero"
    [ -n "${GITHUB_ACTIONS:-}" ] && echo "::error file=$f::$skip -- the skip baseline is zero; a skip hid the rent-comp retirement breakage"
    echo "| \`$f\` | SKIP ($skip) $summary |" >> "$summary_file"
  else
    echo "| \`$f\` | ok $summary |" >> "$summary_file"
  fi
done

echo "failed: ${#failed[@]}  unallowed skips: ${#skipped[@]}"
[ "${#failed[@]}" -eq 0 ] && [ "${#skipped[@]}" -eq 0 ]
