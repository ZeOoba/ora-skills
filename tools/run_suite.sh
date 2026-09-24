#!/usr/bin/env bash
# Runs every tools/test_*.py and enforces the zero-skip and zero-empty baselines.
# Single source for README step 7 (local) and .github/workflows/tools-tests.yml (CI).
#
# Fails on any failing test file AND on any skipped test: a skip is exactly how the
# rent-comp retirement breakage hid (2026-08-05). A genuinely-needed skip goes in
# ALLOWED_SKIPS as an exact-count `path=N` entry with a reason -- that file may report
# exactly skipped=N, no more, so a missing dependency (e.g. PyMuPDF -> census
# skipped=7) still fails.
#
# Also fails on any file that exits 0 having run ZERO tests (2026-09-23, found by the
# adversarial merge gate on PR #79): tools/test_reimport_cycle.py shipped as bare
# pytest-style `def test_*` functions with no unittest runner, so `python <file>`
# executed nothing, exited 0, and was reported `ok` -- the zero-skip check cannot see
# that, because nothing reports as skipped. Every file must print unittest's
# `Ran N tests` with N >= 1. The only exemption is a non-unittest check script listed
# by exact path in NON_UNITTEST, which must instead print `all checks passed`.
# A file whose tests only PARTLY run is caught statically: any module-level
# `def test_*` (a bare function next to a TestCase never executes) fails as BARE.
# (NON_UNITTEST scripts are exempt from BARE: they call their own functions.) A
# whole-module skip (`Ran 0 tests ... skipped=N`, e.g. setUpModule raising SkipTest)
# is still EMPTY, never an allowed skip. ALLOWED_SKIPS only compares unittest's
# skipped=N count, and that count is not always per test: a module whose setUpModule
# raises SkipTest, or a class whose setUpClass does, reports skipped=1 however many
# tests it hides (an @unittest.skip decorator does count each test). So a file that
# ran >= 1 test can still hide a whole setUpClass-skipped class behind a matching
# `path=1` entry -- keep entries for per-test skipUnless cases only (like the census
# long-path test).
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

# Plain-assert check scripts with no unittest runner; each prints `all checks passed`
# on success. A listed file that stops printing it still fails.
NON_UNITTEST='tools/test_description_budget.py'

summary_file=${GITHUB_STEP_SUMMARY:-/dev/null}
failed=()
skipped=()
empty=()
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
  ran=$(printf '%s\n' "$out" | grep -oE '^Ran [0-9]+ tests? in' | grep -oE '[0-9]+' | tail -1)
  bare=''
  if [[ " $NON_UNITTEST " == *" $f "* ]]; then
    printf '%s\n' "$out" | grep -q '^all checks passed' && executed=1 || executed=0
  else
    [ "${ran:-0}" -ge 1 ] && executed=1 || executed=0
    bare=$(grep -nE '^(async[[:space:]]+)?def test_' "$f" | tr '\n' ' ')
  fi
  if [ "$rc" -ne 0 ]; then
    failed+=("$f")
    echo "FAIL $f (exit $rc) $summary"
    [ -n "${GITHUB_ACTIONS:-}" ] && echo "::error file=$f::exit $rc -- $summary"
    echo "| \`$f\` | FAIL (exit $rc) $summary |" >> "$summary_file"
  elif [ -n "$bare" ]; then
    empty+=("$f")
    echo "BARE $f -- module-level def test_* never runs under 'python <file>': $bare"
    [ -n "${GITHUB_ACTIONS:-}" ] && echo "::error file=$f::module-level def test_* never runs -- move it into a unittest.TestCase"
    echo "| \`$f\` | BARE (module-level def test_*) $summary |" >> "$summary_file"
  elif [ "$executed" -ne 1 ]; then
    empty+=("$f")
    echo "EMPTY $f -- exit 0 but no tests ran (needs 'Ran N tests' with N>=1)"
    [ -n "${GITHUB_ACTIONS:-}" ] && echo "::error file=$f::exit 0 but no tests ran -- a file with no unittest runner reports ok while testing nothing"
    echo "| \`$f\` | EMPTY (no tests ran) $summary |" >> "$summary_file"
  elif [ -n "$skip" ] && [[ " $ALLOWED_SKIPS " != *" $f=${skip#skipped=} "* ]]; then
    skipped+=("$f")
    echo "SKIP $f $skip -- the skip baseline is zero"
    [ -n "${GITHUB_ACTIONS:-}" ] && echo "::error file=$f::$skip -- the skip baseline is zero; a skip hid the rent-comp retirement breakage"
    echo "| \`$f\` | SKIP ($skip) $summary |" >> "$summary_file"
  else
    echo "| \`$f\` | ok $summary |" >> "$summary_file"
  fi
done

echo "failed: ${#failed[@]}  unallowed skips: ${#skipped[@]}  ran no/bare tests: ${#empty[@]}"
[ "${#failed[@]}" -eq 0 ] && [ "${#skipped[@]}" -eq 0 ] && [ "${#empty[@]}" -eq 0 ]
