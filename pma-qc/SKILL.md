---
name: pma-qc
description: "Pre-execution and pre-renewal QC gate for PROPERTY MANAGEMENT AGREEMENTS on third-party manager paper (Kohr Royer Griffith, Colliers, Cushman, local PM firms) where Oxford Realty Advisors or an ORA entity is the Owner. Use when the user says: QC this management agreement, review the PM agreement, property management agreement, management agreement review, PM fee review, can I give leasing to another party, who controls leasing at this building, terminate the property manager, or uploads a DOCX/PDF that is a property management agreement. Run before signing, before every auto-renewal, and before engaging a third-party leasing broker at a managed property. Scans 32 defects (exclusive leasing grant with no per-property carve-out, manager authority to execute leases in Owner's name, indemnity reaching the manager's own negligence, undefined fee bases, fee stacking, retained trust-account interest, no turnover obligations) at BLOCK/HIGH/MED/LOW. Carries 18 PROPOSED positions, unratified. v1.0"
---

# Property Management Agreement QC — third-party manager paper

Pre-execution gate for property management agreements where ORA (or an ORA
property entity) is the Owner. Run **before** signature, **before** every annual
auto-renewal, and **before** engaging any third-party leasing broker at a
managed property — the third case is what usually surfaces the agreement's
exclusivity grant for the first time.

For brokerage listing agreements use `listing-agreement-qc`; for ORA's own lease
paper use `lease-form-qc`; for counterparty leases, PSAs, and loan documents use
`legal-intelligence`.

## Why this exists

`listing-agreement-qc` (v1.0, 2026-08-17) gated the *brokerage* engagement.
Nothing gated the *management* engagement — the agreement that, across roughly
27 properties, actually governs who may lease space, who signs the lease, whose
money earns the trust-account interest, and what it costs to leave.

Seed document: the **Kohr Royer Griffith, Inc. Management Agreement** executed
23 December 2020, Owner *Eric Goldberg*, covering five Columbus properties
(2012–2026 Zettler, 2800–2826 Banwick, 384–420 Morrison, 4595–4601 E. 5th Ave,
2000–2008 Zettler). Four pages. It scans **31 of 32**.

Three findings drove the design:

