# Claude Code handoff — ora-skills repo reconciliation

**Paste this whole file as your opening prompt.** It is self-contained; you were not
present for the session that produced it.

Origin: a Cowork session on 2026-08-17 (cloud container, Desktop Commander bridge to
`laptop-cshscbe6`). That session authored a new skill, edited an existing one, hit a
stale-mirror clobber, and committed a partial fix. It could not finish the repo work
because it had no persistent repo access. You do.

---

## 0. Ground truth as of handoff

Repo: `C:\Users\Owner\ora-skills`, branch `main`.

| Fact | Value |
|---|---|
| Baseline commit before the session | `4697d8a` docs(ora-setup-audit): v1.5 |
| Commit the session made | `f2c31da` docs(package-and-stage-skill): v1.21 — **UNPUSHED** |
| `plugin_of()` for both skills in play | `None` — standalone path, not plugin members |
| Working tree at handoff | `register-scheduled-task/SKILL.md` shows ` M` with an **empty diff** (EOL churn, not a real edit) |

**Verify all of this before acting on it.** It is a report, not a guarantee.

---

## 1. What happened, and why it constrains you

The session needed to edit `package-and-stage-skill`. Working cloud-side without the
repo, it read `~/.claude/skills/synced/package-and-stage-skill/SKILL.md` — the platform
mirror — and treated it as the source.

That mirror was serving **v1.19**. The repo was already at **v1.20** (`2026-08-16`, the
Automation Audit size fix) and that commit had never been re-imported to the platform.

Result: an edit built on stale content, installed to the platform as a **second,
conflicting "v1.20"** that reverted the size fix and grew the file ~4.7 KB — on the skill
the Automation Audit had just flagged as the largest and fastest-growing of the three
measured.

Content fingerprints, LF-normalized SHA-256:

| Copy | Chars | sha256 (first 16) |
|---|---|---|
| Synced mirror (the bad basis) — v1.19 | 49,402 | `d66cc2009b24f235` |
| Repo v1.20 (genuine, 2026-08-16 size fix) | 48,342 | `3bdcc3eaecb0a523` |
| Repo v1.21 (committed `f2c31da`) | 52,337 | `9af2f56837be4f1d` |

**The repo was never written with the bad version.** Your pre-commit hook caught the
condition independently on commit — `REPO-FIRST CACHE-AHEAD: package-and-stage-skill`,
rescued the platform copy to `_staging/repo-first-rescue/package-and-stage-skill/`
(54,525 bytes, CRLF), synced the corrected file into AppData, and logged the pending
re-import. The guard worked.

**Two rules this establishes. Honor them in everything below.**

1. `~/.claude/skills/synced/` is **never** an editing basis. It serves the last
   *imported* version and silently lags any repo commit not yet re-installed.
2. A version number is **not** evidence of currency. Two different documents both
   claimed v1.20. Compare content hashes against the repo before building on anything.

---

## 2. Task 1 — Backfill `listing-agreement-qc` into the repo (primary)

The skill exists **only on the platform**. There is no repo directory. This is the
inverse of repo-first and must be corrected.

The package is already on disk:

```
C:\Users\Owner\ora-skills\_staging\2026-08-17\listing-agreement-qc.skill   (26,739 bytes)
```

Six files, forward-slash entries, no directory records:

```
listing-agreement-qc/SKILL.md
listing-agreement-qc/references/cw-form-defect-register.md
listing-agreement-qc/references/deal-folder-checklist.md
listing-agreement-qc/references/standing-positions.md
listing-agreement-qc/scripts/build_excluded_prospects.py
listing-agreement-qc/scripts/listing_qc.py
```

Do:

