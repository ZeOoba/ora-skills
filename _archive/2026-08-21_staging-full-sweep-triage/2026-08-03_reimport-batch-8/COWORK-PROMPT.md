# Cowork prompt — install 8 skills (paste everything below the line)

---

Install eight ORA skills whose repo content is ahead of the Cowork runtime cache. All eight are already committed and pushed; only the Save-skill click is outstanding. Work through them one at a time and report per skill.

**Packages** — all in:

```
C:\Users\Owner\ora-skills\_staging\2026-08-03_reimport-batch-8\
```

| Skill | Files | Install path |
|---|---|---|
| `acquisition-underwriting` | 2 | **Save skill only** |
| `lease-form-qc` | 2 | **Save skill only** |
| `market-monitor` | 2 | **Save skill only** |
| `masterlease-jurisdiction-rebase` | 6 | **Save skill only** |
| `document-assembly` | 1 | either |
| `ratify-hurdle-rate` | 1 | either |
| `solar-lease-underwriting` | 1 | either |
| `tenant-email` | 1 | either |

⚠️ **The four multi-file skills MUST go through the Save-skill button.** The desktop Settings → Capabilities path silently drops subfolder files — reproduced twice on 2026-07-11. A partial install there looks successful and leaves the skill broken at runtime.

Each package was built by `tools/package_skills.py` and verified byte-identical to its committed repo files, with no `__pycache__`/`.pyc` bundled. Do **not** repackage or edit them. If a hash check disagrees, stop and report rather than rebuilding.

## Why each is pending

- **`tenant-email` v1.2** and **`ratify-hurdle-rate` v1.3** (`edc9fa1`) stamped Gabriel as *"Principal"*, contradicting CLAUDE.md's ratified **"VP Acquisitions"**. tenant-email's is the literal signature block embedded in every outbound tenant draft; ratify-hurdle-rate's is the "Ratified by:" line on a governance audit memo. `ratify-hurdle-rate` has **never been installed** — there is no cache directory for it at all.
- **`document-assembly`** (`74120f6`) adds a bullet recording that its signing-authority line is **deliberately exempt** from that ruling. `"Gabriel Goldberg, Member / Principal"` there is the capacity in which Gabriel binds an LLC, not his firm title. **Do not "correct" it.**
- **`lease-form-qc` v2.1.1** (`3cb891f`) bundles `scripts/lease_qc.py` so the scanner can actually run.
- **`masterlease-jurisdiction-rebase` v1.1.2** (`ea9dddf`) — 6 files including a `.docx` fixture and `config/*.json`.
- **`acquisition-underwriting`**, **`market-monitor`**, **`solar-lease-underwriting`** have **no ledger entry** — they surfaced only from the full repo-vs-cache SHA256 sweep, meaning their drift predates the commit hook or a hook run was missed. Treat them as equally real.

## Steps

1. **Confirm all eight `.skill` files exist** at the path above; report sizes.
2. **Before any clicks, capture a baseline**: for each skill, record whether
   `%APPDATA%\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills\<skill>\SKILL.md`
   exists and its mtime. Without a baseline, mtime proves nothing afterwards.
3. **Surface each `.skill`** so its Save-skill control appears and ask Gabriel to click. Eight separate clicks. This cannot be automated — the click is manual by design.
4. **Verify properly, in this order:**
   - **`%APPDATA%\Roaming\Claude\logs\main.log`** — a non-zero `Delta: N to download` followed by `Sync complete`. This is the authoritative signal.
   - Cache mtime vs the step-2 baseline.
   - SHA-256 of each cached file vs `C:\Users\Owner\ora-skills\<skill>\...`. Confirms **what** installed, never **whether**.

   ⚠️ **A hash match alone does NOT mean installed.** The post-commit hook copies changed files straight into the cache, so a skill can match the repo perfectly and still never have been installed — verified on 2026-08-03, when `tenant-email` and `document-assembly` both matched by hash while `main.log` showed no corresponding sync. That copy produces *no* SkillsPlugin log activity, which is exactly why the log is the oracle and the hash is not.

   ⚠️ **`_staging\PENDING_REIMPORT.md` is NOT an install oracle either.** It is cleared by hand *after* the fact, so an entry means only "nobody has cleared it yet". On 2026-08-03 a session read it two minutes after a confirmed click and wrongly reported the skill uninstalled. It is a work queue, nothing more.

   For the multi-file skills, verify **every** bundled file landed, not just `SKILL.md` — that is the exact failure mode the Settings → Capabilities path produces.

5. **Only after a confirmed re-sync**, clear each cleared skill:

```powershell
cd C:\Users\Owner\ora-skills
python tools\pending_reimport.py clear <skill>
```

   Clearing the last entry deletes `PENDING_REIMPORT.md` — expected, not an error. Then run `python tools\pending_reimport.py candidates` and confirm it reports zero. `candidates` (ledger UNION full sweep), not `list`, is the authoritative queue — `list` reads the ledger alone and is blind to sweep-only drift, which is how three of these eight went unnoticed.

6. **Spot-check content landed.** In installed `tenant-email\SKILL.md`: signature block reads `Gabriel Goldberg, VP Acquisitions`, no `Goldberg, Principal` remains. In installed `document-assembly\SKILL.md`: `Member / Principal` is still present — correct there. In `lease-form-qc`: `scripts/lease_qc.py` exists.

## Boundaries

- **Do not edit any SKILL.md.** If content looks wrong, report it — a Cowork-side edit creates the repo-vs-cache drift this process exists to close.
- **Do not commit or push.** All eight commits are already on `origin/main`.
- **You cannot write `event_log.md`** — `~/.claude` is fail-closed to Cowork. Report the outcome; a Claude Code session will log it.
- **These skills are under active concurrent development.** `masterlease-jurisdiction-rebase` alone moved through three commits in one hour (`863a0b3` → `ea9dddf`). If a package's hash no longer matches the repo when you check, the repo moved after packaging — **stop and report; do not repackage**, or you may install a half-finished edit.

## Report back

Per skill: installed yes/no, the `main.log` delta line quoted verbatim, all bundled files present yes/no, hash match yes/no, ledger entry cleared yes/no. Then the final `candidates` output. If any step fails, say which and stop — a partial install reported honestly is fine; a guessed one is not.
