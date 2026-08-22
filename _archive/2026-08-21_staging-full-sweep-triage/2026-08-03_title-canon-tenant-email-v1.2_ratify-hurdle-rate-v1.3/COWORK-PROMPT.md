# Cowork prompt — install 3 skills (paste everything below the line)

---

Install three ORA skills whose repo content is ahead of the Cowork runtime cache. All three are already committed and pushed; only the Save-skill click is outstanding.

**Packages** (all single-file, so either Save skill or Settings → Capabilities works):

```
C:\Users\Owner\ora-skills\_staging\2026-08-03_title-canon-tenant-email-v1.2_ratify-hurdle-rate-v1.3\
    tenant-email.skill
    ratify-hurdle-rate.skill
    document-assembly.skill
```

Each was packaged by `tools/package_skills.py` and verified byte-identical to its committed repo file. Do **not** repackage or edit them — if a hash check disagrees, stop and report rather than rebuilding.

## What changed and why it matters

`tenant-email` **v1.2** and `ratify-hurdle-rate` **v1.3** (commit `edc9fa1`) both stamped Gabriel as *"Principal"*, contradicting CLAUDE.md's ratified identity, **"VP Acquisitions"**. tenant-email's is the literal signature block embedded in every outbound tenant draft; ratify-hurdle-rate's is the "Ratified by:" line on a governance audit memo. Both now read "VP Acquisitions".

`document-assembly` (commit `74120f6`, authored by a different session) adds an explanatory bullet recording that its signing-authority line is **deliberately exempt** from that ruling — `"Gabriel Goldberg, Member / Principal"` there is the capacity in which Gabriel binds an LLC, not his firm title. **Do not "correct" it.** It is included here only because its SKILL.md changed and the runtime cache is stale.

## Steps

1. **Confirm the three files exist** at the path above and report their sizes.
2. **Surface each `.skill`** so its Save-skill control appears, and ask Gabriel to click it. Three separate clicks. Nothing here can be automated — the click is manual by design.
3. **After the clicks, verify the install properly.** In priority order:
   - **`%APPDATA%\Roaming\Claude\logs\main.log`** — look for a non-zero `Delta: N to download` followed by `Sync complete`. This is the authoritative signal: the repo→cache file copy done at commit time produces *no* SkillsPlugin log activity, so a non-zero delta cannot be manufactured by tooling.
   - Then mtime of each `SKILL.md` under
     `%APPDATA%\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills\<skill>\`
     against a pre-click baseline.
   - Then SHA-256 of each cached `SKILL.md` vs `C:\Users\Owner\ora-skills\<skill>\SKILL.md`. This confirms **what** installed, never **whether**.

   ⚠️ **`_staging\PENDING_REIMPORT.md` is NOT an install oracle.** It is cleared by hand *after* the fact, so an entry means only "nobody has cleared it yet" — never "not installed". On 2026-08-03 a session read that ledger two minutes after a confirmed click and wrongly reported the skill uninstalled. Check `main.log` first.

4. **Only after a confirmed re-sync**, clear the ledger:

```powershell
cd C:\Users\Owner\ora-skills
python tools\pending_reimport.py clear tenant-email
python tools\pending_reimport.py clear ratify-hurdle-rate
python tools\pending_reimport.py clear document-assembly
```

   Clearing the last entry deletes `PENDING_REIMPORT.md` entirely — that is expected, not an error.

5. **Spot-check the content actually landed.** In the installed `tenant-email\SKILL.md`, confirm the signature block reads `Gabriel Goldberg, VP Acquisitions` and that no `Goldberg, Principal` remains. In the installed `document-assembly\SKILL.md`, confirm `Member / Principal` is still present — it is correct there.

## Boundaries

- **Do not edit any SKILL.md.** If content looks wrong, report it; a Cowork-side edit creates the repo-vs-cache drift this process exists to close.
- **Do not commit or push.** All three commits are already on `origin/main`.
- **You cannot write `event_log.md`** — `~/.claude` is fail-closed to Cowork. Report the outcome and a Claude Code session will log it.
- `document-assembly` has related probe work in flight under another session's claim (`bd37c567`). If its content differs from what is described here, stop and report rather than reconciling.

## Report back

Per skill: installed yes/no, the `main.log` delta line quoted verbatim, hash match yes/no, and whether the ledger entry was cleared. If any step fails, say which and stop — a partial install is fine to report; a guessed one is not.