1. Unzip into `C:\Users\Owner\ora-skills\` so it lands at the canonical top-level dir
   `ora-skills\listing-agreement-qc\`.
2. Run the pre-flight gate (now documented as step 2a of `package-and-stage-skill`
   v1.21). Expect `name=listing-agreement-qc  description=988/1024`.
3. `python -m py_compile` both scripts.
4. Confirm it conforms to repo conventions — compare structure against `lease-form-qc`,
   which is its closest sibling (`SKILL.md` + `scripts/`). Add anything the repo expects
   that a cloud-authored skill would have missed: `.gitattributes` coverage, EOL
   handling, whatever the pre-commit hooks enforce.
5. Commit as a feature, not a doc change:
   `feat(listing-agreement-qc): v1.0 - broker listing agreement pre-execution QC gate`

**What the skill is,** so you can sanity-check it rather than trust it: a 25-check
scanner (`BLOCK`/`HIGH`/`MED`/`LOW`) over broker listing agreements on counterparty
paper where ORA is the Owner. Reads DOCX via `word/document.xml` (so it sees headers,
footers, tracked changes, and the numbering layer), PDF via `pdftotext -layout`, or raw
text. Auto-detects `SALE ONLY` vs `SALE + LEASE` scope and suppresses the lease-residue
checks (L10, L11) when a lease commission schedule is genuinely present. Checks L1–L25
each cite the standing position SP-1…SP-16 they enforce. Sibling to `lease-form-qc`
(ORA's own lease paper); distinct from `legal-intelligence` (general counterparty
analysis).

### Regression fixtures — a real gap, resolve it

The scanner was benchmarked against two live documents:

| Fixture | Expected |
|---|---|
| `Listing Agreement for Sale RL 2002 Zettler 8.13.26.docx` (sale only, unexecuted) | **18 of 25 fail** |
| `Listing Agreement for Sale and Lease Clean 4.20.2026 - 3875 E Livingston.pdf` (sale + lease, executed) | **14 of 25 fail** |
| A fully remediated ORA listing | **0 of 25** |

Neither file is on the host — both were uploaded into the cloud session. **The benchmark
is currently unreproducible.** Search OneDrive / the deal folders for them. If found,
add a fixture-based regression the way `lease-form-qc` documents its own benchmarks. If
not found, say so plainly and record the numbers as documented-but-unverified rather
than silently shipping an unrunnable benchmark.

Discriminating behaviour worth preserving in any test: L3 must **not** be satisfied by
the phrase "unaffiliated third party" (an early build had that false negative); L10/L11
must fire on the sale-only document and stay silent on the sale-and-lease one; L20 must
catch `FAIRGROUND VILLAGE CENTER LLC` vs `FAIRGROUND VILLAGE CENTER, LLC` by comparing
the entity **tail**, not the full match, or a leading document caption creates a
spurious second variant.

---

## 3. Task 2 — Verify `f2c31da`, then decide on push

`f2c31da` added step 2a to `package-and-stage-skill`, updated the `Done =` line, added
the v1.21 changelog entry, and trimmed four redundant description clauses to fit the new
text inside the 1024 cap (it landed at **1010/1024** — tight; the next feature added to
that description will need the same treatment).

Diff was 4 hunks, 22 insertions / 2 deletions. Step numbering `0`–`8` was deliberately
left untouched and the new step inserted as `2a`, because the document cross-references
step numbers throughout ("steps 5–8", "step 7", "step 0"). **Preserve that if you touch
it.**

Review the commit. If it is sound, push it — the session did not push without asking.
If you disagree with any of it, amend rather than revert; the substance is a real gap.

---

## 4. Task 3 — Reconcile `_staging/repo-first-rescue/`

Six files sit there, each rescued because a runtime cache held content never committed
on any branch:

```
exception-detection/SKILL.md                                    10,093
lease-addendum/templates/Lease_Addendum_TEMPLATE.docx           37,838
lease-form-qc/SKILL.md                                          14,498
masterlease-jurisdiction-rebase/SKILL.md                         8,336
masterlease-jurisdiction-rebase/scripts/rebase.py               17,224
package-and-stage-skill/SKILL.md                                54,525
```

The last one is **this session's bad v1.20**, fully superseded by `f2c31da` — archive it,
do not reconcile it. The other five predate this session and are unexamined. Diff each
against its repo counterpart and either commit the platform-side content or archive it
with a reason. Do not leave them undecided — a rescue directory that accumulates is a
rescue directory nobody reads.

`dirty-tree-triage` is the skill for this if attribution is unclear. Never force-resolve
contested WIP.

---

## 5. Task 4 — Clear the re-import backlog

`_staging/PENDING_REIMPORT.md` shows the platform behind the repo on four skills:

| Skill | Pending since | Commit |
|---|---|---|
| `daily-brief` | 2026-08-17T02:04Z | `e98c92f` fix(daily-brief): split incident narrative to references/, size fix |
| `ora-setup-audit` | 2026-08-17T02:13Z | `4697d8a` docs(ora-setup-audit): v1.5 |
| `package-and-stage-skill` | 2026-08-17T15:36Z | `f2c31da` v1.21 |
| `register-scheduled-task` | 2026-08-17T15:36Z | `bdba52b` v2.10 |

**This backlog is what caused the incident in section 1.** Any session that reads the
synced mirror today gets stale content for four skills. Package and stage all four so
Gabriel can clear them in one pass.

Note the platform currently holds the **bad** `package-and-stage-skill` v1.20. Gabriel
was given `_staging\2026-08-17\package-and-stage-skill.skill` (18,979 bytes, packager
output `description 1010/1024 chars OK`, `1 entries OK`) to replace it. Confirm the
replacement actually landed before clearing that ledger line — and per the ledger's own
doctrine, confirm via `main.log` non-zero `Delta: N to download` → `Sync complete`, not
via a repo-vs-cache hash, which `sync_appdata_mirror.py` makes match by construction.

---

## 6. Task 5 — Settle the working tree

`register-scheduled-task/SKILL.md` is ` M` with an empty diff — LF/CRLF churn from the
hook run, not an edit. Settle it (`git checkout --` or a renormalize, whichever the
repo's `.gitattributes` implies) so the tree is clean.

---

## 7. Task 6 — Archive the staging scratch

Per `package-and-stage-skill` v1.19's own rule, once each package's install is confirmed
and its ledger line cleared, move `_staging/2026-08-17/` to
`_archive/2026-08-17_listing-agreement-qc-and-v1.21/`. **Never delete** (Hard Invariant
6).

That directory holds this session's build scripts and both `.skill` packages:
`patch_v121.py`, `step2a_tight.md`, `changelog_v121.md`, `msg.txt`, `build.ps1`,
`commit.ps1`, `diffcheck.ps1`, `verify_basis.py`, `compare_v120.py`,
`package-and-stage-skill.skill`, `listing-agreement-qc.skill`.

Treat every `.md` in there as a **draft, not a fact** — v1.19 exists because a prior
session appended a false pre-staged draft into `event_log.md` as though it were true.
Re-derive anything you intend to log.

---

## 8. Task 7 — Memory and event log

Record in `memory/event_log.md`: the stale-mirror clobber, the two rules it established
(§1), and the `listing-agreement-qc` v1.0 authoring. The full narrative already lives in
the `package-and-stage-skill` v1.21 changelog entry — cite it rather than duplicating it.
One fact, one home.

Cross-references that already exist and should not be re-created:

- Notion Knowledge Base entry `3bf6ecd8-9e59-81a1-be27-eb3936928f5a` — "Listing
  Agreement Standing Positions v1.0 — ratified 2026-08-17" (⚖️ Legal & Compliance),
  carrying SP-1…SP-16, the C&W form defect register, and the verified parcel facts.
- A project doc `claude/listing-agreement-standing-positions.md` in the attached
  claude.ai project.

---

## 9. Constraints

- **Repo-first.** The repo leads the platform, always. Read
  `ora-skills\<skill>\SKILL.md` — never the synced mirror.
- **Never delete.** Move to `/archive/`.
- **Never overwrite a config without reading it first.**
- **`tools\package_skills.py` is the only packager.** Never `Compress-Archive` — it
  writes backslash zip entries and the importer rejects them per APPNOTE 4.4.17.1.
- **Host-shell discipline.** Every PowerShell invocation using `$` variables or spanning
  statements goes in a `.ps1` run via
  `powershell -NoProfile -ExecutionPolicy Bypass -File <path>` — never inline
  `-Command`. The session hit this failure once this run: `$` tokens are stripped in
  transit and the command arrives mangled.
- **No outbound sends.** Nothing in this handoff involves a counterparty.
- **Do not push anything except `f2c31da` and your own commits**, and only after review.

---

## 10. Done =

`listing-agreement-qc` committed at the canonical top-level dir with its pre-flight gate
reported (`name` + `description N/1024`) and scripts compiling · fixture regression
either wired up or its absence stated explicitly · `f2c31da` reviewed and pushed or
amended · all six `repo-first-rescue` files committed or archived with a reason, none
left undecided · all four `PENDING_REIMPORT` skills packaged and staged, each ledger line
cleared only on `main.log` evidence · working tree clean · `_staging/2026-08-17/` moved
to `_archive/` · `event_log.md` updated from re-derived facts, not from the staged
drafts.

---

## 11. If you want the business artifacts

The same session produced deliverables for the underlying deal (2000-2002 Zettler Rd
listing agreement review, verification addendum, Excluded Prospects exhibit, QC report,
and a held draft email to Cushman & Wakefield). They live in the Cowork session, not on
disk. They are ORA deal-folder material, not repo material — ask Gabriel if you want them
filed.
