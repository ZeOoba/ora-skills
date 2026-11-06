# deal-execution — scripts

Moved out of `SKILL.md` on 2026-09-22 (body split). Both scripts are stdlib-only (`zipfile` + `ElementTree`); no python-docx, no lxml. Run from the skill directory.

## audit_completeness.py — what each check catches

1. **Exhibit population** — an exhibit can be present, correctly titled, referenced throughout, and completely EMPTY. An exhibit whose only content is an empty table grid (zero rows, every cell blank, or struck-only cells) is EMPTY and blocks (Gabriel's in-turn ruling, 2026-11-06): a table counts toward population only through its visible text or images. Trace what depends on each empty exhibit before dismissing it; definitions, representation carve-outs, and delivery obligations routinely hang off exhibits and fail silently when blank. A `THIN` exhibit (a bare image, a parcel number, or a table with a header row and no data rows, such as a skeleton rent roll) is not automatically a defect, but ask whether a third party could draft from it — a recordable instrument cannot be prepared from an aerial markup, and a deed cannot be prepared from a parcel number.
2. **Cross-references** — exhibits cited but absent, exhibits present but never cited, and section references that do not resolve.
3. **Unfilled blanks** — placeholder runs and open definitions. Body blanks are defects; signature-block blanks are expected but must be completed consistently at execution. Inside an exhibit that follows IN WITNESS WHEREOF, every blank is a body blank and blocks (Gabriel's in-turn ruling, 2026-11-06) unless its paragraph (a table is checked cell paragraph by cell paragraph) is a genuine signature or notary line: `SIGNATURE_LINE_RE` matches a line-start `By:`/`Name:`/`Title:`/`Its:`/`Date:`/`Dated:`/`Signature:`/`Printed Name:`/`Witness:`, a bare signature rule (`_____` alone), or notary-acknowledgement wording (`acknowledged before me`, `Notary Public`, `My commission expires`, `STATE OF`/`COUNTY OF` at line start). A line carrying `$` is never exempt, and `Closing Date: ____` is not a signature line. Blanks on the signature page itself (before the first exhibit) stay signature blanks. Pay particular attention to an unfilled **knowledge-party definition**: it silently voids or unbounds every knowledge-qualified representation in the document.

## Script table

Both are stdlib-only (`zipfile` + `ElementTree`); no python-docx, no lxml. Run from the skill directory.

| Script | Purpose | Used by |
|---|---|---|
| `scripts/extract_revisions.py` | Detects revision encoding (OOXML tracked changes / compare-tool formatting / clean) and extracts revisions from all three. Parses the compare-tool summary block for the BASE document and the tool's own change tally. Exit 2 = ambiguous, hard stop. | Workflow 2 Step 0; legal-intelligence Module 6 |
| `scripts/audit_completeness.py` | Exhibit population, exhibit/section cross-reference resolution, unfilled-blank detection (body vs. signature block). Exit 1 = blocking defect. | Workflow 2A Step 5; Workflow 2B Check D; 46-Point Gate |
