---
name: "deal-decision-log"
description: "Use when negotiating any ORA lease, amendment, PSA or exhibit across multiple rounds: create and maintain one running decision log per deal in the Leases project, and read it before every redline or review."
---

# Deal Decision Log

One running log per deal is the single source of truth for what Gabriel has decided, conceded, held and left open. Every redline, counter, exhibit or review reads it first and updates it last.

## When to use
- Any lease, amendment, PSA, LOI-to-lease or exhibit negotiation that will run more than one round.
- Before producing any redline, counter, clean execution copy or evaluation of a counterparty or third-party (including other LLMs') document.
- After Gabriel makes any decision (AskUserQuestion answers count) or concedes or holds a point.

## Location and naming
- Leases project, path `claude/[YYYY-MM-DD of first entry]_[TenantShort]-[Property]-[Unit]_Decision-Log.md`.
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

## Rules
- Only Gabriel's (or Eric's) stated decisions go in Decisions. Claude's recommendations go in the memo, not the log, until accepted.
- Record source for every entry. A decision with no traceable source is marked [UNVERIFIED] and confirmed before relying on it.
- Update in the same turn the decision is made or the file is produced; full read-modify-write via `project_read` then `project_write`.
- When a later decision supersedes an earlier one, strike it (`~~...~~ SUPERSEDED YYYY-MM-DD: ...`), never delete it.
- Before sending any execution or clean copy, reconcile the file against the log: every Decision is reflected in the text, every Open item is cleared or explicitly accepted by Gabriel, every Pre-approved fallback not yet given is absent from the text.
- Pointer: if a deal memo or redline memo is written, it links back to the log.

## Execution-copy reconciliation checklist
- Placeholders: `X`, `[ ]`, `()`, `____` (except signature and date blanks), "TO BE ATTACHED" (allowed only where the log says it is post-execution by design).
- Unanswered counterparty comments, including those stripped from a clean copy.
- Internal contradictions flagged in the log (e.g., definition vs. operative clause).
- Every cross-reference resolves to a real section title.
- Untracked changes: compare the inbound draft against the last draft we sent before reviewing tracked changes.