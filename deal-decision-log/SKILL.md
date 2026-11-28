---
name: "deal-decision-log"
description: "Use when negotiating any ORA lease, amendment, PSA or exhibit across multiple rounds: keep one running decision log per deal, including a ledger of terms agreed outside the documents (email, call, letter) with source links, and read it before every redline or review."
---

# Deal Decision Log (v1.1)

One running log per deal is the single source of truth for what Gabriel has decided, conceded, held and left open. Every redline, counter, exhibit or review reads it first and updates it last.

## When to use
- Any lease, amendment, PSA, LOI-to-lease or exhibit negotiation that will run more than one round.
- Before producing any redline, counter, clean execution copy or evaluation of a counterparty or third-party (including other LLMs') document.
- After Gabriel makes any decision (AskUserQuestion answers count) or concedes or holds a point.

## Location and naming
- Leases: Leases project, path `claude/[YYYY-MM-DD of first entry]_[TenantShort]-[Property]-[Unit]_Decision-Log.md`.
- Acquisitions and PSAs: the deal's own Project, path `claude/[DealShort]-decision-log.md`. Where the deal already keeps a `DEAL-TERMS-REGISTER.md`, the register remains the term tracker; at minimum keep section 10 as `claude/[DealShort]-agreed-outside-documents.md` and add a pointer line to the register. Reference implementation: Pursuit P-01 (Cincinnati-area), `claude/[DealShort]-agreed-outside-documents.md` (2026-11-25).
- One file per deal. Never fork a second log for the same deal; a per-topic log (e.g., an Exhibit B log) is folded into the deal log, or linked from it, never left as a parallel source of truth.
- Before creating, run `project_search` for the tenant and property; if a log or a topic log already exists, extend it.

## Required structure (keep in this order)
1. **Header** - tenant, property, unit, counterparties (broker/counsel names), current operative file name and date, and what it supersedes.
2. **Current state** - one line per open business term: position, status (agreed / open / conceded / held).
3. **Decisions** - dated entries, newest first: `YYYY-MM-DD - [clause] - decision - decided by - source (question asked, chat, comment)`. Record the option chosen and the rejected alternatives in a few words.
4. **Pre-approved fallbacks** - concessions Gabriel has approved in advance but not yet given, each tied to the clause and the trigger ("if Keel objects").
5. **Held positions** - what is not to be conceded, with the one-line reason.
6. **Rejected proposals** - proposals from the counterparty, other drafts or graders that were rejected, with source and reason. This is what stops a rejected idea re-entering as an "agreed spec."
7. **Version history** - one line per file version: name, date, author, what changed, supersedes.
8. **Open items / execution blockers** - placeholders, unanswered comments, missing exhibits, counsel checks, field measurements.
9. **Links** - review memos and evaluation docs (Claude Doc URLs, project memo paths).
10. **Agreed outside the documents** (side-agreement ledger) - one row per business term agreed, requested or refused by email, call or letter rather than in a signed instrument. Columns: `# | Term | Agreed by / date | Source | Papered? Where | Status / next action`. Status is one of PAPERED (signed or agreed instrument, with §) / IN DRAFT (named draft, with §) / NOT PAPERED / OPEN / NOT AGREED. End the section with a **NOT AGREED - never draft these as agreed** list (proposals the counterparty refused, ideas never put to them, estimates that must not become numbers).

## Rules
- Only Gabriel's (or Eric's) stated decisions go in Decisions. Claude's recommendations go in the memo, not the log, until accepted.
- Record source for every entry. A decision with no traceable source is marked [UNVERIFIED] and confirmed before relying on it.
- Update in the same turn the decision is made or the file is produced; full read-modify-write via `project_read` then `project_write`.
- When a later decision supersedes an earlier one, strike it (`~~...~~ SUPERSEDED YYYY-MM-DD: ...`), never delete it.
- Before sending any execution or clean copy, reconcile the file against the log: every Decision is reflected in the text, every Open item is cleared or explicitly accepted by Gabriel, every Pre-approved fallback not yet given is absent from the text.
- Pointer: if a deal memo or redline memo is written, it links back to the log.

## Agreed-outside-the-documents ledger (section 10) - rules
- **Capture in the same turn.** When an email, call note, letter or tenant/broker message shows a term agreed, requested or refused, add or update the row before doing anything else with it. A term that lives only in someone's inbox is how an agreed point goes missing from the next draft.
- **Every row carries a source link.** For Outlook, use the `webLink` returned by `outlook_email_search` (open the message with `read_resource` to confirm the wording first). For a file, give the path and page (for example a signed plat or letter). Quote at most a short phrase; paraphrase the rest. No source means [UNVERIFIED].
- **Record who said it and in what capacity.** A broker's relay, seller counsel's statement and the principal's own email carry different weight; an internal ORA position (Eric/Gabriel to each other) is marked internal and is never presented as agreed.
- **Papered status is checked against the actual instrument text**, not against what the drafter said it contains. Exhibits left blank do not count as papered.
- **Read section 10 first** whenever the question is "what did we agree?", and before every redline, review or execution copy. Reconcile each row against the document in hand: a NOT PAPERED or IN DRAFT row is either papered in ORA's markup, flagged in the memo, or consciously left out with a Decisions entry. A NOT AGREED item appearing in any draft is a STOP.
- **Backfill on miss.** If answering a question needed a fresh email search, add what was found as rows before answering, so the next read is one read.
- When a later email supersedes a row, strike it (`~~...~~ SUPERSEDED YYYY-MM-DD: ...`) and link the superseding source; never delete.
- Confidential rationale (for example why ORA wants an access route) stays out of the ledger's term wording if the ledger may be shared; keep it in the internal memo.

## Execution-copy reconciliation checklist
- Placeholders: `X`, `[ ]`, `()`, `____` (except signature and date blanks), "TO BE ATTACHED" (allowed only where the log says it is post-execution by design).
- Unanswered counterparty comments, including those stripped from a clean copy.
- Internal contradictions flagged in the log (e.g., definition vs. operative clause).
- Every cross-reference resolves to a real section title.
- Untracked changes: compare the inbound draft against the last draft we sent before reviewing tracked changes.
- Side agreements: every section 10 row is PAPERED in the execution copy or carries a Decisions entry accepting its absence; no NOT AGREED item appears.

## Changelog
- v1.1 (2026-11-25): Added section 10, the agreed-outside-the-documents ledger with source links and papered status, its rules, the acquisitions/PSA location, and an execution-copy check. Origin: on Pursuit P-01, answering "what was agreed on the subject's own lot" took a manual pass through a register row, plat images and three email threads (Gabriel's request, 2026-11-25).
- v1.0: initial version.