"""Reviewer model tier at the dispatch sites (audit R34-6, 2026-11-23).

The adversarial-reviewer agent carries no `model:` line by design: its floor (reviewer >=
implementer; never below Opus 5.5 for financial, governor, confidential or security-gate
content) is set where it is dispatched. Two below-floor runs in the R34 window were Opus 5.5
sessions that pinned `sonnet` while following isolated-commit step 4 and merge-ready. Those
steps said "pin the reviewer model" without naming a tier, so the sessions applied the
read-only cost downshift meant for search and lookup.

This suite holds the fix in place:
  1. every skill that dispatches a review pass names the `opus` pin and the Opus 5.5 floor;
  2. no live skill text tells a review/REFUTE dispatch to use sonnet or haiku.
"""
import hashlib
import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Skills whose procedure dispatches a reviewer subagent.
REVIEW_DISPATCH_SKILLS = (
    "isolated-commit/SKILL.md",
    "merge-ready/SKILL.md",
    "adversarial-merge-gate/SKILL.md",
)

PIN = re.compile(r'(?:`opus`|model:\s*"opus")')
FLOOR = re.compile(r"never\s+below\s+Opus\s+5\.5", re.I)
NO_DOWNSHIFT = re.compile(r"never\s+`?sonnet`?\s*/\s*`?haiku`?|downshift[^.]*\bnever\b|downshift[^.]*\bnot\b", re.I)

REVIEW_WORD = re.compile(
    r"\b(review\w*|refut\w*|mandates?|adversarial|critic(?!al\b)\w*|critiqu\w*|second[- ]opinion|"
    r"verif\w*|audit\w*|gates?|QA|checks?|spot[- ]check\w*|pressure[- ]test\w*|"
    r"red[- ]team\w*|validat\w*|scrutini[sz]\w*|independent\s+pass|regressions?|"
    r"findings?|correctness|judge\w*|bugs?|defects?|problems|flaws?|break\w*|wrong|"
    r"fail\w*|holes|safe\s+to\s+merge|signs?\s+off)\b", re.I)
DOWN_MODEL = re.compile(r"\b(?:claude-)?(sonnet|haiku)\b", re.I)
# A prohibition removes only the model(s) it names ("never `sonnet`/`haiku`").
MODEL_PROHIBITION = re.compile(r"never\s+`?(?:sonnet|haiku)`?(?:\s*/\s*`?(?:sonnet|haiku)`?)?", re.I)
# A sentence that says the model is not for review is exempt as a whole.
SENTENCE_EXEMPT = re.compile(
    r"(?:never|not)\s+for\s+(?:a\s+|any\s+)?(?:review|refute)", re.I)
SENTENCE_SPLIT = re.compile(r"(?<=[.;!?])\s+")
# Dated version-history bullets ("- v1.2 (2026-10-30): ...") quote the past.
VERSION_BULLET = re.compile(r"^\s*[-*]\s*\**v\d+(?:\.\d+)+\s*\(\d{4}-\d{2}-\d{2}")
LOOKBACK = 3  # non-blank lines
HISTORY = re.compile(r"(^|/)(versions|_archive|_staging)/|CHANGELOG", re.I)


# Reviewed lines the detector flags that are NOT dispatch instructions: records of past runs,
# descriptions of model tags, results tables. Key: (path, line_key). A changed or vanished line
# fails the suite, so an entry can never silently cover new text.
ALLOWED = {
    # Eval-run record: a past Sonnet substitute run, reported as a limitation.
    ("acquisition-underwriting-eval-harness/references/findings-and-limitations.md",
     "2fe5b929491b1d94"),
    # Describes an observed `[MODEL: claude-sonnet-5 | checked ...]` tag on a scheduled task.
    ("automation-health-monitor/SKILL.md", "920dc55b3e317bab"),
    # Plan results table: Sonnet routers in a routing baseline, not a review dispatch.
    ("docs/plans/2026-11-05_skill-improvement-plan.md", "57fc50c47a6c488b"),
}


def line_key(line):
    return hashlib.sha256(line.strip().encode("utf-8")).hexdigest()[:16]


