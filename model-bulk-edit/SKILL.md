---
name: model-bulk-edit
description: "Safely change the same input across many ORA financial models at once, and audit workbooks whose formulas carry no cached values. Use when the user says: rebase the models, update the refi rate everywhere, change an assumption across all deals, bulk edit workbooks, propagate a constant to the models, sweep the underwriting models, or after any UNDERWRITING CONVENTIONS constant moves in acquisition-underwriting. Also the SOLE path for the cached-value audit -- trigger on: nulls in the QC gate, model reads blank, dead workbook, formulas but no values, why is DSCR empty. Encodes: archive-then-verify before any write, Excel COM with CalculateFullRebuild (NEVER openpyxl for writes -- it silently destroys every cached value), constant-vs-formula pre-check, and a mandatory post-write diff of every model against its archived original. Historical models for closed or passed deals are rebased only on Gabriel's explicit instruction. v1.0"
---

# model-bulk-edit — Oxford Realty Advisors

One input, many workbooks. This skill exists because the dangerous part of a bulk model
edit is never the edit — it is the write mechanism, the models you did not know existed,
and the ones whose verdict quietly moves.

**DRAFT-SAFE, NOT DECISION-SAFE.** This skill changes numbers that decisions were made on.
It never runs unprompted. Hard Invariant 4 governs: modifying financial models requires
Gabriel's explicit instruction, and that instruction covers the models named in it, not
every model the sweep happens to find.

## STEP 0 — Scope, and the historical-record question (ask BEFORE editing)

Enumerate candidates first and classify each as **live** (active pipeline, still being
underwritten) or **historical** (closed, passed, or superseded). A historical model is the
record of a decision that was actually made on the old assumption — rebasing it rewrites
that record. Notion's score-snapshot doctrine ("IMMUTABLE — re-scores get new rows, never
overwrite history") is the standing analogue.

Default: rebase live models, leave historical ones, and **report the split rather than
resolving it silently**. Gabriel may direct otherwise; a blanket "do them all" is a valid
instruction and is then simply followed — but the split still gets reported so he knows
what the instruction covered.

## STEP 1 — Constant or formula? (never skip)

For every target cell, open with `openpyxl.load_workbook(path, data_only=False)` and read
the *stored* value. A literal (`0.07`) is safe to overwrite. A formula (`=Inputs!$B$38`) is
a **dependent** — it follows its precedent and must NOT be written; overwriting it severs
the link and creates a second source of truth. Record which is which before any write.

Also capture, per model: the value cell's exact coordinate, its number format (a rate stored
as `0.07` under a `0.00%` format is 7%, not 7 basis points of confusion), and the label text
you matched on, so the mapping is auditable afterward.

## STEP 2 — Archive, hash-verified, BEFORE any write

Copy each original to `_archive\<YYYY-MM-DD>_<change-slug>\` beside the file itself, then
SHA256 both copies and assert equality. Never delete, never move the original out of place
(Hard Invariant 6). The archive is not a courtesy — STEP 5's diff is computed against it,
so a missing archive means the change cannot be verified at all.

## STEP 3 — Write via Excel COM. NEVER openpyxl.

**This is the rule the whole skill exists for.** `openpyxl` round-trips preserve formulas but
**discard every cached value in the workbook**. The models then read `None` to any consumer
using `data_only=True` — which is exactly what ORA's own QC Gate does — until a human opens
each file in Excel and saves it. A silent, portfolio-wide degradation.

```powershell
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
$xl.AskToUpdateLinks = $false; $xl.EnableEvents = $false
$wb = $xl.Workbooks.Open($path, 0, $false)
$cell = $wb.Worksheets.Item($sheet).Range($addr)
if ([Math]::Abs([double]$cell.Value2 - $expectedOld) -gt 1e-7) { <# SKIP, report #> }
$cell.Value2 = $newValue
$xl.CalculateFullRebuild()      # not Calculate() -- rebuild the dependency tree
$wb.Save(); $wb.Close($false)
```

**Assert the old value before writing it.** A cell that does not hold what you expected is a
mapping error, not an edit target — skip it and report, never write through the surprise.
`CalculateFullRebuild()` rather than `Calculate()`: the latter can leave stale dependents when
the tree itself changed.

Host-shell discipline applies (same rule as `package-and-stage-skill` step 3): run this from a
`.ps1` file via `powershell -NoProfile -ExecutionPolicy Bypass -File <path>`, never an inline
`-Command` one-shot — `$` tokens are stripped in transit. PowerShell 5.1 has no `&&`.

## STEP 4 — Long sweeps outrun the tool timeout

A recursive Excel/openpyxl walk over the Business tree takes minutes and the MCP call caps out
around 60s. Launch detached and poll a file rather than re-running and hoping:

```powershell
Start-Process -FilePath python -ArgumentList @($script,$root,"--quiet") `
  -RedirectStandardOutput $out -RedirectStandardError $err -NoNewWindow
```

## STEP 5 — Diff every model against its archived original

Re-read live and archived copies with `data_only=True` and report, per model: the target cell
old → new, every metric that moved, and **explicitly, every metric that did not**. An unmoved
metric is a finding, not an absence of one — when refi proceeds hold flat under a rate cut, the
LTV ceiling is binding rather than DSCR, which is real information about the deal.

Then run the floor tests: for every DSCR row, report `PASS/BREACH` before and after and flag
any **floor state change**. A rebase that flips a Stage 1 floor has changed a verdict, and that
goes to Gabriel as a finding, not into a summary line.

Confirm `0 null cached values` across every touched workbook. If any appear, STEP 3 was done
wrong — fix the mechanism, do not paper over it by hand.

## STEP 6 — Cached-value audit (also runs standalone)

`scripts/cached_value_lint.py <root> [--quiet] [--json]` classifies every workbook:

| verdict | meaning |
|---|---|
| `OK` | formulas present, cached values present |
| `DEAD` | formulas present, **zero** cached — QC Gate reads nulls here |
| `PARTIAL` | some region never calculated |
| `NO-FORMULAS` | data-only sheet, nothing to cache |
| `UNREADABLE` | openpyxl could not open it — **unchecked, not clean** |

Exit 1 if anything is DEAD or PARTIAL. Remedy is Excel COM (or open-and-save), never an
openpyxl re-save — that is the cause, not the cure.

**`UNREADABLE` is not a pass.** Report the count every time. A sweep that says "no dead
workbooks" while 14 files failed to open has audited nothing about those 14.

## Done =

scope enumerated and split live-vs-historical, with the split REPORTED · every target cell
classified constant-vs-formula, dependents left alone · originals archived to
`_archive\<date>_<slug>\` and SHA256-verified before the first write · written via Excel COM
with `CalculateFullRebuild()`, never openpyxl · old value asserted per cell, surprises skipped
and reported · every touched model diffed against its archive, unmoved metrics reported
alongside moved ones · DSCR floor state reported before/after with any change flagged ·
`0 null cached values` confirmed · `UNREADABLE` count stated · an audit record written into the
archive folder naming authority, method, per-model deltas, and what was deliberately not done.

## Changelog

- v1.0 (2026-08-22): initial. Extracted from the refi-rate rebase (7.00% → 6.50%, 10 workbooks),
  which established every rule above the hard way: the openpyxl cached-value trap (caught before
  the write, not after), the constant-vs-formula pre-check (`125DouglasPike` Sensitivity!B9 is a
  dependent), the unmoved-metric finding (LTV binds, not DSCR), and `125DouglasPike` v2.0 sitting
  DEAD with null DSCRs that no QC run would have surfaced — which is what `cached_value_lint.py`
  now exists to catch.