1. **The binding constraint is upstream of price.** The question that produced
   this skill was operational — *can leasing at one building go to another
   party* — and the answer lived in a single adverb in §1 ("appoints the Agent
   **exclusively** to rent, lease, operate and manage"). A fee-focused review
   never reaches it.
2. **A four-page agreement is not a small agreement.** Brevity here is omission:
   no governing law, no venue, no notice address (for an agreement whose only
   exit is a *written notice*), no audit right, no turnover obligation, no
   assignment restriction, no confidentiality covenant. Nine of the 32 checks
   fire on absence, not on language.
3. **Auto-renewal means no one ever re-reads it.** §1 renews annually with no
   notice requirement in either direction. The 2020 form has governed through
   six renewals unexamined; its $2,000 approval threshold and $45/hour rates are
   2020 dollars.

Scanner benchmarks (v1.0, 32 checks):

| Document | Failures | Notes |
|---|---|---|
| KRG 12.23.2020 (5 properties, executed) | **31 of 32** | 5 BLOCK · 15 HIGH · 10 MED · 1 LOW |
| A fully remediated ORA management agreement | **0 of 32** | target state · `tests/remediated_fixture.txt` |

## The eighteen standing positions — PROPOSED, NOT RATIFIED

`references/standing-positions.md` carries PM-1 … PM-18. **These are drafted
from the KRG review and have not been ratified by Gabriel.** Unlike
`listing-agreement-qc`'s SP-1 … SP-16 (ratified 2026-08-17), they are a proposed
canon: apply them as the review standard, present them as recommendations, and
do not describe any of them as settled ORA policy until ratification is recorded
here and in `event_log.md`.

The four that cost real money, in priority order when a markup must be shortened:

1. **PM-9 — The manager never executes a lease in Owner's name.** The KRG form
   grants authority to "sign, renew and/or cancel leases." This is the direct
   analog of the ratified SP-9 on brokerage paper, where ORA has already won it.
2. **PM-6 — The indemnity does not reach the manager's own negligence.** The KRG
   form has Owner save Agent harmless from *all* damage suits while exculpating
   Agent for everything short of willful misconduct or gross negligence. Owner is
   insuring the manager's ordinary negligence.
3. **PM-1 — Exclusivity is per-property and severable by service line.** Leasing,
   management, and construction supervision are separate grants; a property comes
   off Exhibit A on Owner's notice without terminating the whole agreement.
4. **PM-3 / PM-11 — Every fee base is defined and capped.** "Gross monies
   collected" and "gross lease value" are undefined in the KRG form.

## How to run

### Step 1 — Automated scan

```bash
python3 scripts/pma_qc.py <agreement.docx|pdf|txt> [more ...] [--allow-tokens] [--json]
```

Extraction, OCR fallback, and the report/CLI harness live in `ora_doc_qc.py`
(shared with `listing-agreement-qc` and `lease-form-qc` once their own
retrofits land — see that module's migration notes). A copy ships in this
skill's `scripts/` so pma-qc installs and runs standalone; once
`tools/package_skills.py`'s `SHARED_ROOT_DEPS` injects it from the repo root
the same way it already does for `target-markets.json`, the in-skill copy
should be removed. Prints one line per FAIL with severity and the standing
position it enforces. Exits non-zero on any failure or on UNREADABLE.

### Step 2 — Trust the OCR gate; never read a low word count as clean

**This is the trap this scanner exists to close, and the sibling skill has it.**
The KRG agreement is a scanned image with **no text layer** — `pdftotext`
returns zero bytes. A checker that scans an empty string finds no defects and
reports *clean*. `listing_qc.py` (`listing-agreement-qc` v1.0) has this failure
mode today and should be patched the same way.

`pma_qc.py` therefore refuses to score a document it could not read:

- Under 150 extracted words → automatic OCR fallback (`pdftoppm -r 300 -png`
  piped to `tesseract`), reported in the header as `EXTRACTION ocr`.
- OCR unavailable, or still under 150 words → **exit 2 with `UNREADABLE`**. It
  does not print a failure count. An unreadable document has no QC result.

OCR text is lossy. When the header reads `EXTRACTION ocr`, treat every *absence*
finding (P16, P19, P24, P27–P30 — checks that fire because language is missing)
as **provisional** and confirm against the page images before reporting a
missing clause to a counterparty. Presence findings are reliable; absence
findings on OCR are not.

### Step 3 — Answer the exclusivity question before anything else

Report, in this order, at the top of every review:

1. **Scope of the exclusive grant** — which service lines (lease / manage /
   operate / sell) and which properties.
2. **Severability** — can one property, or one service line, be removed without
   terminating the whole agreement.
3. **Owner carve-outs** — what Owner expressly retained. In the KRG form the
   only one is renewals ("Renewals to be handled by Owner," §2(c)(2)), and that
   single express reservation argues against implying any other.
4. **The exit** — termination mechanics, notice period, notice address, and
   whether any post-termination commission tail exists.

That block answers the operational question. Everything after it is economics.

### Step 4 — Model the fee stack

```bash
python3 scripts/fee_stack.py --collections 480000 --mgmt-pct 4 --mgmt-floor 850 \
    --lease-value 250000 --lease-pct 6 --capex 120000 --capex-pct 4 \
    --insurance-billings 300000 --insurance-pct 10
```

Prints total annual manager compensation, the effective rate against
collections, and the marginal fee on each event class. The point is the stacking:
the KRG form charges the management percentage on collections, again on capital
projects, and 10% on insurance billings — and because "gross monies collected"
is undefined, insurance proceeds landing in the operating account arguably carry
both. Quantify the overlap before negotiating the headline rate.

### Step 5 — Verify the Owner entity against county owner-of-record

The KRG agreement names **"Eric Goldberg"** individually. If title sits in
property LLCs, the named Owner is not the owner of record. Confirm per property:

```bash
curl -s -G "https://gis.franklincountyohio.gov/hosting/rest/services/ParcelFeatures/Parcel_Features/MapServer/0/query" \
  --data-urlencode "where=SITEADDRESS LIKE '%ZETTLER%'" \
  --data-urlencode "outFields=PARCELID,OWNERNME1,SITEADDRESS,BLDGAREA,CLASSDSCRP" \
  --data-urlencode "returnGeometry=false" --data-urlencode "f=json"
```

Other counties: endpoint registry in `ora-millage-lookup` and
`ora-flood-zoning-dd`. A mismatch is **not** a defense to raise casually — years
of accepted services and paid fees support ratification. Report it as a
conforming amendment to make, not as an escape hatch.

### Step 6 — Rebuild Exhibit A

An address list is not a property schedule. Per PM-17 the exhibit carries, per
property: street address range, **parcel ID(s)**, building SF, the **owning
entity** exactly as the county renders it, and the service lines engaged. Source
SF and entity from the ORA Master Workbook (SharePoint, per the Notion pointer
page), never from the agreement's own recitals.

### Step 7 — Agreement-folder close-out

Run `references/agreement-folder-checklist.md` — eleven artifacts, of which the
certificate of fidelity bond, the manager's E&O certificate, and the
countersigned copy are the ones routinely absent.

### Step 8 — Report

Order findings BLOCK → HIGH → MED → LOW, after the Step 3 exclusivity block. For
each: the defect, the failure scenario in dollars where quantifiable, and the
exact replacement language from `references/standing-positions.md`. Close with an
explicit **execute / do not execute** (new agreement) or **renew / renegotiate /
terminate** (existing agreement) recommendation. Deliver as DOCX per the ORA
Style Guide with the 16-point QC Gate applied.

## Renewal-cycle use

For an agreement already in force, the deliverable is a decision, not a markup.
Compute and state:

- **Days to the next auto-renewal**, and the last date a termination notice can
  be delivered to take effect before it.
- **Trailing 12-month fees actually paid**, from QuickBooks, against the fee
  stack model.
- **What termination costs**: any tail, any assumed vendor contracts (KRG §3(c)
  makes Owner assume every contract the Agent signed, with no schedule of what
  those are — demand the schedule before terminating, not after), and the
  transition burden the agreement fails to place on the manager.

## Scope boundaries

| Situation | Skill |
|---|---|
| Third-party property management agreement, ORA as Owner | **this skill** |
| Broker listing agreement (sale or lease), ORA as Owner | `listing-agreement-qc` |
| ORA's own lease form going to a tenant | `lease-form-qc` |
| Counterparty lease, PSA, loan doc | `legal-intelligence` |
| Amending a lease already in effect | `lease-addendum` |
| Whether to self-manage vs. third-party manage | `re-operations` / `portfolio-growth` |
| Drafting the manager engagement or termination email | `communication-intelligence` |

## Hard rules

- This skill **reviews**. It never sends. A markup or a termination notice going
  to a manager is an outbound communication to an external counterparty and
  requires Gabriel's explicit in-turn confirmation (standing invariant 1).
- **A termination notice is irreversible in practice.** Even where the agreement
  permits at-will termination, delivering notice ends a relationship that
  currently holds the tenant files, the deposits, and the vendor contracts. Model
  the transition before recommending it.
- Never state a governing fee, threshold, or termination date from memory or from
  a prior review. Re-read the executed agreement each time.
- PM-1 … PM-18 are **proposed**, not ratified. Say so in every report that cites
  them.

## Changelog

- **v1.0 (2026-08-17)** — Initial. 32 checks, 18 proposed standing positions,
  fee-stack model, agreement-folder checklist, KRG form defect register.
  Benchmarked at 31/32 (KRG 12.23.2020) and 0/32 (remediated fixture). Adds the OCR/unreadable gate that
  `listing_qc.py` lacks — a scanned PDF with no text layer must never score as
  clean.
