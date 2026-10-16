---
name: "external-review-premise-check"
description: "Use when evaluating another LLM's, broker's or reviewer's grade, critique or redline of an ORA document: verify every factual premise and claimed agreement against the deal decision log and the actual document before weighing the recommendation."
---

# External Review Premise Check

External reviews (other LLMs, graders, brokers, counterparty counsel) often rest recommendations on premises that are false: an "agreed specification" that came from a different draft, a clause the document does not contain, a missing exhibit that is attached, a defined term claimed undefined. Check the premise before judging the recommendation.

## When to use
- Gabriel pastes or uploads a grade, evaluation, critique or competing draft from another model or reviewer.
- A counterparty markup or comment asserts what was agreed ("per our discussion", "as agreed").

## Inputs to load first
1. The deal decision log (`deal-decision-log` skill; `project_search` tenant + property). If none exists, say so and treat every "agreed" claim as unverified.
2. The exact document version the reviewer graded (confirm the version; note if a later version has mooted points).
3. Any competing drafts in play (other LLM drafts are the most common source of imported premises).

## Procedure
1. **Extract claims.** List every factual premise in the review: (a) claims about what Gabriel/ORA decided or approved, (b) claims about what the document says or lacks, (c) claims about the lease body, defined terms, exhibits, cross-references, (d) legal assertions.
2. **Verify each claim** against its source of record:
   - Decisions -> the decision log (and the AskUserQuestion answers it records). Search rejected-proposal entries and competing drafts to find where an unsupported "agreed spec" came from.
   - Document content -> extract text with pandoc or python-docx and grep the exact clause; do not rely on memory.
   - Defined terms / exhibits -> search the lease body and exhibit pages (render to PDF if images are involved).
   - Legal assertions -> mark [SPECULATIVE] unless checked against a primary source; route to counsel-pass list.
3. **Classify** each claim: Verified / False premise (state the real source, e.g., "Draft A's proposal, rejected 10/6") / Misread of the document / Moot (superseded by a later version) / Unverifiable.
4. **Then weigh recommendations.** A recommendation built on a false premise is rejected on that ground first; only consider its independent merit afterward and say so separately.
5. **Watch for duplicate-and-drift fixes.** A suggested exhibit sentence that restates lease text in different words (e.g., dropping "or otherwise secured") creates a conflict; reject in favour of cross-reference.
6. **Watch for reopeners.** Recommendations that restate a clause still under negotiation (an unanswered counterparty comment) are rejected unless Gabriel chooses to reopen it.

## Output
- A premise table per reviewer: `Claim | Source checked | Status | Note`, placed before the agree/disagree table.
- In the agree/disagree table, cite the premise status in the reasoning ("Reject (false premise)").
- Record rejected proposals and their source in the decision log's Rejected Proposals section so they cannot recur as "agreed."
- Flag reviewer reliability in one line (e.g., "2 of 3 headline deductions rest on false premises").