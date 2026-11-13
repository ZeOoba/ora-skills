"""stdlib unittest suite for memo_tieout (synthetic fixtures only — no firm data)."""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import memo_tieout as mt  # noqa: E402


def make_docx(path: Path, paragraphs):
    body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{escape(p)}</w:t></w:r></w:p>' for p in paragraphs)
    doc = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
           f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", doc)


def make_xlsx(path: Path, rows, pct_cells=(), formula_only=False):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"
    for r, (label, value) in enumerate(rows, start=1):
        ws.cell(row=r, column=1, value=label)
        c = ws.cell(row=r, column=2, value=("=1+1" if formula_only else value))
        if label in pct_cells:
            c.number_format = "0.00%"
    wb.save(path)


MODEL = [("Purchase Price", 1150000), ("Year 1 NOI", 96432.18), ("Going-in Cap Rate", 0.08386),
         ("DSCR", 1.3167), ("LTV", 0.60), ("Levered IRR", 0.1412), ("Rentable SF", 24500),
         ("Equity Multiple", 2.08)]
PCT = ("Going-in Cap Rate", "LTV", "Levered IRR")


class TieOutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.model = self.tmp / "ORA_IRR_Test_v1.0.xlsx"
        make_xlsx(self.model, MODEL, PCT)

    def _run(self, paras, memo_name="Test_ICMemo_v1.0.docx"):
        memo = self.tmp / memo_name
        make_docx(memo, paras)
        return mt.run(memo, self.model)

    def status(self, results):
        return [(r.claim.text, r.status) for r in results]

    def test_rounded_display_ties(self):
        res, _, warn = self._run(["Bid of $1.15M at a 8.39% cap rate, DSCR 1.32x, 60% LTV, IRR 14.1%."])
        self.assertEqual({s for _, s in self.status(res)}, {"TIED"}, self.status(res))
        self.assertEqual(warn, [])

    def test_full_digit_money_and_sf(self):
        res, _, _ = self._run(["NOI of $96,432 on 24,500 SF."])
        self.assertEqual([s for _, s in self.status(res)], ["TIED", "TIED"])
        self.assertEqual(res[1].claim.kind, "sf")

    def test_conflict_on_labelled_metric(self):
        res, _, _ = self._run(["The deal clears a DSCR of 1.45x."])
        self.assertEqual(res[0].status, "CONFLICT")
        self.assertEqual(res[0].cell, "Summary!B4")

    def test_untied_unlabelled(self):
        res, _, _ = self._run(["Closing costs of $37,250 were assumed."])
        self.assertEqual(res[0].status, "UNTIED")

    def test_near_is_reported_not_tied(self):
        # $96,600 is within 0.5% of 96,432 but outside $0.5 rounding of a full-digit figure.
        res, _, _ = self._run(["NOI of $96,600."])
        self.assertEqual(res[0].status, "NEAR")

    def test_scale_suffixes(self):
        res, _, _ = self._run(["Price $1,150K", "Price $1.15 million"])
        self.assertEqual([r.status for r in res], ["TIED", "TIED"])
        self.assertEqual(res[1].claim.value, 1_150_000)

    def test_pct_rounding_precision(self):
        # 8.4% (1 decimal) ties 0.08386; 8.40% (2 decimals) must not.
        res, _, _ = self._run(["cap rate 8.4%", "cap rate 8.40%"])
        self.assertEqual(res[0].status, "TIED")
        self.assertNotEqual(res[1].status, "TIED")

    def test_version_mismatch_warning(self):
        _, _, warn = self._run(["Bid $1.15M"], memo_name="Test_ICMemo_v2.0.docx")
        self.assertTrue(any("version mismatch" in w for w in warn))

    def test_ignore_pattern(self):
        memo = self.tmp / "m.docx"
        make_docx(memo, ["Bid $1.15M and 2026 vacancy of 5%"])
        res, _, _ = mt.run(memo, self.model, ignore=[r"^5%$"])
        self.assertEqual([r.claim.text for r in res], ["$1.15M"])

    def test_uncached_formulas_refuse(self):
        bad = self.tmp / "uncached.xlsx"
        make_xlsx(bad, MODEL, formula_only=True)
        memo = self.tmp / "m.docx"
        make_docx(memo, ["Bid $1.15M"])
        with self.assertRaises(RuntimeError):
            mt.run(memo, bad)
        self.assertEqual(mt.main([str(memo), str(bad)]), 2)

    def test_exit_codes(self):
        memo = self.tmp / "ok.docx"
        make_docx(memo, ["Bid $1.15M, DSCR 1.32x"])
        out = self.tmp / "r.md"
        self.assertEqual(mt.main([str(memo), str(self.model), "--out", str(out)]), 0)
        self.assertIn("PASS", out.read_text(encoding="utf-8"))
        make_docx(memo, ["DSCR 1.60x"])
        self.assertEqual(mt.main([str(memo), str(self.model), "--out", str(out)]), 1)
        self.assertIn("FAIL", out.read_text(encoding="utf-8"))
        self.assertEqual(mt.main([str(self.tmp / "missing.docx"), str(self.model)]), 2)

    def test_transposition_hint(self):
        # Model NOI 96,432.18 -> memo "$96,342" is a two-digit swap.
        res, _, _ = self._run(["NOI of $96,342."])
        self.assertNotEqual(res[0].status, "TIED")
        self.assertIn("transposition", res[0].note)
        self.assertIn("Summary!B2", res[0].note)

    def test_range_endpoint_never_conflict(self):
        res, _, _ = self._run(["market DSCR band 1.40x–1.60x"])
        self.assertEqual([r.status for r in res], ["UNTIED", "UNTIED"])
        self.assertTrue(all("range endpoint" in r.note for r in res))

    def test_approximate_figure_never_conflict(self):
        res, _, _ = self._run(["NOI leakage of ~$100K and DSCR of approximately 1.50x"])
        self.assertEqual([r.status for r in res], ["UNTIED", "UNTIED"])
        self.assertTrue(all(r.claim.approx for r in res))

    def test_table_cell_borrows_previous_label(self):
        res, _, _ = self._run(["DSCR", "1.45x"])
        self.assertEqual(res[0].claim.metric, "dscr")
        self.assertEqual(res[0].status, "CONFLICT")

    # ---- adversarial-review regressions (RE-4.47-1 refute pass) ----
    def _model(self, rows, pct=()):
        path = self.tmp / f"m{len(list(self.tmp.iterdir()))}.xlsx"
        make_xlsx(path, rows, pct)
        return path

    def _memo(self, paras):
        path = self.tmp / f"memo{len(list(self.tmp.iterdir()))}.docx"
        make_docx(path, paras)
        return path

    def test_threshold_cell_never_ties_a_result_claim(self):
        model = self._model([("Min DSCR", 1.25), ("Max LTV", 0.65), ("DSCR", 1.10), ("LTV", 0.72)],
                            ("Max LTV", "LTV"))
        res, _, _ = mt.run(self._memo(["The deal runs a DSCR of 1.25x at 65% LTV."]), model)
        self.assertEqual([r.status for r in res], ["CONFLICT", "CONFLICT"], [(r.claim.text, r.cell) for r in res])

    def test_threshold_claim_may_tie_threshold_cell(self):
        model = self._model([("Min DSCR", 1.25), ("DSCR", 1.10)])
        res, _, _ = mt.run(self._memo(["The DSCR floor of 1.25x is breached."]), model)
        self.assertEqual(res[0].status, "TIED")

    def test_labelled_claim_ignores_unlabelled_coincidence(self):
        model = self._model([("Going-in Cap Rate", 0.075), ("Base Rent $/SF", 8.40),
                             ("Year 1 NOI", 310000), ("Total Opex", 250000)], ("Going-in Cap Rate",))
        res, _, _ = mt.run(self._memo(["cap rate of 8.40%", "NOI of $250,000"]), model)
        self.assertEqual([r.status for r in res], ["CONFLICT", "CONFLICT"])

    def test_unlabelled_claims_skip_count_and_year_cells(self):
        model = self._model([("Tenant count", 12), ("Analysis year", 2000), ("Hold (years)", 5)])
        res, _, _ = mt.run(self._memo(["Leased 12% today, about $2K reserve, 5x return."]), model)
        self.assertNotIn("TIED", [r.status for r in res], [(r.claim.text, r.cell) for r in res])

    def test_pct_div100_path_needs_percent_label(self):
        model = self._model([("Base Rent $/SF", 8.40), ("Rent growth (%)", 3.0)])
        res, _, _ = mt.run(self._memo(["a figure of 8.40% and growth of 3%"]), model)
        self.assertEqual([r.status for r in res], ["UNTIED", "TIED"])

    def test_any_uncached_formula_refuses_unless_allowed(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        for r, (k, v) in enumerate([("Price", 1150000), ("NOI", 96000), ("DSCR", "=B2/80000")], 1):
            ws.cell(row=r, column=1, value=k)
            ws.cell(row=r, column=2, value=v)
        p = self.tmp / "partial.xlsx"
        wb.save(p)
        memo = self._memo(["Bid $1.15M"])
        with self.assertRaises(RuntimeError):
            mt.run(memo, p)
        res, uncached, _ = mt.run(memo, p, allow_uncached=True)
        self.assertEqual(uncached, 1)
        self.assertEqual(mt.main([str(memo), str(p)]), 2)

    def test_unreadable_memo_is_input_error(self):
        bad = self.tmp / "badxml.docx"
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("word/document.xml", "<w:document")
        nodoc = self.tmp / "nodoc.docx"
        with zipfile.ZipFile(nodoc, "w") as z:
            z.writestr("x.txt", "hi")
        renamed = self.tmp / "renamed.docx"
        renamed.write_bytes(self.model.read_bytes())
        empty = self._memo(["No figures in this memo at all."])
        for memo in (bad, nodoc, renamed, empty):
            self.assertEqual(mt.main([str(memo), str(self.model)]), 2, memo.name)

    def test_out_path_never_overwrites_inputs(self):
        memo = self._memo(["Bid $1.15M"])
        before = memo.read_bytes()
        self.assertEqual(mt.main([str(memo), str(self.model), "--out", str(memo)]), 2)
        self.assertEqual(mt.main([str(memo), str(self.model), "--json", str(self.model)]), 2)
        self.assertEqual(memo.read_bytes(), before)

    def test_more_range_and_estimate_forms(self):
        res, _, _ = self._run(["Price range $1.1M–$1.2M", "DSCR between 1.40x and 1.60x",
                               "DSCR estimated at 1.50x"])
        self.assertNotIn("CONFLICT", [r.status for r in res], [(r.claim.text, r.status) for r in res])

    def test_sf_variants_sign_and_false_multiples(self):
        res, _, _ = self._run(["24,500 RSF and 24.5K SF and 24,500 s.f. and 24,500-SF",
                               "a loss of ($50,000) and -$50K", "a 50x100 lot with 10 x 20 bays"])
        kinds = [(r.claim.kind, r.claim.value) for r in res]
        self.assertEqual(kinds, [("sf", 24500.0)] * 4 + [("money", -50000.0)] * 2, kinds)

    def test_years_and_plain_numbers_ignored(self):
        claims = mt.extract_claims(["Built in 1985, acquired 2026, 3 buildings."], [])
        self.assertEqual(claims, [])

    def test_large_value_under_year_header_still_ties(self):
        model = self._model([("Exit Year Price", 11000000)])
        res, _, _ = mt.run(self._memo(["Target $11.0M"]), model)
        self.assertEqual(res[0].status, "TIED")

    def test_keyword_owned_by_earlier_figure_does_not_bind(self):
        claims = mt.extract_claims(["Debt at LTV 65%, 6.0% coupon."], [])
        self.assertEqual([c.metric for c in claims], ["ltv", None])
        claims = mt.extract_claims(["Debt at 65% LTV, 6.0% coupon."], [])
        self.assertEqual([c.metric for c in claims], ["ltv", None])
        claims = mt.extract_claims(["Year 1 DSCR of 1.25x"], [])
        self.assertEqual(claims[0].metric, "dscr")

    # ---- second refute pass ----
    def test_year_prefixed_metric_never_ties_unrelated_cell(self):
        model = self._model([("Opex reimbursement factor", 1.25), ("Total Opex", 250000),
                             ("Year 1 DSCR", 1.10), ("Year 1 NOI", 310000)])
        res, _, _ = mt.run(self._memo(["Year 1 DSCR of 1.25x; Year 1 NOI of $250,000."]), model)
        self.assertNotIn("TIED", [r.status for r in res], [(r.claim.text, r.cell) for r in res])

    def test_distant_metric_keyword_never_ties_unrelated_cell(self):
        model = self._model([("Opex reimbursement factor", 1.25), ("DSCR", 1.10)])
        res, _, _ = mt.run(self._memo(["The DSCR, after reserves and the lender stress, is 1.25x."]), model)
        self.assertNotEqual(res[0].status, "TIED")

    def test_metric_with_no_usable_cell_is_untied(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws["A1"], ws["B1"] = "Opex reimbursement factor", 1.25
        ws["A2"], ws["B2"] = "DSCR", "#DIV/0!"
        p = self.tmp / "err.xlsx"
        wb.save(p)
        res, _, _ = mt.run(self._memo(["DSCR of 1.25x"]), p)
        self.assertEqual(res[0].status, "UNTIED")

    def test_distant_threshold_word_does_not_open_threshold_cells(self):
        model = self._model([("Min DSCR covenant", 1.25), ("Max LTV", 0.65), ("DSCR", 1.10), ("LTV", 0.72)],
                            ("Max LTV", "LTV"))
        res, _, _ = mt.run(self._memo(["Against the lender's minimum, DSCR is 1.25x and LTV is 65%."]), model)
        self.assertNotIn("TIED", [r.status for r in res], [(r.claim.text, r.cell) for r in res])

    def test_lender_test_label_competes_and_fails(self):
        model = self._model([("Lender DSCR Test", 1.25), ("DSCR", 1.10)])
        res, _, _ = mt.run(self._memo(["DSCR of 1.25x"]), model)
        self.assertEqual(res[0].status, "AMBIGUOUS")

    # ---- fourth refute pass ----
    def test_lender_cells_compete_for_ambiguity(self):
        model = self._model([("Stabilized DSCR", 1.25), ("Lender DSCR", 1.10),
                             ("LTV at stabilized value", 0.65), ("Lender LTV", 0.72)],
                            ("LTV at stabilized value", "Lender LTV"))
        res, _, _ = mt.run(self._memo(["DSCR of 1.25x and LTV of 65%"]), model)
        self.assertNotIn("TIED", [r.status for r in res], [(r.claim.text, r.cell) for r in res])

    def test_qualifier_does_not_leak_from_previous_figure(self):
        model = self._model([("Going-in Cap Rate", 0.075), ("Exit Cap Rate", 0.08)],
                            ("Going-in Cap Rate", "Exit Cap Rate"))
        res, _, _ = mt.run(self._memo(["Exit cap rate 8.0%; going-in cap rate 8.0%"]), model)
        self.assertEqual([r.status for r in res], ["TIED", "CONFLICT"])

    def test_vague_next_word_is_not_threshold(self):
        model = self._model([("Min DSCR", 1.25), ("DSCR", 1.10)])
        res, _, _ = mt.run(self._memo(["DSCR of 1.25x lender-underwritten"]), model)
        self.assertEqual(res[0].status, "CONFLICT")

    def test_interest_rate_cap_is_not_cap_rate(self):
        model = self._model([("Interest rate cap strike", 0.08), ("Going-in yield", 0.075)],
                            ("Interest rate cap strike", "Going-in yield"))
        res, _, _ = mt.run(self._memo(["Going-in cap rate of 8.0%"]), model)
        self.assertNotEqual(res[0].status, "TIED")

    # ---- fifth refute pass ----
    def test_whole_percent_model_still_flags_ambiguity(self):
        model = self._model([("Going-in Cap Rate (%)", 7.5), ("Exit Cap Rate (%)", 8.0),
                             ("LTV (%)", 72), ("Stabilized LTV (%)", 65)])
        res, _, _ = mt.run(self._memo(["The cap rate is 8.0% and LTV of 65%."]), model)
        self.assertEqual([r.status for r in res], ["AMBIGUOUS", "AMBIGUOUS"], [(r.claim.text, r.cell) for r in res])

    def test_zero_value_competes(self):
        model = self._model([("Pro forma cash-on-cash", 0.02), ("Actual cash-on-cash", 0.0)],
                            ("Pro forma cash-on-cash", "Actual cash-on-cash"))
        res, _, _ = mt.run(self._memo(["cash-on-cash of 2.0%"]), model)
        self.assertEqual(res[0].status, "AMBIGUOUS")

    def test_typed_sf_ties_only_same_area_type(self):
        model = self._model([("Land area SF", 24500), ("Rentable SF", 23800)])
        res, _, _ = mt.run(self._memo(["Rentable area of 24,500 SF"]), model)
        self.assertNotEqual(res[0].status, "TIED")

    def test_year_specific_cell_preferred(self):
        model = self._model([("Year 1 DSCR", 1.10), ("Year 5 DSCR", 1.25)])
        res, _, _ = mt.run(self._memo(["Year 1 DSCR of 1.25x"]), model)
        self.assertEqual(res[0].status, "CONFLICT")
        res, _, _ = mt.run(self._memo(["DSCR of 1.25x"]), model)
        self.assertEqual(res[0].status, "AMBIGUOUS")  # two DSCR cells, memo names no year
        self.assertIn("ambiguous", res[0].note)

    # ---- third refute pass ----
    def test_trailing_policy_word_is_not_a_threshold_statement(self):
        model = self._model([("DSCR policy minimum", 1.25), ("Max LTV", 0.65), ("DSCR", 1.10), ("LTV", 0.72)],
                            ("Max LTV", "LTV"))
        res, _, _ = mt.run(self._memo(["DSCR of 1.25x meets policy.", "LTV of 65% within limit.",
                                       "Lender DSCR: 1.25x"]), model)
        self.assertNotIn("TIED", [r.status for r in res], [(r.claim.text, r.cell) for r in res])

    def test_year_claim_with_calendar_year_columns_is_untied(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws["A1"] = "DSCR"
        for i, (yr, v) in enumerate([(2026, 1.10), (2027, 1.15), (2030, 1.25)]):
            ws.cell(row=1, column=2 + i, value=v)
        p = self.tmp / "cal.xlsx"
        wb.save(p)
        res, _, _ = mt.run(self._memo(["Year 1 DSCR of 1.25x"]), p)
        self.assertNotEqual(res[0].status, "TIED")

    def test_qualifier_selects_going_in_vs_exit(self):
        model = self._model([("Going-in Cap Rate", 0.075), ("Exit Cap Rate", 0.08)],
                            ("Going-in Cap Rate", "Exit Cap Rate"))
        res, _, _ = mt.run(self._memo(["Going-in cap rate of 8.0%", "exit cap rate of 8.0%"]), model)
        self.assertEqual([r.status for r in res], ["CONFLICT", "TIED"])

    def test_coverage_and_leverage_vocabulary(self):
        model = self._model([("Opex reimbursement factor", 1.25), ("Expense recovery", 0.65), ("DSCR", 1.10)],
                            ("Expense recovery",))
        res, _, _ = mt.run(self._memo(["Debt coverage ratio of 1.25x", "DCR 1.25x", "Leverage of 65%"]), model)
        self.assertNotIn("TIED", [r.status for r in res], [(r.claim.text, r.cell) for r in res])

    def test_incompatible_intervening_figure_does_not_steal_metric(self):
        claims = mt.extract_claims(["DSCR on the $820K loan comes in at 1.25x"], [])
        self.assertEqual(claims[1].metric, "dscr")

    def test_period_cell_is_a_count(self):
        model = self._model([("Analysis Period", 2026)])
        res, _, _ = mt.run(self._memo(["A reserve of $2K is held."]), model)
        self.assertEqual(res[0].status, "UNTIED")

    def test_hardlink_ads_and_missing_dir_outputs_refused(self):
        import os
        memo = self._memo(["Bid $1.15M"])
        link = self.tmp / "link.md"
        try:
            os.link(memo, link)
        except OSError:
            link = None
        before = memo.read_bytes()
        if link:
            self.assertEqual(mt.main([str(memo), str(self.model), "--out", str(link)]), 2)
        self.assertEqual(mt.main([str(memo), str(self.model), "--out", str(self.model) + ":ads"]), 2)
        self.assertEqual(mt.main([str(memo), str(self.model), "--out", str(self.tmp / "nodir" / "r.md")]), 2)
        self.assertEqual(memo.read_bytes(), before)

    def test_dollar_paren_negative(self):
        claims = mt.extract_claims(["a loss of $(50,000) this year"], [])
        self.assertEqual(claims[0].value, -50000.0)

    def test_figure_at_paragraph_start_is_positive(self):
        claims = mt.extract_claims(["$10.5M  (open)"], [])
        self.assertEqual(claims[0].value, 10_500_000)

    def test_range_dash_is_not_a_negative_sign(self):
        claims = mt.extract_claims(["band $9.00-$9.60 and $1.1M-$1.2M"], [])
        self.assertTrue(all(c.value > 0 for c in claims), [(c.text, c.value) for c in claims])

    # ---- post-merge refute regressions (RE-4.47-1, v4.48) ----
    def _statuses(self, rows, paras, pct=()):
        res, _, _ = mt.run(self._memo(paras), self._model(rows, pct))
        return [(r.claim.text, r.status, r.cell) for r in res]

    def _cli(self, rows, paras):
        return mt.main([str(self._memo(paras)), str(self._model(rows))])

    def test_c2a_result_sentences_are_not_threshold_statements(self):
        for memo in ("DSCR clears the floor: 1.25x.", "DSCR comes in above target at 1.25x."):
            rows = [("Min DSCR", 1.25), ("Target DSCR", 1.25), ("DSCR", 1.10)]
            self.assertEqual(self._cli(rows, [memo]), 1, memo)

    def test_c2b_floor_dscr_is_an_achieved_metric(self):
        rows = [("Floor DSCR (65% LTV loan)", 1.10), ("Year 1 DSCR", 1.30)]
        self.assertEqual(self._cli(rows, ["Floor DSCR of 1.30x."]), 1, self._statuses(rows, ["Floor DSCR of 1.30x."]))

    def test_c2b_dscr_at_max_loan_competes(self):
        rows = [("DSCR at Max Loan", 1.10), ("Stabilized DSCR", 1.40)]
        self.assertEqual(self._cli(rows, ["DSCR of 1.40x."]), 1, self._statuses(rows, ["DSCR of 1.40x."]))

    def test_c3a_year_does_not_carry_over_from_previous_figure(self):
        rows = [("Year 1 DSCR", 1.40), ("Year 5 DSCR", 1.10), ("Year 5 NOI", 300000)]
        memo = ["Year 5 NOI $300K; DSCR 1.10x."]
        self.assertEqual(self._cli(rows, memo), 1, self._statuses(rows, memo))

    def test_c3b_near_match_still_checks_ambiguity(self):
        rows = [("Year 1 DSCR", 1.10), ("Year 5 DSCR", 1.394)]
        self.assertEqual(self._cli(rows, ["DSCR of 1.40x."]), 1, self._statuses(rows, ["DSCR of 1.40x."]))

    def test_c1_trailing_metric_does_not_steal_a_bound_figure(self):
        rows = [("Cap Rate", 0.065), ("IRR", 0.075)]
        memo = ["Cap rate 7.5%, IRR 7.5%."]
        st = self._statuses(rows, memo, pct=("Cap Rate", "IRR"))
        self.assertEqual(st[0][1], "CONFLICT", st)
        self.assertEqual(st[1][1], "TIED", st)

    def test_trailing_metric_still_binds_unclaimed_figure(self):
        claims = mt.extract_claims(["IRR 14.1%, 60% LTV"], [])
        self.assertEqual([c.metric for c in claims], ["irr", "ltv"])

    def test_c4_uncached_array_formula_exits_2(self):
        path = self.tmp / "arr.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws["A1"] = "DSCR"
        ws["B1"] = openpyxl.worksheet.formula.ArrayFormula("B1", "=1+1")
        ws["A2"] = "NOI"
        ws["B2"] = 300000
        wb.save(path)
        self.assertEqual(mt.main([str(self._memo(["NOI of $300,000"])), str(path)]), 2)

    def test_c5_corrupt_docx_stream_exits_2(self):
        rebuilt = self.tmp / "deflated.docx"
        with zipfile.ZipFile(rebuilt, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("word/document.xml", "<x>" + "A" * 4000 + "</x>")
        raw = bytearray(rebuilt.read_bytes())
        start = raw.find(b"word/document.xml") + len("word/document.xml")
        for i in range(start + 4, start + 40):  # corrupt the deflate stream of the first entry's data
            raw[i] ^= 0xFF
        rebuilt.write_bytes(bytes(raw))
        self.assertEqual(mt.main([str(rebuilt), str(self.model)]), 2)

    def test_c7_rounding_band_never_straddles_the_dscr_governor(self):
        self.assertEqual(self._cli([("DSCR", 1.2445)], ["DSCR of 1.25x."]), 1)
        self.assertEqual(self._cli([("DSCR", 1.24)], ["DSCR of 1.3x."]), 1)

    def test_c7_rounding_band_never_straddles_the_ltv_governor(self):
        self.assertEqual(self._cli([("LTV", 0.6451)], ["LTV of 65%."]), 0)  # same side of 65%: rounding is fine
        self.assertEqual(self._cli([("LTV", 0.6549)], ["LTV of 65%."]), 1)  # model breaches the ceiling
        self.assertEqual(self._cli([("DSCR", 1.2512)], ["DSCR of 1.25x."]), 0)  # at the floor on both sides

    def test_c7_near_on_governed_metric_fails(self):
        self.assertEqual(self._cli([("DSCR", 1.3167)], ["DSCR of 1.3201x."]), 1)

    def test_c8_minus_after_a_year_is_a_sign(self):
        claims = mt.extract_claims(["Year 1 -$50,000 cash flow shortfall; price $2,000,000."], [])
        self.assertEqual(claims[0].value, -50000.0)

    def test_paren_percent_is_a_parenthetical(self):
        self.assertEqual(mt.extract_claims(["Less: Vacancy & Credit (5%)"], [])[0].value, 0.05)

    def test_unicode_times_sign_is_extracted(self):
        rows = [("DSCR", 1.40), ("Purchase Price", 2000000)]
        self.assertEqual(self._cli(rows, ["DSCR of 1.10× and price of $2,000,000."]), 1)

    def test_out_equal_to_json_and_pdf_are_refused(self):
        memo = self._memo(["Bid $1.15M"])
        same = self.tmp / "r.md"
        self.assertEqual(mt.main([str(memo), str(self.model), "--out", str(same), "--json", str(same)]), 2)
        pdf = self.tmp / "IC_Memo.pdf"
        pdf.write_bytes(b"%PDF")
        self.assertEqual(mt.main([str(memo), str(self.model), "--out", str(pdf)]), 2)
        self.assertEqual(pdf.read_bytes(), b"%PDF")

    # ---- second refute round on the v4.48 fix ----
    def test_r2_limit_labels_with_loan_or_floor_stay_thresholds(self):
        cases = [
            ([("Min DSCR (loan sizing)", 1.25), ("Loan Amount", 747500)], "DSCR of 1.25x."),
            ([("Maximum Loan-to-Value", 0.65), ("Loan Amount", 805000), ("Purchase Price", 1150000)],
             "Leverage: 65% LTV."),
            ([("Loan Covenant: Minimum DSCR", 1.25)], "DSCR of 1.25x."),
            ([("DSCR Floor", 1.25)], "DSCR of 1.25x."),
            ([("DSCR Floor", 1.25), ("DSCR at 65% LTV (stabilized NOI)", 1.19)], "Floor DSCR of 1.25x."),
            ([("Max Loan DSCR Constraint", 1.25), ("Year 1 DSCR", 1.18)], "DSCR at max loan of 1.25x."),
        ]
        for rows, memo in cases:
            self.assertEqual(self._cli(rows, [memo]), 1, (memo, self._statuses(rows, [memo])))

    def test_r2_achieved_forms_still_compete(self):
        self.assertFalse(mt._is_threshold(mt.Cell("S", "B1", 1.1, False, "Floor DSCR (65% LTV loan)")))
        self.assertFalse(mt._is_threshold(mt.Cell("S", "B1", 1.1, False, "DSCR at Max Loan")))
        self.assertTrue(mt._is_threshold(mt.Cell("S", "B1", 1.25, False, "Max Loan DSCR Constraint")))

    def test_r2_straddle_checked_on_every_matching_cell(self):
        rows = [("DSCR", 1.2501), ("Floor DSCR (65% LTV loan)", 1.2451)]
        self.assertEqual(self._cli(rows, ["DSCR of 1.25x."]), 1, self._statuses(rows, ["DSCR of 1.25x."]))
        rows = [("LTV", 0.6499), ("Floor LTV (max loan)", 0.6504)]
        self.assertEqual(self._cli(rows, ["LTV of 65%."]), 1, self._statuses(rows, ["LTV of 65%."]))

    def test_r2_threshold_claim_on_achieved_cell_is_governed(self):
        rows = [("Floor DSCR (65% LTV loan)", 1.2449)]
        self.assertEqual(self._cli(rows, ["DSCR of 1.25x minimum."]), 1)

    def test_r2_float_noise_at_the_governor_passes(self):
        self.assertEqual(self._cli([("LTV", 0.6500000000000001)], ["LTV of 65%."]), 0)

    def test_r2_distant_keyword_does_not_beat_trailing_metric(self):
        rows = [("Exit Cap Rate", 0.075), ("Vacancy", 0.05)]
        st = self._statuses(rows, ["Exit cap rate assumes 7.5% vacancy."], pct=("Exit Cap Rate", "Vacancy"))
        self.assertNotEqual(st[0][1], "TIED", st)
        claims = mt.extract_claims(["Levered IRR at 60% LTV is 14.1%."], [])
        self.assertEqual(claims[0].metric, "ltv")  # the 60% is the LTV, not the IRR

    def test_r2_en_dash_and_tab_negatives(self):
        self.assertEqual(mt.extract_claims(["Year 1 –$50,000 cash flow."], [])[0].value, -50000.0)
        self.assertEqual(mt.extract_claims(["Cash flow after DS\t1.05x\t-$12,500"], [])[1].value, -12500.0)
        self.assertTrue(all(c.value > 0 for c in mt.extract_claims(["Rents 9.00-$9.60 NNN."], [])))

    def test_r2_trailing_dot_or_space_out_paths_refused(self):
        memo = self._memo(["Bid $1.15M"])
        pdf = self.tmp / "other.pdf"
        pdf.write_bytes(b"%PDF")
        self.assertEqual(mt.main([str(memo), str(self.model), "--out", str(pdf) + "."]), 2)
        self.assertEqual(mt.main([str(memo), str(self.model), "--out", str(self.tmp / "o.xlsx") + " "]), 2)
        self.assertEqual(pdf.read_bytes(), b"%PDF")

    # ---- third refute round ----
    def _metrics(self, text):
        return [(c.text, c.metric) for c in mt.extract_claims([text], [])]

    def test_r3_comma_list_binds_each_figure_to_its_own_keyword(self):
        self.assertEqual(self._metrics("Levered IRR 14.1%, LTV 65%, equity multiple 2.08x, DSCR 1.25x."),
                         [("14.1%", "irr"), ("65%", "ltv"), ("2.08x", "equity_multiple"), ("1.25x", "dscr")])
        rows = [("Levered IRR", 0.141), ("Equity Multiple", 2.08), ("DSCR", 1.2451), ("LTV", 0.6549)]
        memo = ["Levered IRR 14.1%, LTV 65%, equity multiple 2.08x, DSCR 1.25x."]
        self.assertEqual(mt.main([str(self._memo(memo)), str(self._model(rows, ("Levered IRR", "LTV")))]), 1)
        self.assertEqual(self._metrics("Going-in cap rate 8.39%, IRR 8.39%")[1], ("8.39%", "irr"))
        self.assertEqual(self._metrics("65% LTV, 6.0% coupon")[1][1], None)  # a list keyword is not inherited

    def test_r3_same_kind_list_inherits_its_metric(self):
        self.assertEqual(self._metrics("DSCR of 1.18x in Year 1 and 1.25x in Year 5."),
                         [("1.18x", "dscr"), ("1.25x", "dscr")])
        self.assertEqual(self._metrics("DSCR\t1.18x\t1.25x"), [("1.18x", "dscr"), ("1.25x", "dscr")])
        rows = [("Year 1 DSCR", 1.18), ("Year 5 DSCR", 1.2451)]
        self.assertEqual(self._cli(rows, ["DSCR of 1.18x in Year 1 and 1.25x in Year 5."]), 1)
        rows = [("LTV at close", 0.60), ("LTV at refi", 0.6549)]
        self.assertEqual(mt.main([str(self._memo(["LTV of 60% at close and 65% at refi."])),
                                  str(self._model(rows, ("LTV at close", "LTV at refi")))]), 1)

    def test_r3_year_and_qualifier_stay_in_their_clause(self):
        c = mt.extract_claims(["NOI of $300,000 in Year 5; DSCR 1.25x."], [])
        self.assertEqual(c[1].year, None)
        c = mt.extract_claims(["DSCR 1.18x (Year 1); DSCR 1.32x (Year 5)."], [])
        self.assertEqual([x.year for x in c], ["1", "5"])
        c = mt.extract_claims(["A 7.5% going-in cap rate and a 7.5% exit cap rate."], [])
        self.assertEqual([x.quals for x in c], [["going_in"], ["exit"]])
        c = mt.extract_claims(["IRR of 14.1% levered and 11.2% unlevered"], [])
        self.assertEqual([x.quals for x in c], [["levered"], ["unlevered"]])

    def test_r3_hardcoded_floor_dscr_is_the_governor_input(self):
        self.assertTrue(mt._is_threshold(mt.Cell("S", "B1", 1.25, False, "Floor DSCR")))
        self.assertFalse(mt._is_threshold(mt.Cell("S", "B1", 1.19, False, "Floor DSCR", True)))
        rows = [("Floor DSCR", 1.25), ("Stabilized DSCR", 1.2449)]
        self.assertEqual(self._cli(rows, ["Floor DSCR of 1.25x."]), 1, self._statuses(rows, ["Floor DSCR of 1.25x."]))

    def test_r3_typographic_minus_on_percent(self):
        self.assertEqual(mt.extract_claims(["Unlevered IRR of −2.5%"], [])[0].value, -0.025)
        self.assertEqual(mt.extract_claims(["IRR of –2.5%"], [])[0].value, -0.025)
        self.assertEqual([c.value for c in mt.extract_claims(["band 14–17%"], [])], [0.17])

    def test_r3_more_out_paths_refused(self):
        memo = self._memo(["Bid $1.15M"])
        for name in ("rep.xlsb", "rep.docm", "rep.pptx"):
            self.assertEqual(mt.main([str(memo), str(self.model), "--out", str(self.tmp / name)]), 2, name)
        self.assertEqual(mt.main([str(memo), str(self.model), "--out", str(self.tmp)]), 2)

    def test_r3_threshold_named_before_metric(self):
        for memo in ("Minimum DSCR of 1.25x.", "Max LTV: 65%."):
            self.assertTrue(mt.extract_claims([memo], [])[0].threshold, memo)

    def test_r4_every_ltv_held_to_both_ceilings(self):
        # Fail closed: a 40% printed for 40.49% fails whatever the memo says about scope.
        self.assertEqual(self._cli([("LTV", 0.4049)], ["Per-property LTV 40%."]), 1)
        self.assertEqual(self._cli([("Aggregate LTV", 0.4049)], ["Aggregate portfolio LTV of 40%."]), 1)
        self.assertEqual(self._cli([("LTV", 0.6530)], ["Portfolio deal. Building A LTV of 65%."]), 1)
        self.assertEqual(self._cli([("LTV", 0.3949)], ["Portfolio LTV of 39.5%."]), 0)

    # ---- fourth refute round (fail-closed redesign) ----
    def test_r4_comma_and_semicolon_lists_continue_the_metric(self):
        rows = [("Year 1 DSCR", 1.18), ("Year 3 DSCR", 1.30), ("Year 5 DSCR", 1.40)]
        for memo in ("DSCR of 1.18x in Year 1, 1.40x in Year 3 and 1.40x in Year 5.",
                     "DSCR: 1.18x (Year 1), 1.40x (Year 3), 1.40x (Year 5).",
                     "DSCR of 1.18x in Year 1; 1.40x in Year 3.",
                     "DSCR of 1.18x in Year 1, rising to 1.40x in Year 3."):
            self.assertEqual(self._cli(rows, [memo]), 1, (memo, self._statuses(rows, [memo])))
        self.assertEqual(self._statuses([("Going-in Cap Rate", 0.075), ("Exit Cap Rate", 0.08)],
                                        ["Cap rates of 7.5% going-in, 7.5% exit."],
                                        pct=("Going-in Cap Rate", "Exit Cap Rate"))[1][1], "CONFLICT")
        self.assertEqual(self._statuses([("Levered IRR", 0.141), ("Unlevered IRR", 0.095)],
                                        ["IRR of 14.1% levered, 14.1% unlevered."],
                                        pct=("Levered IRR", "Unlevered IRR"))[1][1], "CONFLICT")
        rows = [("Year 1 DSCR", 1.18), ("Year 3 DSCR", 1.2451), ("Year 5 DSCR", 1.40)]
        self.assertEqual(self._cli(rows, ["DSCR of 1.18x in Year 1, 1.25x in Year 3 and 1.40x in Year 5."]), 1)

    def test_r4_threshold_statements_are_not_exempt(self):
        rows = [("DSCR Floor", 1.25), ("Year 1 DSCR", 1.19), ("Stabilized DSCR", 1.21)]
        for memo in ("Minimum DSCR of 1.25x over the hold.", "Min DSCR: 1.25x.", "The minimum DSCR is 1.25x."):
            self.assertEqual(self._cli(rows, [memo]), 1, (memo, self._statuses(rows, [memo])))
        rows = [("Max LTV", 0.65), ("LTV", 0.662)]
        for memo in ("Max LTV: 65%.", "Maximum LTV of 65% at refinance."):
            res, _, _ = mt.run(self._memo([memo]), self._model(rows, ("Max LTV", "LTV")))
            self.assertIn("CONFLICT", [r.status for r in res], memo)
        rows = [("Minimum DSCR (hold)", 1.2451), ("Year 1 DSCR", 1.40)]
        self.assertEqual(self._cli(rows, ["Minimum DSCR of 1.25x."]), 1)
        self.assertEqual(self._cli([("Min DSCR", 1.25), ("Year 1 DSCR", 1.40)], ["Minimum DSCR of 1.25x."]), 0)

    def test_r4_echo_formula_is_not_a_computed_floor(self):
        self.assertTrue(mt.BARE_REF_RE.match("=Inputs!B5"))
        self.assertTrue(mt.BARE_REF_RE.match("='Deal Inputs'!$C$12"))
        self.assertFalse(mt.BARE_REF_RE.match("=B5/B6"))
        rows = [("Floor DSCR", 1.25), ("DSCR at 65% LTV", 1.19), ("Year 1 DSCR", 1.30)]
        self.assertEqual(self._cli(rows, ["Floor DSCR of 1.25x."]), 1)
        self.assertEqual(self._cli(rows, ["The floor DSCR is 1.25x."]), 1)
        rows = [("Floor LTV", 0.65), ("LTV at 1.25x DSCR", 0.68)]
        res, _, _ = mt.run(self._memo(["Floor LTV of 65%."]), self._model(rows, ("Floor LTV", "LTV at 1.25x DSCR")))
        self.assertNotEqual([r.status for r in res], ["TIED"])

    def test_r4_unbound_dscr_in_a_dscr_sentence_is_governed(self):
        rows = [("Year 1 DSCR", 1.2451), ("Equity Multiple", 2.08)]
        for memo in ("Equity multiple 2.08x, DSCR at 1.25x.", "DSCR stands at 1.25x.", "DSCR improves to 1.25x.",
                     "DSCR (Year 1) 1.25x.", "DSCR - 1.25x.", "DSCR ~1.25x.", "Debt service coverage at 1.25x."):
            self.assertEqual(self._cli(rows, [memo]), 1, (memo, self._statuses(rows, [memo])))
        # an unrelated multiple in a DSCR sentence is not held to the DSCR floor
        self.assertEqual(self._cli([("Year 1 DSCR", 1.40), ("Equity Multiple", 1.21)],
                                   ["Equity multiple 1.21x and DSCR 1.40x."]), 0)

    def test_governor_constants_come_from_doctrine(self):
        from ora_walk import doctrine
        self.assertEqual(mt.GOVERNORS["dscr"], (doctrine.DSCR_FLOOR,))
        self.assertEqual(set(mt.GOVERNORS["ltv"]),
                         {doctrine.PER_PROPERTY_LTV_CEILING, doctrine.AGGREGATE_LTV_CEILING})


if __name__ == "__main__":
    unittest.main(verbosity=2)
