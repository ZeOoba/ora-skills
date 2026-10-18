"""30/360 day count for payoff audits (debt-management A3 / Workflow B).

Variants follow ISDA 2006 Definitions s.4.16(f) (Bond Basis) and the SIA standard
calculation methods (US with end-of-February rule); 30E/360 is the Eurobond method.
NASD is intentionally unsupported -- read the Note and flag it instead of guessing.
"""
from __future__ import annotations

import calendar
import sys
from datetime import date

VARIANTS = ("bond_basis", "us_eom", "e360")


def _last_day_of_feb(d: date) -> bool:
    return d.month == 2 and d.day == calendar.monthrange(d.year, 2)[1]


def days_30_360(start: date, end: date, variant: str) -> int:
    if variant not in VARIANTS:
        raise ValueError(f"variant must be one of {VARIANTS}, got {variant!r}; "
                         "if the Note is silent or says NASD, flag it -- do not default")
    if end < start:
        raise ValueError("end must be on or after start")
    d1, d2 = start.day, end.day
    if variant == "e360":
        d1, d2 = min(d1, 30), min(d2, 30)
    else:
        if variant == "us_eom":
            if _last_day_of_feb(start) and _last_day_of_feb(end):
                d2 = 30
            if _last_day_of_feb(start):
                d1 = 30
        if d2 == 31 and d1 >= 30:
            d2 = 30
        if d1 == 31:
            d1 = 30
    return 360 * (end.year - start.year) + 30 * (end.month - start.month) + (d2 - d1)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: daycount.py YYYY-MM-DD YYYY-MM-DD bond_basis|us_eom|e360")
    print(days_30_360(date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2]), sys.argv[3]))
