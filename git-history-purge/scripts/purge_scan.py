"""Build and verify git-filter-repo replace rules for a history purge. Prints COUNTS ONLY.

  python -I purge_scan.py scan   <repo.git> <purge-config.json> <rules-out.txt>
  python -I purge_scan.py verify <repo.git> <purge-config.json> <rules.txt>

purge-config.json lives OUTSIDE every repo (it holds the private values):
  {"remove_path_regex": "(^|/)notes/",   # paths filter-repo removes outright
   "values": [123457, -9876.54, ...],     # private figures (a negative value = its absolute value)
   "min_integer": 10000,                  # optional; whole numbers below it are skipped (default 10000)
   "literals": ["Exact private string", ...],
   "phones": true, "public_phones": ["6145550100"],   # 10-digit numbers allowed to stay
   "phone_numbers": ["6145550123"],       # optional; known private numbers, exactly 10 digits each
   "tip_ref": "refs/heads/main"}          # optional; the tree the purge must not change

Every blob is examined under EVERY path it was ever stored at (git log --raw over all
branches and tags), not just the first path rev-list reports. A blob is scanned when at
least one of its paths is kept. Text vs binary is decided by content, as filter-repo does
(a NUL byte in the first 8192 bytes means binary); binary files holding private data must
be removed by path. Commit messages and annotated-tag messages are scanned too.

Figure forms: a whole number gives "123,457", "123457", "123,457.00" and "123457.00"
(round thousands and values below min_integer are skipped: too common to replace safely);
a non-whole value of 1,000 or more gives "9,876.54", "9876.54" and its shortest form
("123,456.5"). A negative value gives the forms of its absolute value, so the written
"-123,457" and "(123,457)" both match (the sign or brackets stay, the digits go). Every
rule is a boundary-anchored regex: digits inside a longer number or a hex hash, and a phone
number inside a longer digit run, are never touched ("inside a hash": a hex character right
after the figure, or 7+ hex characters right before it; a figure after a shorter run of
letters, such as USD123,457 or CAD987653, IS matched). Skipped values are
counted in the output: they are NOT searched, so purge them another way if they matter.

Phones: "phones": true finds dashed/dotted/spaced numbers in the history (public_phones
excepted). "phone_numbers" lists known numbers; each gives one rule covering 614-555-0123,
(614) 555-0123, (614)555-0123, (614)-555-0123, (614)/555-0123, 614.555.0123, 614/555-0123,
614 555 0123 and 6145550123, with an optional "+1" or "1" prefix (+1 614..., 1-614...,
1 (614) 555-0123, 16145550123), never inside a longer digit run. Both kinds are written only when present.
scan and verify exit 2 if a phone_numbers entry is not exactly 10 digits; scan also exits 2
if tip_ref does not exist or a literal contains a line break.

scan   - writes one rule per form ACTUALLY present, drops any rule that matches a blob in
         tip_ref's tree (a purge must leave the tip unchanged; scrub it with a reviewed PR
         first) and writes <rules-out>.paths.txt (affected paths). Also prints how many
         literals occur in file or directory names: text rules never rename paths, so remove
         or rename those by path.
verify - exit 1 if any removed path is still reachable, any rule still matches a blob, a
         commit message or a tag message, OR the independent search finds a configured
         value, literal or phone number anywhere in the object store. That search reads
         every object, not walked by ref or path: text blobs and commit and tag objects
         ("text objects"), binary blobs as raw bytes, and every tree object's file and
         directory names; the three are reported separately and each one fails verify.
         A configured phone number is found in ANY punctuated form: within a span of digit
         groups joined by 1-3 of ()[]./+- or whitespace, consecutive whole groups whose
         digits equal the number (or 1 + the number) count.
         Anything also present in the tip (tip_ref's blobs or its trees' names) is accepted
         and counted as kept at tip. Values skipped by min_integer are not searched and are
         counted. Run it on the rewrite and on a fresh `git clone --bare` (a --mirror clone
         also fetches GitHub's refs/pull/*, which still hold old history).
"""
import json
import re
import subprocess
import sys
from collections import defaultdict

