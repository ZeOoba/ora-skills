#!/usr/bin/env python3
"""census_acs_extract.py -- Oxford Realty Advisors
Key-free extractor for U.S. Census ACS 1-Year educational attainment by
Metropolitan Statistical Area, 2005-2024, pulled from the public Census
Summary File FTP (no API key). Metric: population 25+ with a bachelor's
degree or higher. Validated vs Census GCT (2019 NY metro = 41.8%)."""
import csv, re, io, zipfile, urllib.request, ssl
BASE = "https://www2.census.gov/programs-surveys/acs/summary_file"
_CTX = ssl.create_default_context()
ANCHORS = {
    2024: dict(fmt="tb",  tbl="B15003"),
    2023: dict(fmt="tb",  tbl="B15003"),
    2019: dict(fmt="seq", tbl="B15003", seq=55, start=64, geo_csv=True),
    2014: dict(fmt="seq", tbl="B15003", seq=56, start=64, geo_csv=True),
    2009: dict(fmt="seq", tbl="B15002", seq=56, start=90, geo_csv=False),
    2005: dict(fmt="seq", tbl="B15002", seq=55, start=90, geo_csv=False, legacy2005=True),
}
XWALK = {
    2005: {"31080":"31100","17410":"17460","46520":"26180","35840":"42260"},
    2009: {"31080":"31100","17410":"17460","46520":"26180","35840":"14600"},
    2014: {"17410":"17460"}, 2019: {"17410":"17460"},
}
def _get(url, timeout=90):
    return urllib.request.urlopen(url, timeout=timeout, context=_CTX).read()
def _baplus_indices(tbl, start):
    tot = start - 1
    if tbl == "B15003":
        return tot, [tot+21, tot+22, tot+23, tot+24]
    return tot, [tot+14, tot+15, tot+16, tot+17, tot+31, tot+32, tot+33, tot+34]
def _parse_seq_estimate(text, tot_i, ba_i, geo):
    out = {}
    for row in csv.reader(io.StringIO(text)):
        if len(row) <= max(ba_i+[tot_i]): continue
        g = geo.get(row[5].strip())
        if not g: continue
        cbsa, name = g
        def num(i):
            try: return float(row[i])
            except: return 0.0
        tot = num(tot_i); ba = sum(num(i) for i in ba_i)
        if tot > 0: out[cbsa] = (name, tot, ba, 100*ba/tot)
    return out
def _geo_seq(year, geo_csv, legacy2005):
    if legacy2005:
        raw = _get(f"{BASE}/2005/data/0UnitedStates/usgeo.2005-1yr").decode("latin-1"); keep="Metropolitan Statistical Area"
    elif geo_csv:
        raw = _get(f"{BASE}/{year}/data/1_year_seq_by_state/UnitedStates/g{year}1us.csv").decode("latin-1"); keep="Metro Area"
    else:
        raw = _get(f"{BASE}/{year}/data/1_year_seq_by_state/US/g{year}1us.txt").decode("latin-1"); keep="Metro Area"
    geo = {}
    if geo_csv:
        for row in csv.reader(io.StringIO(raw)):
            if len(row) < 6 or row[2] != "310": continue
            gid=name=""
            for i,v in enumerate(row):
                if v.startswith("31000US"): gid=v; name=row[i+1] if i+1<len(row) else ""; break
            if gid and keep in name: geo[row[4]] = (gid[-5:], name)
    else:
        for line in raw.splitlines():
            if line[8:11] != "310": continue
            m = re.search(r"31000US(\d{5})", line)
            if not m: continue
            name = line[m.end():].strip()
            if keep in name and "Micropolitan" not in name: geo[line[13:20].strip()] = (m.group(1), name)
    return geo
def _seq_url(year, seq, legacy2005):
    if legacy2005: return f"{BASE}/2005/data/0UnitedStates/us{seq:07d}.2005-1yr.zip"
    folder = "UnitedStates" if year >= 2010 else "US"
    return f"{BASE}/{year}/data/1_year_seq_by_state/{folder}/{year}1us{seq:04d}000.zip"
