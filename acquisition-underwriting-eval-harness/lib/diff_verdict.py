"""Comparison/tolerance engine for the acquisition-underwriting golden-set harness.

Pure function: diff a live SCREEN-mode replay's observed result against one
frozen golden_set/*.json record. The pilot's primary signal is the combined
score only (per every golden file's diff_policy.primary_signal); tier and
per-category comparisons are reported as informational detail and never gate.

`golden["golden"]` values are taken as given, never recomputed or "corrected"
by this module — as of the 2026-08-14 rebaseline they are themselves a fresh
replay's own output (see each golden file's `baselined_date`), not an
external archive, so there is nothing to reconcile here. The ORIGINAL
Notion-archived pre-rebaseline scores (where they carried their own internal
arithmetic inconsistencies, e.g. quality + economics != combined on the 1333
Research Rd and Liberty Office Park rows) live under the sibling key
`archived_pre_v03_reference` and are never read by this module.
"""

from numbers import Real

_VALID_CONFIDENCE_LEVELS = ("HIGH", "MEDIUM", "LOW")


def _require_number(value, label):
    """Return value if it is a real (non-bool) number, else raise ValueError."""
    if isinstance(value, Real) and not isinstance(value, bool):
        return float(value)
    raise ValueError(f"{label} must be a number, got {value!r}")


def _normalize_tier(tier):
    """Normalize a tier label for informational comparison.

    Strips any trailing parenthetical annotation (McCormick's archived tier is
    'KILLED (post-hoc status overwrite, ...)'), then compares casefolded.
    Returns None for non-string/empty input.
    """
    if not isinstance(tier, str):
        return None
    base = tier.split("(", 1)[0].strip()
    return base.casefold() if base else None


def _category_deltas(golden_bd, observed_bd):
    """Per-category observed-minus-golden deltas, or None if either side absent.

    Only numeric golden entries are diffed (Hamilton's breakdown carries
    non-numeric '*_flag' annotation entries — skipped). A golden category
    missing or non-numeric on the observed side maps to None so the reader
    sees the gap rather than a silent omission.
    """
    if not isinstance(golden_bd, dict) or not isinstance(observed_bd, dict):
        return None
    deltas = {}
    for key, golden_val in golden_bd.items():
        if not (isinstance(golden_val, Real) and not isinstance(golden_val, bool)):
            continue  # annotation entry like 'basis_flag': '[est]'
        observed_val = observed_bd.get(key)
        if isinstance(observed_val, Real) and not isinstance(observed_val, bool):
            deltas[key] = float(observed_val) - float(golden_val)
        else:
            deltas[key] = None
    return deltas


def diff_verdict(golden: dict, observed: dict) -> dict:
    """Diff one observed SCREEN replay against its golden record.

    Args:
        golden: full parsed golden_set/*.json dict (top-level `confidence` and
            `diff_policy`; scores under `golden`, keyed `golden["golden"]["verdict_tier"]`
            -- NOT `archived_verdict_tier`, which is a pre-2026-08-14-rebaseline field
            name that only survives inside `archived_pre_v03_reference` for historical
            context and is never read by this module).
        observed: replay report dict with at least `combined` (float),
            `verdict_tier` (str), and optionally `category_breakdown` (dict|None).

    Returns:
        Result dict. `status` (PASS/FLAG) is driven solely by the combined-score
        tolerance — strictly beyond tolerance flags; exactly at tolerance passes.
        `scored` is False (and `informational_only` True) for LOW-confidence
        golden rows: the delta is still computed and reported, but the caller
        must exclude the row from any strict pass/fail tally.

    Raises:
        ValueError: if either combined score or the tolerance is missing/non-numeric,
            or if golden['confidence'] is not one of HIGH/MEDIUM/LOW.
    """
    golden_block = golden.get("golden") or {}
    diff_policy = golden.get("diff_policy") or {}

    combined_golden = _require_number(
        golden_block.get("combined"), "golden['golden']['combined']"
    )
    combined_observed = _require_number(
        observed.get("combined"), "observed['combined']"
    )
    tolerance_pts = _require_number(
        diff_policy.get("tolerance_combined_pts"),
        "golden['diff_policy']['tolerance_combined_pts']",
    )

    combined_delta = combined_observed - combined_golden
    status = "PASS" if abs(combined_delta) <= tolerance_pts else "FLAG"

    confidence = golden.get("confidence")
    if confidence not in _VALID_CONFIDENCE_LEVELS:
        raise ValueError(
            f"golden['confidence'] must be one of {_VALID_CONFIDENCE_LEVELS}, "
            f"got {confidence!r} -- an unrecognized value must not silently "
            "fall through to scored=False (that would exclude a row from the "
            "strict pass/fail tally without anyone deciding to)"
        )
    scored = confidence in ("HIGH", "MEDIUM")

    golden_tier = golden_block.get("verdict_tier")
    observed_tier = observed.get("verdict_tier")
    norm_golden = _normalize_tier(golden_tier)
    norm_observed = _normalize_tier(observed_tier)
    tier_match = (
        norm_golden is not None
        and norm_observed is not None
        and norm_golden == norm_observed
    )

    category_deltas = _category_deltas(
        golden_block.get("category_breakdown"), observed.get("category_breakdown")
    )

    notes = []
    known_gaps = golden.get("known_gaps") or []
    for gap in known_gaps:
        notes.append(f"known_gap: {gap}")
    if not scored:
        notes.append(
            f"excluded from strict scoring: {confidence} confidence "
            "(delta reported as informational only)"
        )
    if not tier_match:
        notes.append(
            "tier mismatch (informational only, per diff_policy.tier_check): "
            f"golden={golden_tier!r} vs observed={observed_tier!r}"
        )
    if category_deltas is None and golden_block.get("category_breakdown"):
        notes.append(
            "golden category_breakdown present but observed side absent — "
            "per-category deltas not computed"
        )

    return {
        "deal_id": golden.get("deal_id"),
        "status": status,
        "scored": scored,
        "informational_only": not scored,
        "confidence": confidence,
        "combined_golden": combined_golden,
        "combined_observed": combined_observed,
        "combined_delta": combined_delta,
        "tolerance_pts": tolerance_pts,
        "tier_match": tier_match,
        "golden_tier": golden_tier,
        "observed_tier": observed_tier,
        "category_deltas": category_deltas,
        "notes": notes,
    }
