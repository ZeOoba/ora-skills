"""Build and verify git-filter-repo replace rules for a history purge. Prints counts, plus (verify)
ref names, paths and blob/commit ids with every configured value masked; never a value itself.

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
branches, tags and notes refs), not just the first path rev-list reports. Notes refs
(refs/notes/*) are read like branches wherever present: their note blobs, commit messages and
ref names (scan and verify print "notes refs read: <n>"). A blob is scanned when at
least one of its paths is kept. Text vs binary is decided by content, as filter-repo does
(a NUL byte in the first 8192 bytes means binary); binary files holding private data must
be removed by path. Commit messages and annotated-tag messages are scanned too.

Figure forms: a whole number gives "123,457", "123457", "123,457.00" and "123457.00"
(round thousands and values below min_integer are skipped: too common to replace safely);
a non-whole value of 1,000 or more gives "9,876.54", "9876.54" and its shortest form
("123,456.5"). A negative value gives the forms of its absolute value, so the written
"-123,457" and "(123,457)" both match (the sign or brackets stay, the digits go). Every
rule is a boundary-anchored regex: digits inside a longer number or a hex hash, and a phone
number inside a longer digit run, are never touched ("inside a hash": 7+ hex characters
right before the figure, or right after it a run of hex characters holding a digit
(123457ab9f) or of 4+ hex letters ending at a non-letter (123457deadbeef)). A figure next to
a short run of letters IS matched: USD123,457, CAD987653, 123,457EUR, 987653CAD, 123457ABC
(1-3 letters after it), 987,653DEADLINE (a longer word). Skipped values are
counted in the output: they are NOT searched, so purge them another way if they matter.

Phones: "phones": true finds dashed/dotted/spaced numbers in the history (public_phones
excepted). "phone_numbers" lists known numbers; each gives one rule covering 614-555-0123,
(614) 555-0123, (614)555-0123, (614)-555-0123, (614)/555-0123, 614.555.0123, 614/555-0123,
614 555 0123, 614 - 555 - 0123 and 6145550123, with an optional "+1" or "1" prefix (+1 614...,
1-614..., 1 (614) 555-0123, 16145550123), never inside a longer digit run. Both kinds accept
the Unicode dashes U+2010..U+2015 and minus U+2212 wherever a - is accepted, and the no-break
(U+00A0), thin (U+2009) and narrow no-break (U+202F) spaces wherever a space is. Both kinds are
written only when present.
scan and verify exit 2 if a phone_numbers entry is not exactly 10 digits; scan also exits 2
if tip_ref does not exist or a literal contains a line break.

scan   - writes one rule per form ACTUALLY present, drops any rule that matches a blob in
         tip_ref's tree (a purge must leave the tip unchanged; scrub it with a reviewed PR
         first) and writes <rules-out>.paths.txt (affected paths). Also prints how many
         literals occur in file or directory names: text rules never rename paths, so remove
         or rename those by path.
verify - exit 1 if any removed path is still reachable, any rule still matches a blob, a
         commit message or a tag message, OR the independent search finds a configured
         value, literal or phone number anywhere in the object store, OR a branch, tag or
         notes ref name holds a configured value or matches a rule (filter-repo never renames refs;
         each is printed as REF-NAME with the value masked: rename or delete it in the
         rewritten copy). The object search reads every object, not walked by ref or path:
         text blobs and commit and tag objects ("text objects"), binary blobs ("binary"),
         and every tree object's file and directory names; the three are reported
         separately and each one fails verify. A binary blob is searched as raw bytes plus
         what verify can decode from it: every member of a zip container (xlsx, docx, pptx,
         zip; a zip or PDF inside it one level deep, e.g. an embedded workbook), each member
         again with its XML tags removed (a figure Word split across runs reads whole), and
         the member names; UTF-16 LE/BE text (byte-order mark, or mostly-NUL odd/even bytes);
         a PDF's FlateDecode (or /Fl) and unfiltered streams, each decoded stream read again
         the same way (an attached xlsx is opened), plus the text of its literal (...) and hex
         <...> strings with the pieces of a TJ array joined. A blob verify cannot read inside -
         an encrypted zip member or PDF, a zip member or PDF stream under another compression
         or filter (images in a PDF), PDF text drawn with a font's own glyph codes
         (Identity-H/V), a container nested more than one level deep, an image file, a
         gzip/bzip2/xz/7z/rar archive, a legacy Office (OLE2) file - is listed
         at the end as OPAQUE <blob> path=<a path> commit=<a commit> ref=<a branch, tag or
         notes ref that reaches the commit> reason=<why>; OPAQUE
         does not change the exit code: open each one and check it, or remove it by path.
         A configured phone number is found in ANY punctuated form: within a span of digit
         groups joined by 1-4 of ()[]./+-, whitespace, a Unicode dash or a no-break/thin
         space, consecutive whole groups whose digits equal the number (or 1 + the number).
         Anything also present in the tip (tip_ref's blobs, what verify decodes from them,
         or its trees' names) is accepted and counted as kept at tip. Values skipped by
         min_integer are not searched and are counted. Names verify prints (REF-NAME,
         OPAQUE paths and zip member names) have every configured value and rule match
         replaced by [private]. Run it on the rewrite and on a fresh `git clone --bare` (a
         --mirror clone also fetches GitHub's refs/pull/*, which still hold old history).
"""
import io
import json
import re
import subprocess
import sys
import zipfile
import zlib
from collections import defaultdict