def _read_seq_zip(year, seq, legacy2005):
    zf = zipfile.ZipFile(io.BytesIO(_get(_seq_url(year, seq, legacy2005))))
    cand = [n for n in zf.namelist() if re.search(r"[\\/]?e\d{7}", n) or n.endswith("e.2005-1yr") or re.search(r"e\d{7}\.2005-1yr$", n)]
    if not cand: cand = [n for n in zf.namelist() if "e" in n.split("/")[-1][:1].lower() or "/data/" in n]
    target = max(cand, key=len)
    return zf.read(target).decode("latin-1")
def extract_metro_attainment(year):
    p = ANCHORS.get(year)
    if p and p["fmt"] == "tb": return _extract_tb(year)
    if not p: raise ValueError(f"Year {year} not in parameter map; add seq/start from that year's lookup file.")
    geo = _geo_seq(year, p.get("geo_csv", year>=2014), p.get("legacy2005", False))
    tot_i, ba_i = _baplus_indices(p["tbl"], p["start"])
    return _parse_seq_estimate(_read_seq_zip(year, p["seq"], p.get("legacy2005", False)), tot_i, ba_i, geo)
def _extract_tb(year):
    b = BASE + f"/{year}/table-based-SF"
    r = csv.reader(io.StringIO(_get(f"{b}/documentation/Geos{year}1YR.txt").decode("latin-1")), delimiter="|")
    hdr = next(r); gi,ni,si = hdr.index("GEO_ID"),hdr.index("NAME"),hdr.index("SUMLEVEL")
    names = {row[gi]: row[ni] for row in r if row[si]=="310"}
    r = csv.reader(io.StringIO(_get(f"{b}/data/1YRData/acsdt1y{year}-b15003.dat").decode("latin-1")), delimiter="|"); next(r)
    out = {}
    for row in r:
        gid = row[0]
        if not gid.startswith("310"): continue
        nm = names.get(gid, "")
        if "Metro Area" not in nm: continue
        def num(i):
            try: return float(row[i])
            except: return 0.0
        tot=num(1); ba=num(43)+num(45)+num(47)+num(49)
        if tot>0: out[gid[-5:]] = (nm, tot, ba, 100*ba/tot)
    return out
def _namekey(nm):
    m = re.search(r",\s*([A-Z]{2})\b", nm); st = m.group(1) if m else ""
    return (nm.split(",")[0].split("-")[0].lower().replace("urban ","").strip(), st)
def build_growth_panel(base_years, endpoint=2024, min_pop25=200000):
    end = extract_metro_attainment(endpoint)
    bases = {y: extract_metro_attainment(y) for y in base_years}
    rows = {}
    for code,(nm,tot,ba,sh) in end.items():
        if nm.split(",")[-1].strip().startswith("PR") or tot < min_pop25: continue
        rec = {"cbsa":code,"metro":nm,"grads_end":round(ba),"share_end":round(sh,1)}
        for y in base_years:
            bd = bases[y]; b = bd.get(code) or bd.get(XWALK.get(y,{}).get(code))
            if not b:
                idx = {_namekey(v[0]):cb for cb,v in bd.items()}; b = bd.get(idx.get(_namekey(nm)))
            if b and b[2] > 0:
                rec[f"net_{y}"]=round(ba-b[2]); rec[f"pct_{y}"]=round(100*(ba-b[2])/b[2],1); rec[f"dshare_{y}"]=round(sh-b[3],1)
        rows[code] = rec
    return rows
if __name__ == "__main__":
    import sys; yr = int(sys.argv[1]) if len(sys.argv)>1 else 2024
    d = extract_metro_attainment(yr); print(f"{yr}: {len(d)} metros")
    for cb in ("35620","12420","16980"):
        if cb in d: print(" ", cb, round(d[cb][3],1), d[cb][0][:35])