def live_markdown():
    out = subprocess.run(["git", "ls-files", "*.md"], cwd=REPO, capture_output=True,
                         text=True, check=True).stdout.split()
    return [p for p in out if not HISTORY.search(p) and not p.startswith(".claude/")]


def downshift_findings(text):
    """Sentences naming sonnet/haiku where a review word sits in the sentence, in an earlier
    sentence on the same line, or in the LOOKBACK non-blank lines before it. No sentence is
    spared for naming a non-review job: every such spare let real review dispatches slip.
    It over-flags by design; reviewed non-dispatch lines go in ALLOWED.
    Pattern check: it catches common phrasings, not all of them."""
    hits = []
    lines = text.splitlines()
    for n, line in enumerate(lines, 1):
        if VERSION_BULLET.match(line):
            continue
        prior = [l for l in lines[:n - 1] if l.strip()][-LOOKBACK:]
        context = "\n".join(prior)
        for sentence in SENTENCE_SPLIT.split(line):
            earlier = context
            context = context + "\n" + sentence
            if SENTENCE_EXEMPT.search(sentence):
                continue
            if not DOWN_MODEL.search(MODEL_PROHIBITION.sub("", sentence)):
                continue
            if REVIEW_WORD.search(sentence) or REVIEW_WORD.search(earlier):
                hits.append((n, line.strip()[:160]))
                break
    return hits


