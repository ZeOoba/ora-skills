# acquisition-underwriting changelog - v4.26 (archived 2026-10-17 under the R24-11 four-entry cap)

Full original text of the v4.26 entry, moved out of SKILL.md when v4.30 was added.

**v4.26 (2026-09-29):** **Cook County v4.25 cleanup (Gabriel, in-turn).** Chicago RCT hard cost confirmed at the C&W extract ($127.79, small tier; b 0.36221) — the row's LOW/POINT/HIGH are UNCHANGED (re-derivation gives $225.59 / $250.65 / $275.72, ±$0.01 rounding); the inline IL/Cook matrix row is removed (the row lives in `references/state-reassessment-matrix.md`, now 11 states; Cook-only rules stay inline); `market-monitor` v1.6 now carries the Cook profile; stale "confirm at merge" wording removed. Chicago still always triggers DENOMINATOR-SENSITIVE until a local GC/insurance quote lands. **No scorecard weight, Stage 1 floor, or governor constant (DSCR 1.25x / per-property LTV 65% / portfolio-aggregate LTV 40%) changed.**
