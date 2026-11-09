# Design note: `--loi-conformance` rent-escalation check (parked 2026-11-09)

Status: PARKED for design review. This branch (`parked/lease-form-qc-escalation-design-review`)
is pushed and has no PR. Audit row: `leaseqc-checkrent-escalation-failopen`.

## Why it is parked

Five adversarial REFUTE rounds (Opus) rejected each regex-on-prose version of
`_check_rent`'s fixed-% escalation match. Every fix opened a new false CONFORMS or a false
block on ORA's own master form: a nearby % from another clause (proportionate share,
management fee, expense cap, late charge, default rate), a step clause that does not repeat
"rent", abbreviation and `:` splitting, BLI blocks with no punctuation, and the "adjusted"
condemnation clause. Matching prose percentages to decide CONFORMS is the wrong tool.

What is settled and can ship separately: an escalation block the checker cannot verify
(`fixed_pct` with no usable value, or a missing/unknown `type`) returns PARTIAL, never
CONFORMS (the first fix on this branch).

## Proposed design

1. **Primary check is schedule arithmetic.** Reuse `_d2` (rent-schedule arithmetic: each
   row reproduces from row 1 to the cent under annual-compounded or monthly-rounded
   compounding). For `fixed_pct`, the register's rate is fed to `_d2` as `e`. A schedule
   that reproduces at the register rate is the only route to CONFORMS.
2. **Prose percentages are a cross-check only.** Percentages read from rent-escalation
   prose can only lower the verdict, never raise it.
3. **Any disagreeing percentage is CONFLICT.** If a percentage read as a rent escalation
   differs from the register value, the row is CONFLICT, even when the schedule reproduces
   and the register value also appears.
4. **A step clause with no percentage is PARTIAL.** For example: "increases as set forth in
   the schedule" with no schedule found, "103% of the prior Lease Year", or a CPI tie.
5. **Never CONFORMS from prose alone.** If no schedule is found, the best possible result is
   PARTIAL (verify by hand), whatever the prose says.

## Open questions for review

- Does the register ever carry a rate without a schedule (option years only)? If so, should
  option-year rows be computed from the register before running `_d2`?
- Should the cross-check be limited to the RENT section (heading-anchored) rather than
  sentence heuristics, now that the master form's section titles are stable?

## Evidence

- REFUTE probes p1-p8, rr3_add, rr4_lq and rr4_add are in the orchestrator's session
  scratchpad.
- The round-1 to round-4 repros are pinned as tests in `tests/test_lease_qc.py` on this
  branch.