PH = b"[figure: private]"
PH_PHONE = b"[phone: private]"
MASK = b"[private]"     # replaces a matched value in a ref name or path that verify prints
HEX = rb"0-9A-Fa-f"
# Before a figure: no digit (a longer number) and no run of 7+ hex characters (a hash). A figure
# glued to fewer letters, such as a currency code (USD123,457, CAD987653), still matches.
NOT_AFTER_NUMBER_OR_HASH = b"(?<![0-9])(?<![" + HEX + b"]{7})"
# After a figure (R2-10): no digit, and no hash-like run of hex characters: one holding a digit
# (123457ab9f0e) or 4+ hex letters ending at a non-letter (123457deadbeef). A currency code or
# other short letter run (123,457EUR, 987653CAD, 123457ABC) and a longer word (987,653DEADLINE)
# still match.
NOT_BEFORE_NUMBER_OR_HASH = b"(?![A-Fa-f]*[0-9])(?![A-Fa-f]{4,}(?![A-Za-z]))"
# Phone separators (R2-13), as UTF-8 bytes. Dashes: ASCII - and ., the Unicode dashes
# U+2010..U+2015 and minus U+2212. Spaces: ASCII space, no-break U+00A0, thin U+2009 and
# narrow no-break U+202F.
DASH = rb"(?:[-.]|\xe2\x80[\x90-\x95]|\xe2\x88\x92)"
SPACE = rb"(?:[ ]|\xc2\xa0|\xe2\x80[\x89\xaf])"
ONE_SEP = b"(?:" + DASH + b"|" + SPACE + b")"
PHONE_RE = re.compile(rb"(?<![\dA-Za-z])(?:\+?1" + ONE_SEP + rb"?)?\(?\d{3}\)?" + ONE_SEP + rb"\d{3}"
                      + ONE_SEP + rb"\d{4}(?!\d)")
# A configured number's rule: no separator, one, or a dash or slash with a space on either side.
PHONE_SEP = b"(?:" + SPACE + b"?(?:" + DASH + b"|/)" + SPACE + b"?|" + SPACE + b")?"


def git(repo, *a, inp=None):
    return subprocess.run(["git", "-C", repo] + list(a), input=inp, capture_output=True, check=True).stdout


NOTES = "--glob=refs/notes/*"   # R3-05: notes refs are read like branches and tags wherever present


