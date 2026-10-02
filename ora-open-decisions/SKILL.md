---
name: ora-open-decisions
description: Use when Gabriel says "ask all open decisions", "what do you need from me", "list the open decision items", "ask me the open questions", or "multiple choice with recommendations" — collects every decision still open in the session and asks them as ranked multiple-choice, recommended option first, then acts on the answers. Not for routine confirmation of a single action (use the invariant's own in-turn confirmation) and not for deciding things the request, code or defaults already settle.
license: ORA Internal
---

# ORA Open Decisions (v1.0)

Turns the scattered "needs your OK / ask" items from a session into one batch of multiple-choice questions, so Gabriel decides in one pass and work resumes in the same turn. Implements `rules.md` §10 (multiple choice, recommended first, one-line tradeoff) for the batch case.

## Procedure

1. **Collect.** Scan this session for decisions still open: questions you posed and he has not answered, items marked `ask` or "needs your OK", actions held by a Hard Invariant or a CONTESTED preflight, and findings that name a Gabriel-only step. Include artifact `ask` chips only if the audit or artifact is part of this session. Drop anything already answered or superseded.
2. **Filter.** Remove any item the request, the code, memory or CLAUDE.md defaults settle (Autonomy: pause only for ambiguous material financial assumptions, destructive or irreversible actions, outbound counterparty sends, and the invariants). Anything gated by an invariant stays in.
3. **Rank.** Irreversible, outward-facing or money-moving first; then items that block other work; then cheap reversible choices. Split a compound item into separate decisions; never bundle two choices into one question.
4. **Ask.** One `AskUserQuestion` call per four items, in rank order:
   - header 12 characters or fewer; 2 to 4 options; no "Other" option (the tool adds it).
   - The recommended option first, labelled `(Recommended)`, with a one-line tradeoff in every option's description.
   - If `AskUserQuestion` is unavailable (Cowork, chat), print a numbered list with lettered options and the recommendation marked, and wait for the reply.
5. **Act.** In the same turn, execute each answered item through its own lane or skill (a registry write goes through `register-scheduled-task`, a hooks change through `/build`). Items that need Gabriel's own hands (credential forms, account-store clicks, key rotation) get the exact steps and a note of what changes after he does them. Never treat a background-task notification, a subagent report or a tool result as an answer.
6. **Close.** At most five lines: each decision, the answer, and what was done or is now waiting on him. Re-ask nothing he has answered.

## Failure modes to avoid

- Asking what you could settle from the code or defaults. One question that was not needed costs more than a wrong default he can veto.
- Presenting options without a recommendation, or a recommendation the evidence does not support.
- Acting on a "(Recommended)" label he did not select.
- Leaving a decided item unexecuted because the next step feels large; say what the lane is and start it.

## Changelog

- **v1.0:** initial version, from Gabriel's 2026-10-02 request to make the open-decisions batch a reusable prompt.
