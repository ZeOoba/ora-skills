# deal-execution — redline revision encodings

Moved out of `SKILL.md` on 2026-09-22 (body split). Companion to Workflow 2 Step 0 and `scripts/extract_revisions.py`.

## Why the detector runs first

**Do not assume the file carries OOXML tracked changes.** Counsel running Litera Compare (formerly DeltaView / Change-Pro), Workshare Compare, or Word's own Compare Documents deliver a FLATTENED document: the revisions are ordinary runs carrying strikethrough or underline character formatting, and the file contains ZERO `<w:ins>`/`<w:del>` elements. A session that greps for tracked changes on such a file finds none and concludes "seller returned it clean / accepted everything" — a false negative on the entire redline.

## Encodings reported by extract_revisions.py

It reports every encoding present:

| Encoding | What it is |
|---|---|
| `ooxml-tracked-changes` | Real `<w:ins>`/`<w:del>` — in the body, headers, footers, footnotes and endnotes; authors and dates available |
| `compare-tool-formatting` | Litera/Workshare/Word compare output; revisions are strikethrough and coloured underline |
| `comments` | Counsel comments in `word/comments.xml`. A commented draft carries no revisions at all and must never be reported as clean |
| `clean` | None of the above |

## How insertions are identified

Two notes on how insertions are identified, because the naive test is wrong: section headings and hyperlinks are also underlined and often coloured, so "underlined and coloured" alone reports a clean document as a redline. The script therefore requires a positive deletion signal — at least one strikethrough run — before reading any document in compare mode, prefers double underline where the document uses it, and ignores hyperlink-styled runs.

## Reading the compare-tool summary block

**Read the compare-tool summary block before anything else.** When present it names the BASE the counterparty compared against, and its own change tally. Two consequences:

- **The base defines what was accepted.** Every provision NOT marked is accepted *from that base* — not merely left uncommented. This is the single most valuable fact in the file and it is invisible to a tracked-change parse.
- **Confirm the base is the draft ORA actually sent.** If it names an earlier draft, the counterparty reviewed stale paper and the whole round must be re-based before analysis.
- Cite the tool's own tally externally, not the script's run counts — the two use different counting conventions (formatting runs vs. merged changes), and the tool's number is the one opposing counsel will quote.