def refs_of(repo):
    """Branches, tags and notes refs (whose commits hold each note as a blob)."""
    return [r for r in git(repo, "for-each-ref", "--format=%(refname)").decode().split()
            if r.startswith(("refs/heads/", "refs/tags/", "refs/notes/"))]


def blob_paths(repo, refs):
    """sha -> set of every path that blob was ever stored at, across all branches and tags."""
    out = defaultdict(set)
    if not refs:
        return out
    # --branches --tags instead of listing refs: hundreds of ref names exceed the Windows command line.
    raw = git(repo, "log", "-z", "--raw", "--no-abbrev", "--no-renames", "--root", "-m", "--format=",
              "--branches", "--tags", NOTES)
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


MAX_MEMBER = 256 << 20          # a zip member larger than this is not decompressed (zip bomb)
OPAQUE_MAGIC = ((b"\x89PNG", "image (PNG)"), (b"\xff\xd8\xff", "image (JPEG)"), (b"GIF8", "image (GIF)"),
                (b"II*\x00", "image (TIFF)"), (b"MM\x00*", "image (TIFF)"), (b"BM", "image (BMP)"),
                (b"\x1f\x8b", "compressed (gzip)"),
                (b"BZh", "compressed (bzip2)"), (b"\xfd7zXZ\x00", "compressed (xz)"),
                (b"7z\xbc\xaf\x27\x1c", "compressed (7z)"), (b"Rar!", "compressed (rar)"),
                (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "legacy Office/OLE2 file"))


