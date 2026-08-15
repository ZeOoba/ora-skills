---
name: owner-outreach
description: Oxford Realty Advisors weekly off-market owner cold-outreach pipeline. Use whenever the user mentions owner outreach, off-market letters, T1 letter pack, cold outreach queue, owner mailing, motivated seller outreach, off-market owner letters, or asks to refresh/run/check the weekly owner-outreach cycle -- even if they just say "run outreach" or "what's in the owner outreach queue this week." Promotes qualifying parcels from the off-market master (built by parcel-data-recovery / acquisition-underwriting off-market screens) into a dated queue, dedups against the Notion Owner Outreach ledger, drafts T1 cold-outreach letters on ORA letterhead, and reports promoted/net-new counts. DRAFT ONLY -- this is outbound counterparty communication (Hard Invariant 1); nothing is ever sent without Gabriel's explicit confirmation. v1.2 (2026-08-15: see Changelog).
metadata:
  type: ora-operations
---

# Owner Outreach — Oxford Realty Advisors (off-market cold-outreach pipeline)

Weekly refresh of the T1 (first-touch) owner-outreach cycle: off-market master → queue → Notion dedup →
letter pack. Three scripts live in the project folder and do the real work — this skill's job is to run
them in the right order, in the right mode, and to stop at the right point.

**Outbound counterparty communication — DRAFT ONLY.** Per Hard Invariant 1, nothing in this pipeline is
ever sent without Gabriel's explicit in-turn confirmation. A scheduled run produces a drafted, reviewable
letter pack plus a Notion create-pages payload staged for the agent to push — never an auto-send.

## Scripts (fixed paths — the pipeline's actual location, not bundled resources)

