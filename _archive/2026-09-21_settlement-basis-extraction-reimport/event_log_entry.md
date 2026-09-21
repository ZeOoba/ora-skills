## 2026-09-21 -- settlement-basis-extraction v1.3 installed via Save-skill click

- Skill: settlement-basis-extraction
- Version: v1.3
- Source commit: e976e08 (references/charge-capitalization-taxonomy.md sync); SKILL.md content itself last touched by e8852614 (2026-09-21 13:29:25 -0400, "v1.3 persistent basis flag + pre-ship re-check")
- Install path: pre-packaged .skill (package-and-stage-skill Entry point B), staged via Cowork session, installed by Gabriel's Save-skill click -- not merely the repo commit
- Confirming timestamp: 2026-09-21T15:03:39 (cache directory CreationTime moved from baseline 2026-08-24T15:21:36 to 2026-09-21T15:03:39.906868; corroborated by main.log Local [SkillsPlugin] "Sync complete: 1 downloaded" at the same second)
- Verify verdict: CONFIRMED (tools/reimport_correlate.py verify settlement-basis-extraction)
- Post-install content check: cache SKILL.md and references/charge-capitalization-taxonomy.md both present; taxonomy file content-identical to repo (CRLF/LF-normalized); SKILL.md differs only in a cosmetic YAML quoting artifact on the `name:` field (`"settlement-basis-extraction"` in cache vs unquoted in repo) -- semantically identical, not content drift
- Ledger: _staging\PENDING_REIMPORT.md NOT cleared by this session (per instruction) -- clear only after this entry is appended via append-event-log.py --entry-file