def utf16_text(data):
    """data decoded as UTF-16 and re-encoded as UTF-8, or None if it does not look like UTF-16:
    a byte-order mark, or (no BOM) NUL bytes on over 30% of the odd (LE) or even (BE) positions
    of the first 4096 bytes and four times as many as on the other positions."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        enc = "utf-16"
    else:
        sample = data[:4096]
        even, odd, half = sample[0::2].count(0), sample[1::2].count(0), len(sample) // 2
        if half < 2:
            return None
        if odd > 0.3 * half and odd > 4 * even:
            enc = "utf-16-le"
        elif even > 0.3 * half and even > 4 * odd:
            enc = "utf-16-be"
        else:
            return None
    return data[:len(data) // 2 * 2].decode(enc, "replace").encode("utf-8")


STREAM_RE = re.compile(rb"(?<![A-Za-z])stream\r?\n")


def pdf_streams(data):
    """(streams, opaque reasons) for a PDF: each stream as (content, filtered); FlateDecode (or
    its /Fl abbreviation) is decompressed and an unfiltered stream is taken as is (best effort); a
    stream under any other filter, damaged Flate data or encryption is opaque."""
    if re.search(rb"/Encrypt\b", data):
        return [], {"encrypted PDF"}
    streams, opaque = [], set()
    for m in STREAM_RE.finditer(data):
        end = data.find(b"endstream", m.end())
        if end < 0:
            break
        head = data[max(0, data.rfind(b"obj", 0, m.start())):m.start()]
        f = re.search(rb"/Filter\s*(\[[^\]]*\]|/[A-Za-z0-9]+)", head)
        names = re.findall(rb"/([A-Za-z0-9]+)", f.group(1)) if f else []
        if not names:
            streams.append((data[m.end():end], False))
            continue
        if names in ([b"FlateDecode"], [b"Fl"]):
            try:
                streams.append((zlib.decompressobj().decompress(data[m.end():end]), True))
                continue
            except zlib.error:
                opaque.add("PDF stream with damaged Flate data")
                continue
        opaque.add("PDF stream filter " + "+".join(n.decode("ascii") for n in names))
    return streams, opaque


PDF_TOKEN = re.compile(rb"[\[\]()<%]")
PDF_ESC = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}


LITERAL_STOP = re.compile(rb"[()\\]")
HEX_STRING = re.compile(rb"<([0-9A-Fa-f\s]*)>")


def pdf_literal(data, i):
    """(decoded bytes, index after it) of the PDF literal string starting at data[i] == "(":
    balanced parentheses, backslash escapes and 1-3 digit octal codes."""
    out, depth, i = bytearray(), 1, i + 1
    while True:
        m = LITERAL_STOP.search(data, i)
        if not m:
            out += data[i:]
            return bytes(out), len(data)
        out += data[i:m.start()]
        i = m.start()
        c = data[i:i + 1]
        if c == b"\\":
            nxt = data[i + 1:i + 2]
            octal = re.match(rb"[0-7]{1,3}", data[i + 1:i + 4])
            if octal:
                out.append(int(octal.group(0), 8) & 0xFF)
                i += 1 + len(octal.group(0))
            elif nxt in (b"\r", b"\n"):                     # line continuation
                i += 2 + (data[i + 1:i + 3] == b"\r\n")
            else:
                out += PDF_ESC.get(nxt, nxt)
                i += 2
            continue
        depth += 1 if c == b"(" else -1
        if not depth:
            return bytes(out), i + 1
        out += c
        i += 1


def pdf_strings(data):
    """The text a PDF content holds in its strings: every literal (...) and hex <...> string
    decoded; the pieces of one TJ array (or any [...] array) joined with nothing between them, so
    a figure split by kerning ([(987,)-15(653)] TJ) reads whole; separate strings on separate
    lines. Empty if there are none."""
    lines, cur, depth, i = [], [], 0, 0
    while True:
        m = PDF_TOKEN.search(data, i)
        if not m:
            break
        c, i = m.group(0), m.start()
        if c == b"(":
            s, i = pdf_literal(data, i)
            (cur if depth else lines).append(s)
            continue
        if c == b"<":
            if data[i + 1:i + 2] == b"<":                  # a dictionary, not a string
                i += 2
                continue
            h = HEX_STRING.match(data, i)
            if h:
                digits = re.sub(rb"\s", b"", h.group(1))
                s = bytes.fromhex((digits + b"0" * (len(digits) % 2)).decode("ascii"))
                (cur if depth else lines).append(s)
                i = h.end()
                continue
        elif c == b"[":
            depth += 1
        elif c == b"]" and depth:
            depth -= 1
            if not depth:
                lines.append(b"".join(cur))
                cur = []
        elif c == b"%":                                   # a comment runs to the end of the line
            e = re.compile(rb"[\r\n]").search(data, i)
            i = e.start() if e else len(data)
            continue
        i += 1
    if cur:
        lines.append(b"".join(cur))
    return b"\n".join(l for l in lines if l)


# Closing a paragraph, table cell or spreadsheet cell, or a tab or line break, ends a piece of
# text; every other tag (a run, its properties, a proofing mark) sits INSIDE one, so it is removed
# with nothing in its place. "Price 987,</w:t></w:r><w:r><w:t>653" then reads "Price 987,653".
XML_TAG = re.compile(rb"<(/?)(?:[A-Za-z0-9_.-]+:)?([A-Za-z0-9_.-]+)[^<>]*>")
XML_BREAK = {b"p", b"tc", b"tr", b"td", b"th", b"tab", b"br", b"cr", b"c", b"si", b"row", b"li", b"div"}


def xml_text(data):
    """data with its XML tags removed (see XML_BREAK), or None if it has none."""
    if b"<" not in data or not XML_TAG.search(data):
        return None
    return XML_TAG.sub(lambda m: b"\n" if m.group(2) in XML_BREAK else b"", data)


GLYPH_CODES = re.compile(rb"/Identity-[HV](?![A-Za-z0-9])")


def expand(data, depth=0):
    """(parts, opaque): the byte strings verify searches for one blob, and the reasons any part
    of it could not be read (empty if none). A zip container (xlsx/docx/pptx/zip) gives every
    member's name, content, and content with its XML tags removed (text split across runs), opening
    a zip or PDF inside it one level deep. A PDF gives its raw bytes, each FlateDecode or
    unfiltered stream run through expand() again (an attached xlsx is read), and the text of its
    literal and hex strings with TJ array pieces joined; text drawn with a font's glyph codes
    (Identity-H/V) is opaque. UTF-16 text gives its raw bytes plus the text as UTF-8; an image,
    another compressed format or a legacy Office (OLE2) file is opaque."""
    if data[:4] in (b"PK\x03\x04", b"PK\x05\x06"):
        if depth >= 2:
            return [data], {"zip nested more than one level"}
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
            infos = z.infolist()
        except (zipfile.BadZipFile, zipfile.LargeZipFile, ValueError, EOFError, OSError):
            return [data], {"unreadable zip"}
        parts, opaque = [b"\n".join(i.filename.encode("utf-8", "surrogateescape") for i in infos)], set()
        for info in infos:
            if info.is_dir():
                continue
            if info.flag_bits & 1:
                opaque.add("encrypted zip member " + info.filename)
                continue
            if info.file_size > MAX_MEMBER:
                opaque.add("zip member too large " + info.filename)
                continue
            try:
                member = z.read(info)
            except (NotImplementedError, RuntimeError, zipfile.BadZipFile, zlib.error, EOFError, OSError):
                opaque.add("zip member with unknown compression or damaged " + info.filename)
                continue
            sub, why = expand(member, depth + 1)
            parts += sub
            text = None if is_binary(member) else xml_text(member)
            if text is not None:
                parts.append(text)
            opaque |= {info.filename + ": " + w for w in why}
        return parts, opaque
    if data[:5] == b"%PDF-":
        if depth >= 2:
            return [data], {"PDF nested more than one level"}
        streams, opaque = pdf_streams(data)
        pieces = STREAM_RE.split(data)                   # the strings outside every stream too
        parts = [data, pdf_strings(pieces[0] + b"".join(p.split(b"endstream", 1)[-1] for p in pieces[1:]))]
        for content, filtered in streams:
            sub, why = expand(content, depth + 1)
            parts += [p for p in sub if filtered or p is not content]
            parts.append(pdf_strings(content))
            opaque |= {"PDF stream: " + w for w in why}
            if GLYPH_CODES.search(content):
                opaque.add("PDF text in font glyph codes (Identity-H/V)")
        if GLYPH_CODES.search(data):
            opaque.add("PDF text in font glyph codes (Identity-H/V)")
        return [p for p in parts if p], opaque
    text = utf16_text(data) if is_binary(data) or data[:2] in (b"\xff\xfe", b"\xfe\xff") else None
    if text is not None:
        return [data, text], set()
    if is_binary(data):
        for magic, why in OPAQUE_MAGIC:
            if data.startswith(magic):
                return [data], {why}
    return [data], set()


def mask(data, patterns):
    """data with every match of every pattern replaced by MASK, for printing a name verify found."""
    for p in patterns:
        data = p.sub(MASK, data)
    return data


def blob_origins(repo, shas):
    """sha -> (a path, a commit, a ref reaching that commit) that stored it, from branches, tags
    and notes refs; absent if unreachable."""
    want, out, commit, ref = set(shas), {}, "", b""
    toks = git(repo, "log", "-z", "--raw", "--no-abbrev", "--no-renames", "--root", "-m", "--source",
               "--format=%x01%H %S", "--branches", "--tags", NOTES).split(b"\0")
    i = 0
    while i < len(toks):
        t = toks[i].lstrip(b"\n")
        if t.startswith(b"\x01"):
            c, _, ref = t[1:].partition(b" ")
            commit = c.decode()
        elif t.startswith(b":") and i + 1 < len(toks):
            new = t.split()[3].decode()
            if new in want and new not in out:
                out[new] = (toks[i + 1], commit, ref)
            i += 1
        i += 1
    return out


def messages(repo, refs):
    """Commit messages plus annotated-tag messages, as one bytes blob."""
    if not refs:
        return b""
    msgs = git(repo, "log", "--format=%B%x00", "--branches", "--tags", NOTES)
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
    post = b"(?:\\.0+)?" + NOT_BEFORE_NUMBER_OR_HASH + b"(?!\\.[0-9])"
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

    A span is digit groups joined by 1-4 of ()[]./+-, whitespace, a Unicode dash (U+2010..U+2015,
    U+2212) or a no-break/thin space (U+00A0, U+2009, U+202F). Any run of consecutive WHOLE
    groups whose digits equal the number (or 1 + the number) is one occurrence, so the number is
    never found inside a longer digit run. Same search/findall/sub API as a regex.
    """
    JOIN = rb"(?:[\s()\[\]./+-]|\xe2\x80[\x90-\x95\x89\xaf]|\xe2\x88\x92|\xc2\xa0)"
    SPAN = re.compile(rb"[0-9]+(?:" + JOIN + rb"{1,4}[0-9]+)*")
    GROUP = re.compile(rb"[0-9]+")

    def __init__(self, n):
        self.targets = {n.encode(), b"1" + n.encode()}

    def spans(self, data):
        """(start, end) of each occurrence."""
        out = []
        for span in self.SPAN.finditer(data):
            groups = list(self.GROUP.finditer(data, span.start(), span.end()))
            i = 0
            while i < len(groups):
                acc, j = b"", i
                while j < len(groups) and len(acc) < 11 and acc not in self.targets:
                    acc += groups[j].group(0)
                    j += 1
                if acc in self.targets:
                    out.append((groups[i].start(), groups[j - 1].end()))
                    i = j
                else:
                    i += 1
        return out

    def findall(self, data):
        return [data[a:b] for a, b in self.spans(data)]

    def search(self, data):
        return bool(self.spans(data))

    def sub(self, repl, data):
        for a, b in reversed(self.spans(data)):
            data = data[:a] + repl + data[b:]
        return data


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
    print("notes refs read: %d" % sum(1 for r in refs if r.startswith("refs/notes/")))
    print("found: numbers %d, literals %d, phones %d"
          % (count(present, "number"), count(present, "literal"), count(present, "phone")))
    print("rules written: %d; dropped (present at tip): %d" % (len(keep), len(present) - len(keep)))
    print("values skipped (round thousands or below threshold, NOT searched): %d" % skipped)
    names = {p.encode("utf-8", "surrogateescape") for ps in kept.values() for p in ps}
    in_names = sum(1 for lit in cfg.get("literals", []) if any(lit.encode("utf-8") in n for n in names))
    print("literals found in file names: %d (filter-repo text rules do not rename paths; "
          "remove or rename by path)" % in_names)
    return 0


