# ora-skills — CLAUDE.md

Source of truth for Oxford Realty Advisors' custom skills: one top-level folder per skill, each with a `SKILL.md`. Structure, packaging flow, routing and the skill inventory live in `README.md`; this file holds only what an agent must know before editing.

## Commands

- Gate before every commit: `bash tools/run_suite.sh` (tools suite) and `bash tools/run_skill_suites.sh` (skill suites). Both must print no `FAIL` and no `SKIP`. `pip install pymupdf python-docx reportlab lxml openpyxl` first, and `poppler-utils` for `pdftotext`; a missing dependency shows up as `SKIP`, which is not a pass.
- Frontmatter, tree hygiene and shared-dependency check over every skill: `python tools/skill_ci_gates.py frontmatter`.
- Package a skill: `python tools/package_skills.py <outdir> <skill>`. The output directory comes first; swapping the arguments packages into a skill's own source tree. Never use PowerShell `Compress-Archive`.
- CI (`skill-gates`, `tools-tests`) re-runs the same commands on every push to any branch.

## Rules that prevent known failures

- `SKILL.md` frontmatter needs `name` and `description`. The description is about 1024 characters, states when to use the skill plus routing tie-breaks ("NOT X, use Y"), and never contains a version, a date, changelog text or a summary of the steps. Overflow trigger vocabulary goes under `## BODY TRIGGERS` in the body.
- The version lives in the body H1 as `# Title (vX.Y)`, with a dated changelog in the body. Any change that touches a scored or governor constant (DSCR, LTV, scorecard weights) must say explicitly whether that constant changed. Do not change governor constants without Gabriel's permission.
- Never delete a skill. Retire it with `git mv <skill> _archive/<skill>_retired-YYYY-MM-DD`, after `git grep -n -w "<skill>" -- . ':(exclude)<skill>' ':(exclude)_archive'` shows nothing still depends on it. Repoint or tombstone every hit in the same commit.
- `target-markets.json` lives once at the repo root. Never copy it into a skill folder; any edit must bump its `version` and `updated` fields, and CI checks this against the PR base.
- Test files under `tools/test_*.py` use stdlib `unittest` with a `__main__` runner. Bare pytest-style `def test_*` functions never execute and fail the gate. Skill-level test suites (`test_*.py` under a skill dir) are gated automatically; to keep one out of CI, add a top-level `CI_EXCLUDE = "<reason>"` line to that file. `skill_ci_gates.py suite-continuity --base auto` fails if a suite present at the PR base disappears, unless it moved to `_archive/<skill>/...` or the standard retirement form `_archive/<skill>_retired-YYYY-MM-DD/...`, or the removing commit carries a `Suite-Removed: <path>` trailer. It runs in CI, not in the local `tools/run_skill_suites.sh`.
- Update the skill inventory in `README.md` whenever a skill is added or archived.
- Never commit tenant PII, financial statements or QuickBooks backups, and never name an active confidential deal in a skill, example or fixture.
- Concurrent sessions edit this repo. Run `git fetch origin` and `git status -sb`, stage explicit paths only (never `git add -A` or `git commit -a`), and check `git diff --cached --stat` before committing.
- Local-only tooling (`tools/repo_first_check.py`, `tools/sync_appdata_mirror.py`, the git hooks in `tools/hooks/`) depends on the Windows AppData runtime cache and does not apply in a cloud checkout. Cache divergence is reconciled from the local Code session, not here.
