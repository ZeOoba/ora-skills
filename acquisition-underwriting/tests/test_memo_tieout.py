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


if __name__ == "__main__":
    unittest.main(verbosity=2)