class ReviewDispatchTier(unittest.TestCase):
    def test_each_dispatch_site_names_the_opus_pin_and_floor(self):
        for rel in REVIEW_DISPATCH_SKILLS:
            text = (REPO / rel).read_text(encoding="utf-8")
            with self.subTest(skill=rel):
                self.assertTrue(PIN.search(text), f"{rel}: no `opus` reviewer pin")
                self.assertTrue(FLOOR.search(text), f"{rel}: Opus 5.5 floor not stated")
                self.assertTrue(NO_DOWNSHIFT.search(text),
                                f"{rel}: does not exclude review from the sonnet/haiku downshift")

    def test_no_live_skill_text_downshifts_a_review_dispatch(self):
        bad, used = [], set()
        for rel in live_markdown():
            path = REPO / rel
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            lines = text.splitlines()
            for n, line in downshift_findings(text):
                key = (rel, line_key(lines[n - 1]))
                if key in ALLOWED:
                    used.add(key)
                    continue
                bad.append(f"{rel}:{n}: {line}")
        self.assertEqual(bad, [], "review dispatch pinned below Opus:\n" + "\n".join(bad))
        stale = sorted(set(ALLOWED) - used)
        self.assertEqual(stale, [], "ALLOWED entries whose line changed or vanished: re-review "
                                    "the line, then update or drop the entry")

    def test_detector_flags_a_sonnet_review_pin_and_spares_prohibitions(self):
        # Phrasings from the PR's own adversarial review (8 slipped the first detector).
        caught = [
            'Dispatch the reviewer with model: "sonnet".',
            "REFUTE pass, `model: haiku` is fine",
            "Dispatch the reviewer on sonnet.",
            "Spawn the adversarial-reviewer agent with `sonnet`.",
            "Review pass: use Sonnet 4.6 to save cost.",
            "Pin the reviewer model to haiku.",
            "Pin the reviewer model at `sonnet`; no need for Opus.",
            "reviewer:\n  model: sonnet",
            "For the review, a sonnet model is fine.",
            "Reviewer model: claude-sonnet-4-6",
            # Second-round review probes.
            "Reviewer: sonnet (never `haiku`).",
            "Not for a review: Explore uses haiku. Reviewer uses sonnet.",
            "- v9.9 (now): dispatch the reviewer on sonnet going forward.",
            "Spawn the reviewing agent on sonnet.",
            'Agent(subagent_type="adversarial-reviewer",\n      prompt=p,\n      model="sonnet")',
            "Second-opinion check: dispatch on sonnet.",
            "Critic subagent: model sonnet.",
            # Follow-up review of #287 (audit session).
            "Dispatch the adversarial-reviewer agent. Use the cheaper model (Sonnet) for it.",
            "Spawn a refutation agent; model sonnet.",
            "Review is never skipped; run it on sonnet.",
            "Run the gate check with Sonnet 4.6.",
            "QA pass on haiku is acceptable.",
            "Verify agent: haiku",
            "Reviewer\n\n\n\n\nmodel: sonnet",
            "Audit the diff on haiku.",
            # Review of the first follow-up draft: the non-review spare hid these.
            "Review the diff on sonnet, searching for callers of each touched function.",
            "QA: use Explore (haiku) to check every reader and confirm the fix.",
            "Review pass: dispatch a sonnet agent to search the diff for regressions and format findings.",
            "Audit the formatting and logic of the change on haiku.",
            "Second-pass review uses haiku to look up readers and judge correctness.",
            "For the code-review step, use sonnet.",
            "Spot-check the PR with haiku.",
            "Critique the change on sonnet.",
            "Pressure-test the fix with haiku.",
            "Independent pass: model haiku.",
            "Red-team the guard on sonnet.",
            "Validate the claims with sonnet.",
            "Scrutinize the diff using haiku.",
            # Round-2 review of the follow-up: caught at c689272, missed at e037350.
            "Code review: dispatch a sonnet agent to search the diff and report problems.",
            "Reviewer lane: Explore (haiku) searches the diff for bugs and reports them back.",
            "Step 4 (review), use Explore on haiku to search for bugs in the change.",
            "Code review lane: use Explore (haiku) to list callers, then flag any bug it sees.",
            "## Adversarial review\n\nDispatch a sonnet agent to search the diff for bugs.",
            "### REFUTE pass\nUse haiku to search every reader of the touched data.",
            # Round-3 review: base caught these, the any-lead-in spare missed them.
            "Adversarial review: run it on sonnet, searching each touched file for what breaks.",
            "REFUTE pass: a sonnet agent searches the diff and reports what breaks.",
            "Code review: sonnet searches the change and lists anything wrong.",
            "For the review, dispatch sonnet to search the diff and say what fails.",
            "Reviewer: haiku, searching the diff.",
            "Adversarial review, sonnet agent: search the diff.",
            # Round-3 review: missed by base and head alike (known limits, now caught).
            "Have sonnet try to break the change.",
            "Have haiku poke holes in the plan.",
            "Ask a sonnet agent whether the diff is safe to merge.",
            "Gate step: Explore on haiku looks up readers and signs off.",
            # Round-4 review: slipped through the "lane:" / "After review," spares (now removed).
            "Review lane: dispatch a sonnet agent to search the diff.",
            "REFUTE lane: Explore (haiku) searches each reader.",
            "Adversarial lane: haiku searches the change and lists issues.",
            "After review, sonnet searches the diff a second time.",
            "After the review, Explore (haiku) re-searches the diff for anything missed.",
            "After review, use Explore on sonnet to look up each flagged caller.",
            # Round-5 review: `critics?` dropped these; only the bare word "critical" is excluded.
            "Criticize the diff on sonnet.",
            "Criticise the change with haiku.",
            "Criticism pass: model sonnet.",
            "Critically examine the PR on haiku.",
            "criticizes via haiku",
        ]
        for text in caught:
            with self.subTest(text=text):
                self.assertEqual(len(downshift_findings(text)), 1)
        spared = [
            "Never `sonnet`/`haiku` for a review pass.",
            "The cost downshift to `sonnet`/`haiku` is for search, never for a review or REFUTE pass.",
            'Explore search uses model: "sonnet".',
            "- v1.2.2 (2026-10-30): reviewer runs on sonnet were moved to opus.",
            "Critical: Explore agents run on haiku.",
        ]
        for text in spared:
            with self.subTest(text=text):
                self.assertEqual(downshift_findings(text), [])

    def test_known_false_positives_stay_flagged(self):
        # Deliberate over-flagging. Four review rounds (2026-11-23) showed that every way of
        # sparing these let a real review dispatch slip that the c689272 detector caught:
        # "Review lane: sonnet searches the diff", "After review, haiku searches every file
        # again". With no spare, this detector flags everything c689272 flags (its vocabulary
        # and context window are supersets). A real line like these goes in ALLOWED after review.
        for text in (
            "Code review lane: use Explore (haiku) to list callers first.",
            "After review, dispatch a sonnet agent to format the changelog.",
        ):
            with self.subTest(text=text):
                self.assertEqual(len(downshift_findings(text)), 1)

if __name__ == "__main__":
    unittest.main()
