#!/usr/bin/env bash
# Runs every gated skill-level test suite under tools/run_suite.sh's rules (zero failures,
# zero unallowed skips, zero EMPTY/BARE files, zero unmatched globs). Single source for
# local runs and .github/workflows/skill-gates.yml (2026-10-03).
#
# The gated set is auto-discovered by tools/skill_ci_gates.py: every test_*.py under a skill dir,
# minus files declaring a top-level CI_EXCLUDE = "<reason>" (an empty reason fails).
# `skill_ci_gates.py suite-continuity --base auto` (CI only; this runner does not run it) fails
# if a suite present at the PR base is no longer discovered, unless (a) a file added in
# base..HEAD under _archive/ (any depth) has a path ending <skill>/<rest> or
# <skill>_retired-YYYY-MM-DD/<rest> (path-only match), or (b) any commit in base..HEAD has a
# line starting `Suite-Removed: <path>`. Recommended: git mv <skill> _archive/<skill>_retired-DATE
# plus a trailer on the removing commit; the gate itself is looser.
#
# Shared-file staging: the QC suites (lease-form-qc, lease-addendum, listing-agreement-qc)
# import tools/ora_doc_qc.py, which package_skills.py injects as scripts/ora_doc_qc.py via
# SHARED_ROOT_DEPS at package time. The suites themselves are written for the dev-checkout
# layout (lease-form-qc's test_ora_doc_qc_resolves_to_the_repo_root_canonical_copy asserts NO
# co-located copy exists in the checkout; others read cross-skill fixtures),
# where each script's sys.path fallback resolves tools/. So the suites run in place, and the
# packaged layout is verified separately by `skill_ci_gates.py packaged-layout`, which builds
# each SHARED_ROOT_DEPS skill with package_skills.package() outside the repo and confirms its
# scripts import the packaged copy -- nothing is ever hand-copied into the tree.
#
# Usage: bash tools/run_skill_suites.sh   (from anywhere; needs the deps listed in skill-gates.yml)

cd "$(dirname "$0")/.." || exit 2

python tools/skill_ci_gates.py packaged-layout || exit 1

suites=$(python tools/skill_ci_gates.py suites) || exit 1
# Windows Python prints CRLF; a trailing \r on each path would make every file NOMATCH.
suites=${suites//$'\r'/}
# shellcheck disable=SC2086  # one repo-relative path per line, no spaces
bash tools/run_suite.sh $suites
