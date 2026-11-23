"""Shape check for an `ora.acq-screen-packet/1` screen packet (acquisition-underwriting v4.59).

Usage: python screen_packet.py <packet.json>   -> exit 0 valid, 1 rejected, 2 unreadable

The reader of record is scripts/import-acq-screen-packet.ts in the oxford-command-center repo
(parseScreenPacket) plus the AcquisitionInput Zod contract in src/contracts/acquisition.ts. This
file mirrors their FORMAT rejects so a skill run can check the packet it just wrote before the
operator imports it. It does not resolve the candidate crosswalk (that needs the warehouse) and it
never fixes a value: a percent-form rate is a reject, not divided by 100.

Contract snapshot: oxford-command-center main 0748f1e0 (2026-11-24; PR #591 merged, plus #604). When the contract
gains, renames or rebounds a field, update INPUT_FIELDS and the bands here in the same change as
SKILL.md; the importer stays authoritative if the two disagree. Stdlib only.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import re
import sys
from pathlib import Path

SCHEMA = "ora.acq-screen-packet/1"

ENVELOPE_KEYS = {"schema", "skillVersion", "screenedAt", "deal", "sourceFiles", "input", "notes"}
DEAL_KEYS = {"candidateId", "notionPageId", "hubspotDealId", "address"}

PRODUCT_TYPES = {
    "shallow-bay-multi", "flex", "office-warehouse", "functional-single-tenant",
    "quasi-ios", "retail-only", "office-only", "other",
}
# 'block-tilt-brick' is the contract's legacy alias (preprocessed to 'cmu'); accepted, never written by the skill.
CONSTRUCTION_TYPES = {"tilt-precast", "cmu", "brick", "hybrid", "pemb", "mixed", "unknown", "block-tilt-brick"}
RCT_ADDERS = {"heavy-office", "climate-controlled", "cranes", "esfr", "excess-site-work", "paving-lighting"}
CLUSTER_TIERS = {"owned-submarket", "established", "entry", "satellite", "none"}
CONFIDENCE = {"confirmed", "estimated", "derived"}
DD_KEYS = {"flood", "zoning", "roof", "deferred-maintenance-capex"}
USE_KEYS = {"automotive", "childRelated", "childSafetyReviewed"}

UST10YR_MIN, UST10YR_MAX = 0.005, 0.2
EXIT_CAP_MAX = 0.25

# field -> kind. Every key AcquisitionInput accepts; anything else is a reject (strict contract).
INPUT_FIELDS = {
    "dealId": "str",
    "isPortfolio": "bool",
    "price": "money",
    "maxBuildingSf": "sf",
    "totalSf": "sf",
    "productType": ("enum", PRODUCT_TYPES),
    "officePct": ("range", 0.0, 1.0),
    "demisableOffice": "bool",
    "clearHeightFt": "num",
    "hasDriveIn": "bool",
    "hasDock": "bool",
    "dockCount": "count",
    "driveInCount": "count",
    "multiStory": "bool",
    "truckCourtFt": "num",
    "constructionType": ("enum", CONSTRUCTION_TYPES),
    "rctAdders": ("list", RCT_ADDERS),
    "yearBuilt": "int",
    "sfhaOnPad": "bool",
    "sfhaOnExcessLandOnly": "bool",
    "groundLeased": "bool",
    "groundLeaseYearsRemaining": "num",
    "envRemediationPctOfPrice": ("range", 0.0, 1.0),
    "use": "use",
    "allInBasis": "money",
    "replacementCostTotal": "money",
    "replacementCostBand": ("enum", {"low", "mid", "high"}),
    "market": "str",
    "stabilizedYoc": ("open_low", -0.5, 0.5),
    "unleveredIrr10yr": ("open_low", -0.5, 0.5),
    "ust10yr": ("range", UST10YR_MIN, UST10YR_MAX),
    "ustAsOf": "str",
    "vacantSfShareAtClose": ("range", 0.0, 1.0),
    "exitCapPct": ("open_low", 0.0, EXIT_CAP_MAX),
    "leveredIrr": ("open_low", -1.0, 1.0),
    "underwriteHorizonYrs": ("enum", {5, 10}),
    "clusterTier": ("enum", CLUSTER_TIERS),
    "driveMinutesToCluster": "num",
    "marketFundamentalsAdj": ("range", -1.0, 1.0),
    "marketFundamentalsConfidence": ("enum", CONFIDENCE),
    "compSourcedAt": "str",
    "sellerMotivationScore": ("range", 0.0, 1.0),
    "isVacant": "bool_required_type",
    "inPlaceRentPsf": "num",
    "marketRentPsf": "num",
    "marketRentConfidence": ("enum", CONFIDENCE),
    "waltYears": "num",
    "valueAddScore": ("range", 0.0, 1.0),
    "ddKnown": "ddknown",
    "asAtUtc": "str",
}

FILENAME_RE = re.compile(r"^ScreenPacket_[A-Za-z0-9-]+_(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])20[0-9]{2}\.json$")


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _iso_date(s) -> bool:
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return False
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        return False
    return True


def _check_field(name: str, v, kind) -> str | None:
    if v is None:
        if kind == "bool_required_type":
            return f"input.{name}: must be true or false (omit it rather than null)"
        if kind == "ddknown":
            return f"input.{name}: must be an object (omit it rather than null)"
        return None
    if kind in ("bool", "bool_required_type"):
        return None if isinstance(v, bool) else f"input.{name}: must be true/false"
    if kind == "str":
        return None if isinstance(v, str) else f"input.{name}: must be a string"
    if kind == "int":
        return None if _is_num(v) and float(v).is_integer() else f"input.{name}: must be an integer"
    if kind == "count":
        return None if _is_num(v) and float(v).is_integer() and v >= 0 else f"input.{name}: must be a non-negative integer"
    if kind == "num":
        return None if _is_num(v) else f"input.{name}: must be a finite number"
    if kind == "money":
        return None if _is_num(v) and v >= 0 else f"input.{name}: must be a finite non-negative amount"
    if kind == "sf":
        return None if _is_num(v) and v > 0 else f"input.{name}: must be a positive SF"
    # Nested objects: Zod strips an unknown key inside `use` / `ddKnown`, and the importer rejects any key
    # it stripped (strippedKeyPath, PR #591 merge gate S-1), so a misspelled key is a format reject.
    if kind == "use":
        if not isinstance(v, dict) or not all(isinstance(v.get(k), bool) for k in USE_KEYS):
            return f"input.{name}: must carry {sorted(USE_KEYS)} as true/false"
        extra = sorted(set(v) - USE_KEYS)
        return f"input.{name}.{extra[0]}: unrecognized key (not in the AcquisitionInput contract)" if extra else None
    if kind == "ddknown":
        if not isinstance(v, dict):
            return f"input.{name}: must be an object"
        if not all(isinstance(v[k], bool) for k in DD_KEYS if k in v):
            return f"input.{name}: values must be true/false"
        extra = sorted(set(v) - DD_KEYS)
        return f"input.{name}.{extra[0]}: unrecognized key (not in the AcquisitionInput contract)" if extra else None
    tag = kind[0]
    if tag == "enum":
        ok = isinstance(v, (str, int)) and not isinstance(v, bool) and v in kind[1]
        return None if ok else f"input.{name}: {v!r} is not one of {sorted(map(str, kind[1]))}"
    if tag == "list":
        if not isinstance(v, list) or any(not isinstance(x, str) or x not in kind[1] for x in v):
            return f"input.{name}: must be a list drawn from {sorted(kind[1])}"
        return None
    if tag == "range":
        lo, hi = kind[1], kind[2]
        if not _is_num(v) or v < lo or v > hi:
            return f"input.{name}: {v!r} is outside [{lo}, {hi}] (a decimal, never a percent)"
        return None
    if tag == "open_low":
        lo, hi = kind[1], kind[2]
        if not _is_num(v) or v <= lo or v > hi:
            return f"input.{name}: {v!r} is outside ({lo}, {hi}] (rates are decimals: 0.0743 = 7.43%, never percents)"
        return None
    raise AssertionError(f"unhandled kind for {name}")


def validate_packet(p, today: _dt.date | None = None) -> list[str]:
    """Return every reject reason for one packet (empty list = valid). `today` defaults to the UTC date."""
    errs: list[str] = []
    if not isinstance(p, dict):
        return ["packet: must be a JSON object"]
    extra = set(p) - ENVELOPE_KEYS
    if extra:
        errs.append(f"packet: unknown key(s) {sorted(extra)}")
    if p.get("schema") != SCHEMA:
        errs.append(f"schema: must be {SCHEMA!r}")
    sv = p.get("skillVersion")
    if not isinstance(sv, str) or not sv.strip():
        errs.append("skillVersion: required, non-blank")
    if not _iso_date(p.get("screenedAt")):
        errs.append(f"screenedAt: {p.get('screenedAt')!r} is not an ISO calendar date (YYYY-MM-DD)")
    else:
        # The importer allows today (UTC) plus one day of timezone slack; a later date would sit in its
        # screens ledger as the newest screen and mark every real later screen stale (merge gate C-1).
        base = today or _dt.datetime.now(_dt.timezone.utc).date()
        if p["screenedAt"] > (base + _dt.timedelta(days=1)).isoformat():
            errs.append(f"screenedAt: {p['screenedAt']!r} is in the future")

    deal = p.get("deal")
    if not isinstance(deal, dict):
        errs.append("deal: required object")
    else:
        dx = set(deal) - DEAL_KEYS
        if dx:
            errs.append(f"deal: unknown key(s) {sorted(dx)}")
        if "address" in deal and not isinstance(deal["address"], str):
            errs.append("deal.address: must be a string")
        for k in ("candidateId", "notionPageId", "hubspotDealId"):
            if k in deal and not (isinstance(deal[k], str) and deal[k].strip()):
                errs.append(f"deal.{k}: must be a non-blank string")
        ids = [deal.get(k) for k in ("candidateId", "notionPageId", "hubspotDealId")]
        if not any(isinstance(i, str) and i.strip() for i in ids):
            errs.append("deal: needs candidateId, notionPageId or hubspotDealId")

    # Optional means "may be absent", never null (Zod .optional()).
    sf = p.get("sourceFiles")
    if "sourceFiles" in p and (not isinstance(sf, list) or not all(isinstance(x, str) for x in sf)):
        errs.append("sourceFiles: must be a list of strings")
    notes = p.get("notes")
    if "notes" in p and (not isinstance(notes, dict) or not all(isinstance(x, str) for x in notes.values())):
        errs.append("notes: must map field names to strings")

    inp = p.get("input")
    if not isinstance(inp, dict):
        errs.append("input: required object")
        return errs
    unknown = set(inp) - set(INPUT_FIELDS)
    if unknown:
        errs.append(f"input: unknown key(s) {sorted(unknown)} (the contract is strict)")
    for name, kind in INPUT_FIELDS.items():
        if name in inp:
            e = _check_field(name, inp[name], kind)
            if e:
                errs.append(e)
    mb, ts = inp.get("maxBuildingSf"), inp.get("totalSf")
    if _is_num(mb) and _is_num(ts) and mb > ts:
        errs.append("input: maxBuildingSf exceeds totalSf")
    return errs


def skill_rules(p) -> list[str]:
    """This skill's own rules on top of the importer's (v4.59): provenance notes are mandatory."""
    errs: list[str] = []
    if not isinstance(p, dict) or not isinstance(p.get("input"), dict):
        return errs
    deal = p.get("deal") if isinstance(p.get("deal"), dict) else {}
    if deal.get("hubspotDealId") and (deal.get("candidateId") or deal.get("notionPageId")):
        errs.append("deal: a Notion row and a HubSpot deal are separate candidates; name ONE twin (the Notion row by default)")
    notes = p.get("notes") if isinstance(p.get("notes"), dict) else {}
    if "left-null" not in notes:
        errs.append("notes.left-null: required (name each omitted field and why, or 'none')")
    covered = " / ".join(notes.keys())
    for field in p["input"]:
        if field == "dealId":
            continue
        if not re.search(rf"(^|[^A-Za-z]){re.escape(field)}([^A-Za-z]|$)", covered):
            errs.append(f"notes: no source note for input.{field}")
    return errs


def check_payload(payload) -> list[str]:
    packets = payload["packets"] if isinstance(payload, dict) and isinstance(payload.get("packets"), list) else [payload]
    out: list[str] = []
    seen: dict[tuple[str, str], int] = {}
    for i, p in enumerate(packets):
        out += [f"packet {i}: {e}" for e in validate_packet(p) + skill_rules(p)]
        deal = p.get("deal") if isinstance(p, dict) and isinstance(p.get("deal"), dict) else {}
        for k in ("candidateId", "notionPageId", "hubspotDealId"):
            v = deal.get(k)
            if isinstance(v, str) and v.strip():
                if (k, v) in seen:
                    # The importer skips both as ambiguous: array order would decide the current score.
                    out.append(f"packet {i}: deal.{k} {v!r} also named by packet {seen[(k, v)]}; a file names a candidate once, never twice")
                seen.setdefault((k, v), i)
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python screen_packet.py <packet.json>", file=sys.stderr)
        return 2
    path = Path(argv[0])
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        print(f"cannot read {path}: {e}", file=sys.stderr)
        return 2
    errs = check_payload(payload)
    if not FILENAME_RE.match(path.name):
        print(f"warning: file name {path.name!r} is not ScreenPacket_<Property>_<MMDDYYYY>.json", file=sys.stderr)
    for e in errs:
        print(f"REJECT {e}")
    print("OK" if not errs else f"{len(errs)} problem(s)")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
