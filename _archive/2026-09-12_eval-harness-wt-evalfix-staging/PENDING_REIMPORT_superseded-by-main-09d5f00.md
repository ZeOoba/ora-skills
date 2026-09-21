# PENDING REIMPORT — repo is ahead of the Cowork runtime cache
#
# UNTRACKED local state (see .gitignore). Written by tools/hooks/post-commit.
# Each line = a skill whose PACKAGED content was committed but NOT yet reimported
# into the runtime cache (Save-skill click is manual). Clear a line after a
# CONFIRMED Save-skill install re-syncs the cache:
#   python tools/pending_reimport.py clear <skill>
# To act on a pending skill: package_skills.py -> present .skill -> Save-skill click.
#
# THIS IS NOT AN INSTALL ORACLE. The ledger is cleared BY HAND after the fact, so a
# line here means only "nobody has cleared it yet" -- it does NOT mean the skill is
# uninstalled. To decide whether an install actually happened, in this order:
#   1. AppData\Roaming\Claude\logs\main.log -- a non-zero "Delta: N to download"
#      followed by "Sync complete". The post-commit copy produces NO SkillsPlugin log
#      activity, so a non-zero delta cannot be manufactured by this tooling.
#   2. Runtime-cache mtime against a pre-click baseline.
#   3. Hash vs repo -- confirms WHAT installed, never WHETHER.
# 2026-08-03: a session read this ledger two minutes after a confirmed Save-skill
# click and reported the skill uninstalled. See memory/reference_skill_reimport_sync_lag.md.

- acquisition-underwriting | pending since 2026-09-12T22:29Z | commit e087d3e "fix(eval-harness): v4.21 no-price-no-NOI Basis rule, Hamilton+REDACTED-148 rebaselines, skip gate, multi-completion check" | trigger: acquisition-underwriting/SKILL.md
- acquisition-underwriting-eval-harness | pending since 2026-09-12T22:29Z | commit e087d3e "fix(eval-harness): v4.21 no-price-no-NOI Basis rule, Hamilton+REDACTED-148 rebaselines, skip gate, multi-completion check" | trigger: acquisition-underwriting-eval-harness/SKILL.md, acquisition-underwriting-eval-harness/golden_set/REDACTED-021.json, acquisition-underwriting-eval-harness/golden_set/REDACTED-027.json, acquisition-underwriting-eval-harness/lib/doctrine_skip_gate.py, acquisition-underwriting-eval-harness/lib/test_doctrine_skip_gate.py
