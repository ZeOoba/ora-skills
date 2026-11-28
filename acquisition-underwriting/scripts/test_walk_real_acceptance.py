"""Off-repo cross-engine acceptance for walk-solver component mode (RE-4.61-3).

The real deal fixture and its engine pins are confidential and never enter this public repo. Point
ORA_WALK_REAL_FIXTURE at the local JSON to run: python acquisition-underwriting/scripts/test_walk_real_acceptance.py
"""
import json
import os
import sys
import unittest

CI_EXCLUDE = "needs the off-repo confidential deal fixture (ORA_WALK_REAL_FIXTURE); never available in CI"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ora_walk import rct_table  # noqa: E402

# IRR legs do not read the RCT table; the synthetic one only lets the Basis leg compute.
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "rct-table.synthetic.json"),
          encoding="utf-8") as _fh:
    rct_table.use(json.load(_fh))

@unittest.skipUnless(os.environ.get("ORA_WALK_REAL_FIXTURE"), "real-deal fixture is off-repo; set ORA_WALK_REAL_FIXTURE")
class RealDealAcceptance(unittest.TestCase):
    """Cross-engine acceptance on the real deal component mode was built from (RE-4.61-3). The fixture and its engine
    pins are confidential and never enter this public repo: point ORA_WALK_REAL_FIXTURE at the local JSON (deal spec
    plus "_acceptance_pins": {ust, tol, tol_b, A: {base, downside}, B: {base, downside}, C: {base}})."""

    def test_irr_legs_match_the_deal_engine(self):
        from ora_walk import components as C
        with open(os.environ["ORA_WALK_REAL_FIXTURE"], encoding="utf-8") as fh:
            spec = json.load(fh)
        pins = spec.pop("_acceptance_pins")
        cases = {k: v for k, v in pins.items() if k not in ("ust", "tol", "tol_b")}
        self.assertTrue(cases, "no acceptance cases in _acceptance_pins")          # no vacuous pass
        for case, legs in cases.items():
            self.assertTrue(legs, f"case {case} has no pinned legs")
        for case, legs in pins.items():
            if case in ("ust", "tol", "tol_b"):
                continue
            s = json.loads(json.dumps(spec))
            s["property_tax"]["case"] = case
            d = C.from_dict(s)
            labels = C.departure_labels(d)
            d = C.replace(d, cited_overrides={**(d.cited_overrides or {}),
                                              **{lb: "test" for lb in labels if lb not in (d.cited_overrides or {})}})
            r = C.solve_components(d, pins["ust"])["input_case"]
            tol = pins["tol_b"] if case == "B" else pins["tol"]
            for side, want in legs.items():
                with self.subTest(case=case, side=side):
                    self.assertLessEqual(abs(r[f"legs_{side}"]["irr"] / want - 1), tol)


if __name__ == "__main__":
    unittest.main()
