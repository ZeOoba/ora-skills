#!/usr/bin/env python3
"""Static trust-gate checks over .github/workflows/claude-ci-fix.yml (2026-11-12).

Audit row ci-fix-coderabbit-exemption-public-injection: the repo went public on
2026-11-09. Every path that starts the token-holding agent (CLAUDE_CODE_OAUTH_TOKEN,
id-token: write, Bash(git:*)) must carry a trust gate.

Structural parse, not substring matching (a substring check let `!<gate>`, `|| true`
and a new ungated `|| (...)` clause through). The job-level `if:` is parsed as:
  * a disjunction of top-level clauses, each a parenthesised group;
  * each clause a pure `&&` conjunction of ATOMS (no nested `||`, no `!`);
  * every atom must be in the KNOWN allowlist below, byte-for-byte after whitespace
    normalisation -- `true`, a negated gate, a widened association list or any
    unrecognised expression is rejected;
  * each clause must match one recognised SHAPE: its event atom plus every gate
    that shape requires.

Whole-workflow structure (review G1/G3, 2026-11-12):
  * `on:` and `permissions:` match exact allowlists;
  * no `github_token`, `allowed_non_write_users` or tag-mode trigger inputs;
  * claude-code-action is used only by the gated claude-fix job;
  * no `${{ github.event.* }}` inside any `prompt:` or `run:` value (duplicated keys too);
  * a fork-head refusal pre-step (`gh pr view ... headRepository,headRepositoryOwner`
    vs $GITHUB_REPOSITORY, `exit 1`, no `if:`/continue-on-error) precedes every agent step;
  * every agent step has a fixed prompt and an allowlisted step `if:`;
  * no `@claude` trigger anywhere (removed 2026-11-12, Gabriel's decision).

Stdlib only -- run with `python tools/test_claude_ci_fix_workflow.py`.
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "claude-ci-fix.yml"

_TRUSTED = "contains(fromJSON('[\"OWNER\",\"MEMBER\",\"COLLABORATOR\"]'), {})"
A = {
    "ev_check_suite": "github.event_name == 'check_suite'",
    "ev_review": "github.event_name == 'pull_request_review'",
    "ev_issue_comment": "github.event_name == 'issue_comment'",
    "ev_review_comment": "github.event_name == 'pull_request_review_comment'",
    "cs_failed": "github.event.check_suite.conclusion == 'failure'",
    "cs_has_pr": "github.event.check_suite.pull_requests[0] != null",
    "cs_same_repo": ("github.event.check_suite.pull_requests[0].head.repo.id == "
                     "github.event.check_suite.pull_requests[0].base.repo.id"),
    "changes_requested": "github.event.review.state == 'changes_requested'",
    "reviewer_trusted": _TRUSTED.format("github.event.review.author_association"),
    "is_pr": "github.event.issue.pull_request != null",
    "mention": "contains(github.event.comment.body, '@claude')",
    "commenter_trusted": _TRUSTED.format("github.event.comment.author_association"),
    "coderabbit": "github.event.comment.user.login == 'coderabbit[bot]'",
    "issue_pr_author_trusted": _TRUSTED.format("github.event.issue.author_association"),
    "pr_same_repo": "github.event.pull_request.head.repo.full_name == github.repository",
    "pr_author_trusted": _TRUSTED.format("github.event.pull_request.author_association"),
}
KNOWN = {v: k for k, v in A.items()}

# Each recognised clause shape: the exact atom set a clause must have.
SHAPES = {
    "check_suite": {"ev_check_suite", "cs_failed", "cs_has_pr", "cs_same_repo"},
    "review": {"ev_review", "changes_requested", "reviewer_trusted", "pr_same_repo", "pr_author_trusted"},
    "issue_comment coderabbit": {"ev_issue_comment", "is_pr", "coderabbit", "issue_pr_author_trusted"},
    "review_comment coderabbit": {"ev_review_comment", "coderabbit", "pr_same_repo", "pr_author_trusted"},
}
# No @claude shape on purpose: the @claude trigger and the default tag-mode step were
# removed 2026-11-12 (Gabriel's decision -- tag mode builds its prompt from PR comments,
# which on a public repo any outsider can write). A clause carrying the `mention` or
# `commenter_trusted` atoms therefore matches no shape and fails, and
# structure_problems() separately rejects any `@claude` text or prompt-less agent step.


def job_if_text(text):
    """The job-level `if: |` block of claude-fix (lines before `runs-on:`), joined."""
    m = re.search(r"^  claude-fix:\n(?:.*\n)*?    if: \|\n((?:      .*\n)+?)    runs-on:", text, re.M)
    if not m:
        raise AssertionError("job-level `if: |` block of claude-fix not found")
    return " ".join(line.strip() for line in m.group(1).splitlines())


def _split_top(expr, op):
    """Split expr on `op` at parenthesis depth 0, ignoring quoted strings."""
    parts, depth, quote, start, i = [], 0, None, 0, 0
    while i < len(expr):
        ch = expr[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced parentheses")
        elif depth == 0 and expr.startswith(op, i):
            parts.append(expr[start:i])
            start = i + len(op)
            i = start
            continue
        i += 1
    if depth != 0 or quote:
        raise ValueError("unbalanced parentheses or quotes")
    parts.append(expr[start:])
    return [p.strip() for p in parts]


def _strip_outer(expr):
    """Remove ONE pair of parentheses that wraps the whole expression, else None."""
    if not (expr.startswith("(") and expr.endswith(")")):
        return None
    inner = expr[1:-1]
    try:
        _split_top(inner, "||")  # raises if the outer pair does not wrap everything
    except ValueError:
        return None
    return inner.strip()


def _norm(s):
    return re.sub(r"\s+", " ", s).strip()


def if_problems(text):
    """Problems in the job-level `if:` of claude-fix (structural clause/atom parse)."""
    try:
        expr = job_if_text(text)
        clauses = _split_top(expr, "||")
    except (AssertionError, ValueError) as e:
        return [f"unparseable job-level if: {e}"]
    found = []
    for n, clause in enumerate(clauses, 1):
        inner = _strip_outer(clause)
        if inner is None:
            found.append(f"clause {n}: not a single parenthesised group")
            continue
        if "||" in _norm(inner).replace("'||'", ""):
            found.append(f"clause {n}: nested `||` (each clause must be a pure && conjunction)")
            continue
        atoms = set()
        for atom in _split_top(inner, "&&"):
            a = _norm(atom)
            if a.startswith("!"):
                found.append(f"clause {n}: negated atom")
            elif a not in KNOWN:
                found.append(f"clause {n}: unrecognised atom (only allowlisted gates/predicates may appear)")
            else:
                atoms.add(KNOWN[a])
        if not any(atoms == shape for shape in SHAPES.values()):
            found.append(f"clause {n}: does not match any fully-gated trigger shape")
    return found


# --- Whole-workflow structure (2026-11-12, review G1/G3) ------------------------------
ACTION = "anthropics/claude-code-action"
ALLOWED_ON = {
    "check_suite": ["completed"],
    "pull_request_review": ["submitted"],
    "issue_comment": ["created"],
    "pull_request_review_comment": ["created"],
}
ALLOWED_PERMISSIONS = {
    "contents": "read", "pull-requests": "write", "issues": "write",
    "checks": "read", "id-token": "write",
}
# Exact step-level `if:` texts allowed on agent steps (whitespace-normalised). Anything
# else -- `true`, `always()`, a dropped CodeRabbit exclusion -- is rejected.
ALLOWED_AGENT_STEP_IFS = {
    "github.event_name == 'check_suite' || (github.event_name == 'pull_request_review' && "
    "github.event.review.state == 'changes_requested') || ((github.event_name == 'issue_comment' || "
    "github.event_name == 'pull_request_review_comment') && github.event.comment.user.login == 'coderabbit[bot]')",
}
PRE_STEP_NAME = "Refuse fork-head PRs (PR head must live in this repo)"
_INTERP_EVENT = re.compile(r"\$\{\{[^}]*\bgithub\.event\.")
_FORBIDDEN_INPUT = re.compile(r"^\s*(github_token|allowed_non_write_users)\s*:", re.M)


def _top_block(text, key):
    """Lines of a top-level `key:` block (until the next column-0 key)."""
    m = re.search(rf"^{re.escape(key)}:[ \t]*\n((?:(?:[ \t].*|)\n)*)", text, re.M)
    return m.group(1).splitlines() if m else None


def _jobs(text):
    """{job_name: block_text} for every job under `jobs:`."""
    lines = _top_block(text, "jobs") or []
    jobs, name = {}, None
    for line in lines:
        m = re.match(r"^  ([\w-]+):\s*$", line)
        if m:
            name = m.group(1)
            jobs[name] = []
        elif name:
            jobs[name].append(line)
    return {k: "\n".join(v) + "\n" for k, v in jobs.items()}


def _steps(job_block):
    """List of step texts (each starting at its `      - ` line)."""
    m = re.search(r"^    steps:\s*\n", job_block, re.M)
    if not m:
        return []
    steps, cur = [], None
    for line in job_block[m.end():].splitlines():
        if re.match(r"^      - ", line):
            cur = [line]
            steps.append(cur)
        elif line.startswith("        ") or not line.strip():
            if cur is not None:
                cur.append(line)
        elif re.match(r"^      #", line):
            continue  # step-level comment between steps
        else:
            break  # dedent past the step list
    return ["\n".join(s) for s in steps]


def _key_values(step, key):
    """Every value of `key:` in a step -- a duplicated key (YAML keeps the LAST one)
    must not hide behind a clean first occurrence."""
    lines = step.splitlines()
    vals = []
    for i, line in enumerate(lines):
        m = re.match(rf"^(\s*)(?:- )?{re.escape(key)}:(.*)$", line)
        if m:
            vals.append(_key_value("\n".join(lines[i:]), key))
    return vals


def _key_value(step, key):
    """Value text of the first `key:` in a step (inline remainder plus deeper-indented lines)."""
    lines = step.splitlines()
    for i, line in enumerate(lines):
        m = re.match(rf"^(\s*)(?:- )?{re.escape(key)}:(.*)$", line)
        if m:
            indent = len(m.group(1)) + (2 if line.lstrip().startswith("- ") else 0)
            out = [m.group(2)]
            for nxt in lines[i + 1:]:
                if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                    break
                out.append(nxt)
            return "\n".join(out)
    return None


def _is_valid_pre_step(step):
    if f"name: {PRE_STEP_NAME}" not in step:
        return False
    if _key_value(step, "if") is not None or "continue-on-error" in step:
        return False  # must always run and must fail the job
    run = _key_value(step, "run") or ""
    return all(s in run for s in (
        "gh pr view", "--json headRepository,headRepositoryOwner", "$GITHUB_REPOSITORY", "exit 1"))


def structure_problems(text):
    found = []
    # on: exact allowlist
    on = _top_block(text, "on")
    parsed, ev = {}, None
    for line in on or []:
        m = re.match(r"^  ([\w-]+):\s*$", line)
        t = re.match(r"^    types:\s*\[([^\]]*)\]\s*$", line)
        if m:
            ev = m.group(1)
            parsed[ev] = None
        elif t and ev:
            parsed[ev] = [x.strip() for x in t.group(1).split(",") if x.strip()]
        elif line.strip() and not line.strip().startswith("#"):
            parsed.setdefault("<unparsed>", []).append(line.strip())
    if parsed != ALLOWED_ON:
        found.append("on: is not exactly the allowlisted events/types")
    # permissions: exact allowlist
    perms = {}
    for line in _top_block(text, "permissions") or []:
        m = re.match(r"^  ([\w-]+):\s*(\S+)\s*$", line)
        if m:
            perms[m.group(1)] = m.group(2)
    if perms != ALLOWED_PERMISSIONS:
        found.append("permissions: is not exactly the allowlisted set")
    # forbidden action inputs anywhere
    for m in _FORBIDDEN_INPUT.finditer(text):
        found.append(f"forbidden input `{m.group(1)}`")
    # @claude / tag mode must not come back (2026-11-12 removal). Comments are ignored
    # so the explanatory notes in the workflow do not trip this.
    code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    if "@claude" in code:
        found.append("@claude trigger text present (the @claude path was removed on purpose)")
    if re.search(r"^\s*(trigger_phrase|assignee_trigger|label_trigger)\s*:", code, re.M):
        found.append("tag-mode trigger input present (trigger_phrase/assignee_trigger/label_trigger)")
    jobs = _jobs(text)
    agent_jobs = [j for j, b in jobs.items() if ACTION in b]
    if agent_jobs != ["claude-fix"]:
        found.append("claude-code-action must be used only by the gated claude-fix job")
    for jname, block in jobs.items():
        steps = _steps(block)
        for i, step in enumerate(steps):
            for key in ("prompt", "run"):
                vals = _key_values(step, key)
                if any(v and _INTERP_EVENT.search(v) for v in vals):
                    found.append(f"job {jname} step {i + 1}: ${{{{ github.event.* }}}} interpolated into {key}:")
                if len(vals) > 1:
                    found.append(f"job {jname} step {i + 1}: duplicated `{key}:` key")
        if jname != "claude-fix":
            continue
        pre_seen = False
        for i, step in enumerate(steps):
            if _is_valid_pre_step(step):
                pre_seen = True
            if ACTION in step:
                if not (_key_value(step, "prompt") or "").strip():
                    found.append(f"claude-fix step {i + 1}: agent step has no fixed prompt (tag mode)")
                if not pre_seen:
                    found.append(f"claude-fix step {i + 1}: agent step not preceded by the fork-head pre-step")
                cond = _key_value(step, "if")
                if cond is None or _norm(re.sub(r"^\s*\|", "", cond)) not in ALLOWED_AGENT_STEP_IFS:
                    found.append(f"claude-fix step {i + 1}: agent step `if:` is not an allowlisted condition")
    return found


def gate_problems(text):
    return if_problems(text) + structure_problems(text)


class TestClaudeCiFixTrustGates(unittest.TestCase):
    def test_every_agent_feeding_path_is_gated(self):
        self.assertEqual(gate_problems(WORKFLOW.read_text(encoding="utf-8")), [])

    def test_threat_model_comment_no_longer_assumes_a_private_repo(self):
        self.assertNotIn("this repo is private", WORKFLOW.read_text(encoding="utf-8"))


def _clause(*keys):
    return "(" + " && ".join(A[k] for k in keys) + ")"


class TestCheckerCatchesUngatedClauses(unittest.TestCase):
    GATED = (
        "jobs:\n  claude-fix:\n    if: |\n"
        + " ||\n".join("      " + _clause(*sorted(s, key=lambda k: not k.startswith("ev_")))
                       for s in SHAPES.values())
        + "\n    runs-on: ubuntu-latest\n"
    )

    def test_gated_fixture_passes(self):
        self.assertEqual(if_problems(self.GATED), [])

    def test_mutations_are_flagged(self):
        t = self.GATED
        muts = {
            "negated PR-author gate": t.replace(A["issue_pr_author_trusted"], "!" + A["issue_pr_author_trusted"], 1),
            "append || true": t.replace("\n    runs-on:", " ||\n      true\n    runs-on:"),
            "new ungated clause": t.replace("\n    runs-on:", " ||\n      (github.event_name == 'issue_comment')\n    runs-on:"),
            "widened association list": t.replace('"COLLABORATOR"]', '"COLLABORATOR","NONE"]', 1),
            "dropped same-repo gate": t.replace(" && " + A["pr_same_repo"], "", 1),
            "dropped PR-author gate on coderabbit issue_comment": t.replace(
                _clause(*sorted(SHAPES["issue_comment coderabbit"], key=lambda k: not k.startswith("ev_"))),
                _clause(*sorted(SHAPES["issue_comment coderabbit"] - {"issue_pr_author_trusted"},
                                key=lambda k: not k.startswith("ev_")))),
            "nested || inside a clause": t.replace(
                A["coderabbit"], "(" + A["coderabbit"] + " || " + A["mention"] + ")", 1),
            "fully gated @claude clause reintroduced": t.replace(
                "\n    runs-on:",
                " ||\n      " + _clause("ev_review_comment", "mention", "commenter_trusted",
                                        "pr_same_repo", "pr_author_trusted") + "\n    runs-on:"),
            "|| true inside a conjunct": t.replace(A["cs_same_repo"], "(" + A["cs_same_repo"] + " || true)", 1),
            "unparenthesised clause": t.replace("(" + A["ev_check_suite"], A["ev_check_suite"], 1),
        }
        for name, mutated in muts.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(mutated, t, "mutation did not apply")
                self.assertTrue(if_problems(mutated), f"{name} was not flagged")


class TestStructureMutationsOnRealWorkflow(unittest.TestCase):
    """Mutate the real workflow file; each mutation must be flagged (review G1/G3)."""

    def setUp(self):
        self.src = WORKFLOW.read_text(encoding="utf-8")

    def _mutants(self):
        s = self.src
        step_if_first = "          github.event_name == 'check_suite' ||\n"
        pre_name = f"name: {PRE_STEP_NAME}"
        tag_step = (f"\n      - uses: {ACTION}@58985842b834ed26087302ba27d07bc24ca8697a\n"
                    "        if: |\n"
                    "          (github.event_name == 'issue_comment' || github.event_name == 'pull_request_review_comment') &&\n"
                    "          github.event.comment.user.login != 'coderabbit[bot]'\n"
                    "        with:\n          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}\n")
        second_job = ("\n  claude-fix-2:\n    runs-on: ubuntu-latest\n    steps:\n"
                      f"      - uses: {ACTION}@58985842b834ed26087302ba27d07bc24ca8697a\n"
                      "        with:\n          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}\n")
        return {
            "on: issue_comment edited": s.replace("issue_comment:\n    types: [created]",
                                                  "issue_comment:\n    types: [created, edited]", 1),
            "on: + pull_request_target": s.replace("on:\n", "on:\n  pull_request_target:\n", 1),
            "on: + workflow_dispatch": s.replace("on:\n", "on:\n  workflow_dispatch:\n", 1),
            "permissions contents: write": s.replace("  contents: read", "  contents: write", 1),
            "github_token input": s.replace("          claude_args: |",
                                            "          github_token: ${{ secrets.GITHUB_TOKEN }}\n          claude_args: |", 1),
            "allowed_non_write_users input": s.replace("          claude_args: |",
                                                       "          allowed_non_write_users: '*'\n          claude_args: |", 1),
            "event text interpolated into prompt": s.replace(
                "CodeRabbit posted automated review feedback on this PR.",
                "CodeRabbit said ${{ github.event.comment.body }}.", 1),
            "event-text prompt line appended": s.rstrip("\n") + "\n          prompt: ${{ github.event.issue.body }}\n",
            "tag-mode step reintroduced (no prompt)": s.rstrip("\n") + "\n" + tag_step,
            "@claude in a job-level clause": s.replace(
                "github.event.comment.user.login == 'coderabbit[bot]' && contains(fromJSON",
                "contains(github.event.comment.body, '@claude') && contains(fromJSON", 1),
            "trigger_phrase input": s.replace("          claude_args: |",
                                              "          trigger_phrase: '/fix'\n          claude_args: |", 1),
            "event text interpolated into run": s.replace(
                'printf \'%s\\n\' "$REVIEW_OR_COMMENT_BODY"', "printf '%s\\n' \"${{ github.event.comment.body }}\"", 1),
            "second ungated agent job": s.rstrip("\n") + "\n" + second_job,
            "agent step if: widened with true": s.replace(step_if_first, "          true ||\n", 1),
            "pre-step removed (renamed)": s.replace(pre_name, "name: something else", 1),
            "pre-step made conditional": s.replace(pre_name, pre_name + "\n        if: github.event_name == 'check_suite'", 1),
            "pre-step continue-on-error": s.replace(pre_name, pre_name + "\n        continue-on-error: true", 1),
            "pre-step exit 1 removed": s.replace("exit 1", "exit 0"),
        }

    def test_real_workflow_mutations_are_flagged(self):
        for name, mutated in self._mutants().items():
            with self.subTest(mutation=name):
                self.assertNotEqual(mutated, self.src, "mutation did not apply")
                self.assertTrue(structure_problems(mutated), f"{name} was not flagged")

    def test_benign_clause_reorder_is_not_flagged(self):
        lines = self.src.split("\n")
        ifl = [l for l in lines if l.startswith("      (github.event_name")]
        swapped = self.src.replace(ifl[1], "@@1").replace(ifl[2], ifl[1]).replace("@@1", ifl[2])
        self.assertNotEqual(swapped, self.src)
        self.assertEqual(gate_problems(swapped), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