PH = b"[figure: private]"
PH_PHONE = b"[phone: private]"
PHONE_RE = re.compile(rb"(?<![\dA-Za-z])(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}(?!\d)")
HEX = rb"0-9A-Fa-f"
# Before a figure: no digit (a longer number) and no run of 7+ hex characters (a hash). A figure
# glued to fewer letters, such as a currency code (USD123,457, CAD987653), still matches.
NOT_AFTER_NUMBER_OR_HASH = b"(?<![0-9])(?<![" + HEX + b"]{7})"
PHONE_SEP = rb"[-./ ]?"


def git(repo, *a, inp=None):
    return subprocess.run(["git", "-C", repo] + list(a), input=inp, capture_output=True, check=True).stdout


def refs_of(repo):
    return [r for r in git(repo, "for-each-ref", "--format=%(refname)").decode().split()
            if r.startswith(("refs/heads/", "refs/tags/"))]


def blob_paths(repo, refs):
    """sha -> set of every path that blob was ever stored at, across all branches and tags."""
    out = defaultdict(set)
    if not refs:
        return out
    # --branches --tags instead of listing refs: hundreds of ref names exceed the Windows command line.
    raw = git(repo, "log", "-z", "--raw", "--no-abbrev", "--no-renames", "--root", "-m", "--format=",
              "--branches", "--tags")
    toks = raw.split(b"\0")
    i = 0
    while i < len(toks):
        t = toks[i].lstrip(b"\n")
        if t.startswith(b":") and i + 1 < len(toks):
            new = t.split()[3].decode()
            if set(new) != {"0"}:
                out[new].add(toks[i + 1].decode("utf-8", "surrogateescape"))
            i += 2
        else:
            i += 1
    if out:
        kinds = git(repo, "cat-file", "--batch-check=%(objectname) %(objecttype)",
                    inp="\n".join(out).encode()).decode().splitlines()
        blobs = {s for s, t in (k.split() for k in kinds) if t == "blob"}
        out = {s: p for s, p in out.items() if s in blobs}
    return out