def value_patterns(cfg):
    """(patterns, skipped): verify's loose search pattern for each configured value, literal and
    phone number, and how many values min_integer / round thousands left unsearched."""
    min_int = int(cfg.get("min_integer", 10000))
    pats, skipped = [], 0
    for v in cfg.get("values", []):
        forms = figure_forms(v, min_int)
        if not forms:
            skipped += 1
            continue
        alt = b"|".join(re.escape(f.encode()) for f in sorted(forms, key=len, reverse=True))
        pats.append(re.compile(NOT_AFTER_NUMBER_OR_HASH + b"(?:" + alt + b")" + NOT_BEFORE_NUMBER_OR_HASH))
    pats += [re.compile(re.escape(s.encode("utf-8"))) for s in cfg.get("literals", [])]
    pats += [PhoneDigits(n) for n in phone_numbers(cfg) or []]
    return pats, skipped


def residual(repo, cfg, tip_ref):
    """Independent of the scan's rules: search every object for every configured value.

    Every object in the store, not walked by ref or path: text blobs plus commit and tag
    objects ("text"), binary blobs as raw bytes plus whatever expand() decodes from them -
    zip members, PDF Flate streams, UTF-16 text ("binary") - and the file/directory names in
    every tree object ("names"). Loose patterns (only digit/hash neighbours excluded; a phone
    number in any punctuated form, see PhoneDigits), so a
    value the rules missed - wrong form, odd context, unusual file - still shows up. A value
    also present in the tip (tip_ref's blobs or its trees' names) is kept at the tip
    (accepted) and not counted as residual.
    Returns dict: left (values with a residual), occ, at_tip, skipped, per category
    (text/binary/names) a [values, occurrences] pair, searched/all (patterns), opaque
    ({blob sha: reasons} outside the tip) and opaque_at_tip (a count).
    """
    pats, skipped = value_patterns(cfg)
    lst = git(repo, "cat-file", "--batch-all-objects", "--batch-check=%(objectname) %(objecttype)").decode()
    kinds = dict(l.split() for l in lst.splitlines() if l)
    opaque = {}

    def searchable(objs):
        """Yield (sha, category, bytes to search); a blob may yield several parts (expand)."""
        for sha, data in objs:
            kind = kinds.get(sha)
            if kind == "tree":
                yield sha, "names", tree_names(data, len(sha) // 2)
            elif kind == "blob":
                parts, why = expand(data)
                if why:
                    opaque[sha] = why
                cat = "binary" if (is_binary(data) or len(parts) > 1 or why) else "text"
                for part in parts:
                    yield sha, cat, part
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
    opaque_at_tip = len(opaque)
    opaque.clear()

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
            "skipped": skipped, **{k: [len(c[0]), c[1]] for k, c in cats.items()},
            "searched": [p for i, p in enumerate(pats) if i not in at_tip], "all": pats,
            "opaque": opaque, "opaque_at_tip": opaque_at_tip}


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
    # R2-13: filter-repo rewrites contents, never ref names. A name is printed with every value masked.
    names = [r.encode("utf-8", "surrogateescape") for r in refs]
    ref_hits = [n for n in names if any(p.search(n) for p in rxs + res["searched"])]
    printable = lambda b: mask(b, rxs + res["all"]).decode("utf-8", "backslashreplace")
    print("removed paths still reachable: %d" % len(removed))
    print("notes refs read: %d" % sum(1 for r in refs if r.startswith("refs/notes/")))
    print("blobs checked: %d; blobs matching a rule: %d; message hits: %d" % (len(kept), hit_blobs, msg_hits))
    print("independent search of every object: values still present: %d (%d occurrences); "
          "kept at tip (accepted): %d" % (res["left"], res["occ"], res["at_tip"]))
    print("  in text objects: %d (%d occurrences); in binary blobs: %d (%d occurrences); "
          "in file names: %d (%d occurrences)" % tuple(res["text"] + res["binary"] + res["names"]))
    print("  values skipped (round thousands or below min_integer, NOT searched): %d" % res["skipped"])
    print("branch and tag names holding a value or matching a rule: %d (filter-repo does not rename refs; "
          "rename or delete them in the rewritten copy)" % len(ref_hits))
    for n in ref_hits:
        print("REF-NAME " + printable(n))
    opaque = res["opaque"]
    print("opaque blobs (NOT searched inside): %d; at tip (accepted): %d. Open each one and check it, "
          "or remove it by path" % (len(opaque), res["opaque_at_tip"]))
    origins = blob_origins(repo, opaque) if opaque else {}
    for sha in sorted(opaque):
        path, commit, ref = origins.get(sha, (b"(none)", "(unreachable)", b"(none)"))
        why = "; ".join(sorted(opaque[sha])).encode("utf-8", "surrogateescape")
        print("OPAQUE %s path=%s commit=%s ref=%s reason=%s"
              % (sha, printable(path), commit, printable(ref), printable(why)))
    return 1 if (removed or hit_blobs or msg_hits or res["left"] or ref_hits) else 0


def main(argv):
    if len(argv) != 5 or argv[1] not in ("scan", "verify"):
        print(__doc__)
        return 2
    with open(argv[3], encoding="utf-8") as fh:
        cfg = json.load(fh)
    return (scan if argv[1] == "scan" else verify)(argv[2], cfg, argv[4])


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")
    sys.exit(main(sys.argv))
