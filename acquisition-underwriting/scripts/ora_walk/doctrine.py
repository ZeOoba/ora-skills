"""ORA acquisition doctrine constants — READ-ONLY mirror of acquisition-underwriting SKILL.md.

Source of record: ora-skills/acquisition-underwriting/SKILL.md (v4.48, 2026-11-13; constants
unchanged since v4.45, 2026-11-08) and
oxford-command-center/config/replacement-cost.v3.json (RCT v03, ratified 2026-07-14).
If these values and SKILL.md disagree, SKILL.md wins and this file is the bug.
Governor constants (DSCR 1.25 / LTV 65 per-property / LTV 40 aggregate) change only by
Gabriel's in-turn ratification (Hard Invariant 4) — never edit them to make a deal work.
"""

DOCTRINE_VERSION = "acquisition-underwriting v4.48 / RCT v03 (replacement-cost.v3.1)"

# --- Governors (Hard Invariant 4) ---
DSCR_FLOOR = 1.25                 # the 1.25x floor DSCR is tested at a 65%-LTV loan on stabilized NOI (v4.44/v4.45)
PER_PROPERTY_LTV_CEILING = 0.65   # refi sized to LESSER of 65% LTV and 1.25x DSCR
AGGREGATE_LTV_CEILING = 0.40      # portfolio-level; checked at STAGE 2.3, all-cash basis (not here)

# --- STAGE 1 floors (SKILL.md STAGE 1 — FLOORS) ---
YOC_FLOOR = 0.08
IRR_FLOOR_MIN = 0.10              # 10-yr unlevered IRR >= max(10%, UST + 550 bps)
IRR_FLOOR_UST_SPREAD = 0.055
MAJORITY_VACANT_PREMIUM = 0.01    # +100 bps when >50% of SF vacant at close (v4.40)
BASIS_FLOOR_OLD = 0.65            # discount-to-replacement floor at/below 1995
BASIS_FLOOR_NEW = 0.60            # at/above 2005; linear -0.5%/yr between
BASIS_RAMP_START, BASIS_RAMP_END = 1995, 2005
RCT_LOW_FACTOR = 0.90             # LOW = 0.90 x (POINT x construction multiplier + adders)
RENO_NO_SHIFT, RENO_FULL_RESET = 0.05, 0.25   # renovation effective-vintage rule (R%)
DENOM_SENSITIVE_BAND = 0.05       # within ±5 discount-pts of the floor (SKILL.md STAGE 1 DENOMINATOR-SENSITIVE flag)

# --- Gates (flags) ---
SINGLE_PRICE_MIN, SINGLE_PRICE_MAX = 500_000, 10_000_000
PORTFOLIO_PRICE_MAX = 15_000_000
PORTFOLIO_MIN_BLDGS, PORTFOLIO_MAX_BLDGS = 2, 5
MAX_SF_PER_BUILDING = 50_000

# --- Underwriting conventions (SKILL.md UNDERWRITING CONVENTIONS) ---
CLOSING_COST = 0.02               # of price
RESERVES_PSF = 0.15               # $/SF/yr non-recoverable, grows with expenses
EXPENSE_GROWTH = 0.03
MARKET_RENT_GROWTH = 0.025        # Base case (SKILL.md Suite-Level Rollover & Credit Block (e)); 3% is the in-model contractual MINIMUM, not growth
HOLD_YEARS = 10
STRUCTURAL_VACANCY = 0.05         # vacancy line floor already netted into stabilized NOI (MAX(5%, downtime))
LEASE_UP_TI_PSF = 8.00            # Lease-Up Assumption Block standing TI default, [EST] until a broker quote
REFI_SPREAD = 0.02                # refi rate = 10-yr UST + 200 bps (v4.37)
REFI_AMORT_YEARS = 25
REFI_FINANCING_COST = 0.01

# --- Construction-Type Multiplier (SKILL.md Construction-Type Multiplier Schedule), point values only ---
CONSTRUCTION_MULT = {
    "tilt-up": 1.00, "precast": 1.00, "cmu": 0.97, "brick": 1.10, "hybrid": 0.93,
}
PEMB_TILT = ((20_000, 0.88), (40_000, 0.90), (float("inf"), 0.92))  # SF upper bound, mult
UNKNOWN_MULT_CAP = 0.90           # unknown type: PEMB value for the SF, capped at 0.90

# Adder schedule (SKILL.md RCT v03 adder schedule), $/SF added to POINT after the multiplier. Site-work pair never stacks.
ADDERS = {"office_buildout": 15.0, "climate_control": 12.0, "cranes": 18.0, "esfr": 4.0,
          "site_work": 8.0, "paving_lighting": 8.0}
NON_STACKING_ADDERS = {"site_work", "paving_lighting"}

EXIT_CAPS = {
    "Columbus OH": 0.075, "Cincinnati OH": 0.075, "Indianapolis IN": 0.075,
    "Kansas City MO": 0.0775, "Madison WI": 0.0725, "Mid-Atlantic": 0.0725,
    "Grand Rapids MI": 0.08, "Richmond VA": 0.0775, "Des Moines IA": 0.0775,
    "Louisville KY": 0.0775, "Chicago-Cook IL": 0.08,
}
DEFAULT_EXIT_CAP = 0.0775  # flag when used

# RCT v03 POINT $/SF (LOW is re-derived after the construction multiplier). SKILL.md Replacement Cost Table (RCT v03).
RCT_POINT = {
    "Columbus OH": 255.16, "Cincinnati OH": 279.40, "Kansas City MO": 253.22,
    "Indianapolis IN": 282.03, "Mid-Atlantic": 258.85, "Madison WI": 254.53,
    "Grand Rapids MI": 281.23, "Richmond VA": 258.85, "Des Moines IA": 257.40,
    "Louisville KY": 263.41, "Chicago-Cook IL": 250.66,
}
# Always DENOMINATOR-SENSITIVE (SKILL.md RCT v03 standing-flag markets): proxies + Chicago; Indianapolis keeps its standing flag.
DENOMINATOR_SENSITIVE = {"Madison WI", "Grand Rapids MI", "Richmond VA", "Des Moines IA",
                         "Chicago-Cook IL", "Indianapolis IN"}
RCT_FALLBACK_POINT = min(RCT_POINT.values())  # cheapest market => strictest floor (Chicago, 250.66)

MARKET_ALIASES = {
    "columbus": "Columbus OH", "cincinnati": "Cincinnati OH", "indianapolis": "Indianapolis IN",
    "kansas city": "Kansas City MO", "kc": "Kansas City MO", "madison": "Madison WI",
    "maryland": "Mid-Atlantic", "maryland/dc": "Mid-Atlantic", "baltimore": "Mid-Atlantic",
    "mid-atlantic": "Mid-Atlantic", "grand rapids": "Grand Rapids MI", "richmond": "Richmond VA",
    "des moines": "Des Moines IA", "louisville": "Louisville KY", "chicago": "Chicago-Cook IL",
    "cook county": "Chicago-Cook IL", "chicago–greater cook county il": "Chicago-Cook IL",
    "chicago-greater cook county il": "Chicago-Cook IL",
}