def raw_objects(repo, shas):
    """Yield (sha, raw content) for each object."""
    proc = subprocess.Popen(["git", "-C", repo, "cat-file", "--batch"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    try:
        for sha in shas:
            proc.stdin.write((sha + "\n").encode())
            proc.stdin.flush()
            header = proc.stdout.readline().split()
            data = proc.stdout.read(int(header[2]))
            proc.stdout.read(1)
            yield sha, data
    finally:
        proc.stdin.close()
        proc.wait()


def is_binary(data):
    """filter-repo's test: a NUL byte in the first 8192 bytes."""
    return b"\0" in data[:8192]


def text_blobs(repo, shas):
    """Yield (sha, data) for blobs filter-repo treats as text."""
    for sha, data in raw_objects(repo, shas):
        if not is_binary(data):
            yield sha, data


def tree_names(data, hash_len):
    """The entry names of a raw tree object, one per line (the binary object ids left out)."""
    names, i = [], 0
    while i < len(data):
        sp = data.index(b" ", i)
        nul = data.index(b"\0", sp)
        names.append(data[sp + 1:nul])
        i = nul + 1 + hash_len
    return b"\n".join(names)


def messages(repo, refs):
    """Commit messages plus annotated-tag messages, as one bytes blob."""
    if not refs:
        return b""
    msgs = git(repo, "log", "--format=%B%x00", "--branches", "--tags")
    tags = git(repo, "for-each-ref", "--format=%(objecttype)%00%(contents)%00", "refs/tags").split(b"\0")
    for kind, body in zip(tags[0::2], tags[1::2]):
        if kind.strip() == b"tag":
            msgs += body + b"\0"
    return msgs


def history(repo, remove_rx):
    refs = refs_of(repo)
    paths = blob_paths(repo, refs)
    removed = {p for ps in paths.values() for p in ps if remove_rx and remove_rx.search(p)}
    kept = {s: sorted(p for p in ps if not (remove_rx and remove_rx.search(p))) for s, ps in paths.items()}
    kept = {s: ps for s, ps in kept.items() if ps}
    return refs, kept, removed, messages(repo, refs)


def figure_forms(v, min_integer):
    v = abs(v)   # a negative figure is written -123,457 or (123,457): match its digits
    if v == int(v):
        i = int(v)
        if abs(i) < min_integer or i % 1000 == 0:
            return set()
        return {"{:,}".format(i), str(i), "{:,.2f}".format(i), "{:.2f}".format(i)}
    if abs(v) < 1000:
        return set()
    short = repr(float(v))
    whole, _, frac = short.partition(".")
    return {"{:,.2f}".format(v), "{:.2f}".format(v), short, "{:,}".format(int(whole)) + "." + frac}


def num_pattern(form):
    """Anchored pattern for one written form of a figure.

    Always: no digit or 7+ hex run before it and no hex/digit after it (hashes, longer
    numbers; a currency code before it is fine), no decimal point before it (0.123457) or decimal digits after it (123457.12). Only for comma-grouped
    forms: no thousands group before or after (1,123,457 / 123,457,000). A plain form next
    to a comma is a CSV or JSON neighbour (BldgA,123457,2450000), so it still matches.
    """
    pre = NOT_AFTER_NUMBER_OR_HASH + b"(?<![0-9]\\.)"
    post = b"(?:\\.0+)?(?![" + HEX + b"])(?!\\.[0-9])"
    if "," in form:
        if len(form.split(",")[0].lstrip("-")) == 3:
            pre += b"(?<![0-9],)"
        post += b"(?!,[0-9]{3}(?![0-9]))"
    return pre + b"\\$?" + re.escape(form.encode()) + post


def num_rule(form):
    return b"regex:" + num_pattern(form) + b"==>" + PH


def phone_rule(p):
    return b"regex:(?<![0-9A-Za-z])" + re.escape(p) + b"(?![0-9])==>" + PH_PHONE


def phone_numbers(cfg):
    """The configured "phone_numbers" as 10-digit strings, or None if any entry is malformed."""
    nums = [str(n) for n in cfg.get("phone_numbers", [])]
    return nums if all(re.fullmatch(r"[0-9]{10}", n) for n in nums) else None


def number_phone_pattern(n):
    """Every common written form of one 10-digit number, optional +1 / 1 prefix, no longer run."""
    a, b, c = n[:3].encode(), n[3:6].encode(), n[6:].encode()
    return (b"(?<![0-9A-Za-z])(?:\\+?1" + PHONE_SEP + b")?(?:\\(" + a + b"\\)" + PHONE_SEP + b"|"
            + a + PHONE_SEP + b")" + b + PHONE_SEP + c + b"(?![0-9])")


class PhoneDigits:
    """Verify's loose search for one configured phone number, in any punctuated form.

    A span is digit groups joined by 1-3 of ()[]./+- or whitespace. Any run of consecutive
    WHOLE groups whose digits equal the number (or 1 + the number) is one occurrence, so the
    number is never found inside a longer digit run. Same search/findall API as a regex.
    """
    SPAN = re.compile(rb"[0-9]+(?:[\s()\[\]./+-]{1,3}[0-9]+)*")
    GROUP = re.compile(rb"[0-9]+")

    def __init__(self, n):
        self.targets = {n.encode(), b"1" + n.encode()}

    def findall(self, data):
        hits = []
        for span in self.SPAN.finditer(data):
            groups = self.GROUP.findall(span.group(0))
            i = 0
            while i < len(groups):
                acc, j = b"", i
                while j < len(groups) and len(acc) < 11 and acc not in self.targets:
                    acc += groups[j]
                    j += 1
                if acc in self.targets:
                    hits.append(acc)
                    i = j
                else:
                    i += 1
        return hits

    def search(self, data):
        return bool(self.findall(data))


def number_phone_rule(n):
    return b"regex:" + number_phone_pattern(n) + b"==>" + PH_PHONE


def lit_rule(s):
    return b"regex:" + re.escape(s.encode("utf-8")) + b"==>" + PH


def rule_regex(rule):
    pat = rule.rpartition(b"==>")[0]
    return re.compile(pat[6:]) if pat.startswith(b"regex:") else re.compile(re.escape(pat))


def scan(repo, cfg, out):
    remove_rx = re.compile(cfg["remove_path_regex"]) if cfg.get("remove_path_regex") else None
    min_int = int(cfg.get("min_integer", 10000))
    public = set(cfg.get("public_phones", []))
    if any("\n" in s or "\r" in s for s in cfg.get("literals", [])):
        print("a literal contains a line break: filter-repo rules are one per line; split it into one literal per line")
        return 2
    nums = phone_numbers(cfg)
    if nums is None:
        print("phone_numbers: every entry must be exactly 10 digits")
        return 2
    refs, kept, _, msgs = history(repo, remove_rx)
    tip_ref = cfg.get("tip_ref", "refs/heads/main")
    if tip_ref not in refs:
        print("tip_ref %s not found: set \"tip_ref\" in the config to the branch whose tree must not change" % tip_ref)
        return 2
    texts = dict(text_blobs(repo, list(kept)))
    corpus = list(texts.values()) + [msgs]

    candidates = []   # (kind, rule)
    skipped = 0
    for v in cfg.get("values", []):
        forms = figure_forms(v, min_int)
        skipped += 0 if forms else 1
        candidates += [("number", num_rule(f)) for f in sorted(forms, key=len, reverse=True)]
    candidates += [("literal", lit_rule(s)) for s in cfg.get("literals", [])]
    if cfg.get("phones"):
        phones = set()
        for d in corpus:
            for m in PHONE_RE.finditer(d):
                if re.sub(rb"\D", b"", m.group(0))[-10:].decode() not in public:
                    phones.add(m.group(0))
        candidates += [("phone", phone_rule(p)) for p in sorted(phones, key=len, reverse=True)]
    candidates += [("phone", number_phone_rule(n)) for n in nums]

    present = []
    for kind, rule in dict.fromkeys(candidates):
        rx = rule_regex(rule)
        if any(rx.search(d) for d in corpus):
            present.append((kind, rule))

    ls = git(repo, "ls-tree", "-r", tip_ref).decode().splitlines()
    tip = [d for _, d in text_blobs(repo, [l.split()[2] for l in ls if l.split()[1] == "blob"])]
    keep = [(k, r) for k, r in present if not any(rule_regex(r).search(d) for d in tip)]

    rxs = [rule_regex(r) for _, r in keep]
    hit_paths = {p for s, d in texts.items() if any(x.search(d) for x in rxs) for p in kept[s]}
    with open(out, "wb") as fh:
        fh.write(b"\n".join(r for _, r in keep) + (b"\n" if keep else b""))
    with open(out + ".paths.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(sorted(hit_paths)) + "\n")
    count = lambda rows, k: sum(1 for kind, _ in rows if kind == k)
    print("blobs scanned: %d; affected paths: %d" % (len(texts), len(hit_paths)))
    print("found: numbers %d, literals %d, phones %d"
          % (count(present, "number"), count(present, "literal"), count(present, "phone")))
    print("rules written: %d; dropped (present at tip): %d" % (len(keep), len(present) - len(keep)))
    print("values skipped (round thousands or below threshold, NOT searched): %d" % skipped)
    names = {p.encode("utf-8", "surrogateescape") for ps in kept.values() for p in ps}
    in_names = sum(1 for lit in cfg.get("literals", []) if any(lit.encode("utf-8") in n for n in names))
    print("literals found in file names: %d (filter-repo text rules do not rename paths; "
          "remove or rename by path)" % in_names)
    return 0


def residual(repo, cfg, tip_ref):
    """Independent of the scan's rules: search every object for every configured value.

    Every object in the store, not walked by ref or path: text blobs plus commit and tag
    objects ("text"), binary blobs as raw bytes ("binary") and the file/directory names in
    every tree object ("names"). Loose patterns (only digit/hash neighbours excluded; a phone
    number in any punctuated form, see PhoneDigits), so a
    value the rules missed - wrong form, odd context, unusual file - still shows up. A value
    also present in the tip (tip_ref's blobs or its trees' names) is kept at the tip
    (accepted) and not counted as residual.
    Returns dict: left (values with a residual), occ, at_tip, skipped, and per category
    (text/binary/names) a [values, occurrences] pair.
    """
    min_int = int(cfg.get("min_integer", 10000))
    pats, skipped = [], 0
    for v in cfg.get("values", []):
        forms = figure_forms(v, min_int)
        if not forms:
            skipped += 1
            continue
        alt = b"|".join(re.escape(f.encode()) for f in sorted(forms, key=len, reverse=True))
        pats.append(re.compile(NOT_AFTER_NUMBER_OR_HASH + b"(?:" + alt + b")(?![" + HEX + b"])"))
    pats += [re.compile(re.escape(s.encode("utf-8"))) for s in cfg.get("literals", [])]
    pats += [PhoneDigits(n) for n in phone_numbers(cfg) or []]

    lst = git(repo, "cat-file", "--batch-all-objects", "--batch-check=%(objectname) %(objecttype)").decode()
    kinds = dict(l.split() for l in lst.splitlines() if l)

    def searchable(objs):
        """Yield (sha, category, bytes to search)."""
        for sha, data in objs:
            kind = kinds.get(sha)
            if kind == "tree":
                yield sha, "names", tree_names(data, len(sha) // 2)
            elif kind == "blob" and is_binary(data):
                yield sha, "binary", data
            else:
                yield sha, "text", data

    tip = set()
    if tip_ref:
        tip = {l.split()[2] for l in git(repo, "ls-tree", "-r", "-t", tip_ref).decode().splitlines()
               if l.split()[1] in ("blob", "tree")}
        tip.add(git(repo, "rev-parse", tip_ref + "^{tree}").decode().strip())
    at_tip = set()
    for _, _, data in searchable(raw_objects(repo, sorted(tip))):
        at_tip |= {i for i, rx in enumerate(pats) if rx.search(data)}

    cats = {"text": [set(), 0], "binary": [set(), 0], "names": [set(), 0]}
    wanted = [sha for sha, k in kinds.items() if k in ("blob", "tree", "commit", "tag") and sha not in tip]
    for _, cat, data in searchable(raw_objects(repo, wanted)):
        for i, rx in enumerate(pats):
            if i in at_tip:
                continue
            n = len(rx.findall(data))
            if n:
                cats[cat][0].add(i)
                cats[cat][1] += n
    left = set().union(*(c[0] for c in cats.values()))
    return {"left": len(left), "occ": sum(c[1] for c in cats.values()), "at_tip": len(at_tip),
            "skipped": skipped, **{k: [len(c[0]), c[1]] for k, c in cats.items()}}


def verify(repo, cfg, rules_path):
    remove_rx = re.compile(cfg["remove_path_regex"]) if cfg.get("remove_path_regex") else None
    with open(rules_path, "rb") as fh:
        rxs = [rule_regex(r) for r in fh.read().splitlines() if r]
    if phone_numbers(cfg) is None:
        print("phone_numbers: every entry must be exactly 10 digits")
        return 2
    refs, kept, removed, msgs = history(repo, remove_rx)
    tip_ref = cfg.get("tip_ref", "refs/heads/main")
    if tip_ref not in refs:
        print("tip_ref %s not found" % tip_ref)
        return 2
    hit_blobs = sum(1 for _, d in text_blobs(repo, list(kept)) if any(x.search(d) for x in rxs))
    msg_hits = sum(len(x.findall(msgs)) for x in rxs)
    res = residual(repo, cfg, tip_ref)
    print("removed paths still reachable: %d" % len(removed))
    print("blobs checked: %d; blobs matching a rule: %d; message hits: %d" % (len(kept), hit_blobs, msg_hits))
    print("independent search of every object: values still present: %d (%d occurrences); "
          "kept at tip (accepted): %d" % (res["left"], res["occ"], res["at_tip"]))
    print("  in text objects: %d (%d occurrences); in binary blobs: %d (%d occurrences); "
          "in file names: %d (%d occurrences)" % tuple(res["text"] + res["binary"] + res["names"]))
    print("  values skipped (round thousands or below min_integer, NOT searched): %d" % res["skipped"])
    return 1 if (removed or hit_blobs or msg_hits or res["left"]) else 0


def main(argv):
    if len(argv) != 5 or argv[1] not in ("scan", "verify"):
        print(__doc__)
        return 2
    with open(argv[3], encoding="utf-8") as fh:
        cfg = json.load(fh)
    return (scan if argv[1] == "scan" else verify)(argv[2], cfg, argv[4])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