All three live in `C:\Users\Owner\OneDrive - Oxford Capital Partners\Business\Investment Candidates -- 2026\`
(path corrected 2026-08-14 -- this doc had dropped the `Business\` segment the scripts themselves fixed
on 2026-07-21):
`owner_outreach_queue.py`, `build_t1_letterpack.py`, `owner_outreach_weekly.py`. Run them from that
folder via `owner_outreach_weekly.py` (the orchestrator) — do not call the queue/letter scripts directly
except for debugging a single step. These are deliberately NOT bundled into this skill package: they are
tightly coupled to that project folder's live data (the off-market master, `owner-outreach-ledger.csv`,
`mailing-overrides.csv`, `principal-overrides.csv`, `mail-log.csv`, `target-markets.json`) and bundling a
copy would create exactly the kind of sync-drift this skill exists to prevent. If the scripts and this
SKILL.md ever disagree about behavior, the scripts are the source of truth — re-read them before acting
on a stale description here.

## Workflow

1. **Scan run:** `python owner_outreach_weekly.py` (no flags). Corrected 2026-08-14 -- this step
   previously (wrongly) documented `--strict-age` as always-on. Per the 2026-07-12 relax, the queue
   script's staleness check is **WARN-only by default**: a stale upstream off-market master (>7 days)
   prints loudly in stdout/the run summary but does not halt the run. Report a STALE flag plainly if it
   appears; it is expected, not a bug -- `--strict-age` still exists on the queue script directly for
   anyone who wants the hard halt back, but the weekly orchestrator no longer passes it.
   Every scan run also applies the 2026-08-14 cadence gate (below) automatically. `--wave-cap N` is
   **opt-in, not automatic** -- pass it explicitly (`python owner_outreach_weekly.py --wave-cap 50`)
   to cap the pack at the top-N eligible letters; omitted, the full eligible queue renders as before.
2. On success, it produces: a dated queue (`YYYYMMDD_Owner-Outreach-Queue_Phase1_v01.xlsx`), a net-new
   Notion payload (`_oo_netnew_pages.json`), and a letter pack
   (`YYYYMMDD_Owner-Outreach_T1-Letter-Pack_Phase1_v01.docx`) — the letter pack generation includes a
   built-in letter-count integrity check (compares the DOCX's letter count against the promoted
   Tier-0-ready count) and will itself hard-fail if they don't match; the weekly orchestrator now
   propagates that failure instead of reporting success on a broken pack.
3. **Notion stage (agent, not script):** read `_oo_netnew_pages.json` and create the net-new pages in the
   Notion Owner Outreach Queue DB via MCP. The script never writes to Notion directly.
4. **Commit:** once the Notion push succeeds, run `python owner_outreach_weekly.py --commit` to append
   those parcels to `owner-outreach-ledger.csv` so next week's dedup is correct. Do not commit before
   confirming the Notion push succeeded — a false commit will silently swallow real net-new parcels next
   week.
5. **Report:** route the run summary (rows scanned, promoted, net-new by market, RECOVER gaps, upstream
   master age, integrity-check result) to `ggoldberg@oxfordra.net` ONLY, per routing canon. **Do not**
   release or send the letter pack itself — that is a separate, explicit action Gabriel takes.

## What changed 2026-07-11 (read before assuming old behavior)

The scripts were audited and patched against real defects found in the two manual runs (2026-06-15,
2026-06-22):
- Both scripts pointed at a OneDrive folder path with a stray `(1)` duplicate-folder suffix that does
  not exist on this machine — every run would have failed to even find the master file until fixed.
- `owner_outreach_queue.py`'s market-priority ranking only covered 4 of ORA's 9 target clusters
  (Cincinnati and Kansas City — both established/primary — silently ranked last). It now reads
  `target-markets.json` at run time (established clusters rank ahead of entry-phase), falling back to a
  corrected static list only if that file is unreadable.
- `owner_outreach_weekly.py`'s Notion-category `METROS` set was missing Kansas City and Cincinnati.
- The letter-pack signature block was signing "Oxford Capital" with no email — stale relative to the
  `communication-intelligence` standard (Gabriel Goldberg / Oxford Realty Advisors /
  ggoldberg@oxfordra.net, ratified 2026-07-08). Corrected; phone and street-address footer unchanged.
- The 2026-06-22 run silently re-processed a 12-day-stale master and reported an uninformative
  zero-net-new result instead of halting. `--strict-age` is now always passed by the orchestrator.
  (Superseded 2026-07-12 -- see below; this bullet is kept as history, not current behavior.)
- A real silent-corruption incident (2026-06-15 pack: PDF had 59 letters, the same-named DOCX re-saved
  four days later had 44) prompted the letter-count integrity check in step 2 above.

## What changed 2026-08-14

Four changes landed today; two are code, two are corrections to this doc which had drifted out of sync
with the scripts.

- **Cadence gate (code, earlier today via Cowork).** The pack previously rendered the FULL current queue
  every scan, so a weekly release re-mailed every owner (the 07-13/21/27 packs were identical).
  `owner_outreach_weekly.py` now tracks actual mail events in `mail-log.csv` (populated by
  `python owner_outreach_weekly.py --released [YYYY-MM-DD]`, run after Gabriel physically mails a pack)
  and holds any parcel mailed within the last 21 days (`MIN_TOUCH_GAP_DAYS`) out of the next pack via
  `build_t1_letterpack.py --exclude`. `_oo_pack_manifest.json` records exactly which parcels a given pack
  contains, so `--released` logs the right set. `mail-log.csv` starts empty -- Gabriel must seed it with
  any packs physically mailed before 2026-08-14 or that history is unknown to the gate.
- **Named salutations (code).** `principal-overrides.csv` (beside `mailing-overrides.csv`; columns
  `parcel_id, salutation_name, confidence, source, verified_date`; hand/agent-maintained from the
  recorder worksheet + Notion Principals DB, never auto-resolved) now drives the letter salutation.
  `Verified`/`Probable` confidence renders `Dear {salutation_name},`; everything else falls back to
  `Dear Owner of {SiteAddress},`. The generic `Dear Property Owner` salutation is retired -- if it ever
  appears in a saved pack, the letter script hard-fails, same severity as the letter-count integrity
  check.
- **`--wave-cap N` (code).** `build_t1_letterpack.py --wave-cap N` and `owner_outreach_weekly.py
  --wave-cap N` (passthrough) cap a pack at the top-N eligible letters by Screen Score (tiebreak P1 %) --
  sized for the ~50/week hand-addressing budget. Deferred rows are reported on the cover page as
  "Deferred (wave cap)", distinct from cadence-held rows, and the same cap is applied when writing
  `_oo_pack_manifest.json` so the manifest matches what was actually rendered. Opt-in, not automatic.
- **Doc corrections (this file only, no code change).** The `Scripts` path above was missing the
  `Business\` segment the scripts themselves corrected on 2026-07-21, and step 1 above wrongly described
  `--strict-age` as still always-on after the 2026-07-12 relax to WARN-only. Both fixed today.

**Still pending (not done, don't assume otherwise):** a full v2.0 rewrite of this doc (Gabriel's own
change list also calls for dropping the version to a clean "v2.0" once landed) and T2--T4 multi-touch
rendering (`build_t1_letterpack.py --touch N`, body text sourced from a not-yet-supplied sequence-
templates doc). Both are blocked on source files Gabriel has not yet provided in-session -- verify they
still say "pending" before assuming either shipped.

## Guardrails

- This is the T1 (first-touch) stage only. Second-stage conversation structures (extended-1031-study
  leaseback, installment sale/seller carry, objection handling) are documented in
  `2026-06-15_Owner-Outreach_Creative-Structures-and-Objections_v01.md` in the project folder and are
  NOT encoded in this skill — treat that file as the playbook once a T1 letter gets a response, don't
  improvise past it.
- Standard firm name in outbound mail is "Oxford Realty Advisors" (current as of 2026-07-08) — verify
  this hasn't moved again against `communication-intelligence`'s signature-block canon before a live
  run, the same way the 2026-06-15 draft went stale on this exact point.
- `mailing-overrides.csv` and `principal-overrides.csv` are live, hands-on-keyboard patch files
  (address recovery and named salutations respectively) — treat entries there as authoritative
  overrides, never auto-resolved or auto-generated.
- Never fabricate a mailing address, an owner name, or a salutation name/confidence. Rows without a
  verified mailing address are reported as `[RECOVER]` and skipped from the letter pack, not guessed at;
  rows without a `Verified`/`Probable` `principal-overrides.csv` entry fall back to the generic
  address-anchored salutation, never an invented name.

## Known remaining gap (flag, don't silently fix)

No automated trigger yet forces the upstream off-market master (`AllMarkets-OffMarket-Master`) to
refresh on a cadence that keeps this skill's weekly run meaningful — that refresh is
`parcel-data-recovery`/`acquisition-underwriting` off-market screening territory, out of this skill's
scope. Until that's addressed, expect this pipeline to legitimately halt most weeks on a stale-master
FATAL rather than produce a queue. Report the halt and the master's age plainly rather than working
around it.

## Changelog

- v1.2 (2026-08-15): LOW fix (Skill Text Audit finding F9). Moved the v1.1/v1.0 changelog prose that had accumulated in the frontmatter `description` field down here — this is the first `## Changelog` heading in this file (the existing "What changed 2026-07-11" / "What changed 2026-08-14" sections above remain as the detailed operational history; this section is the short version-tag log matching other skills' convention). Description now carries a single trailing version tag. No pipeline logic, cadence-gate behavior, or trigger vocabulary changed.
- v1.1 (2026-08-14): Cadence gate (`mail-log.csv` / `MIN_TOUCH_GAP_DAYS`), named salutations (`principal-overrides.csv`), and `--wave-cap N` landed; `Scripts` path and `--strict-age` doc description corrected. v2.0 rewrite and T2-T4 multi-touch rendering still pending. Full detail: "What changed 2026-08-14" above.
- v1.0 (2026-07-11): Built from the three project scripts; audited and patched against defects found in the 2026-06-15/2026-06-22 manual runs. Full detail: "What changed 2026-07-11" above.
