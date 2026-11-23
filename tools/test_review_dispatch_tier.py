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
    r"\b(review\w*|refut\w*|mandates?|adversarial|critics?|second[- ]opinion|verif\w*|"
    r"audit\w*|gates?|QA|checks?)\b", re.I)
# Tokens that name a review dispatch outright. A sentence holding one is never spared as
# a non-review task.
STRONG_REVIEW = re.compile(r"\b(reviewer\w*|refut\w*|adversarial|mandates?|verifier)\b", re.I)
# A sentence that names a clearly non-review job ("Code review lane: use Explore (haiku) to
# list callers first", "After review, dispatch a sonnet agent to format the changelog").
NON_REVIEW_TASK = re.compile(
    r"\b(Explore|search\w*|lookup|look\s+up|format\w*|changelog|list\s+(?:callers|files|paths))\b",
    re.I)
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
    sentence on the same line, or in the LOOKBACK non-blank lines before it. A sentence that
    names a non-review job (Explore, search, formatting) and no reviewer is spared.
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
            if NON_REVIEW_TASK.search(sentence) and not STRONG_REVIEW.search(sentence):
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
            "Code review lane: use Explore (haiku) to list callers first.",
            "After review, dispatch a sonnet agent to format the changelog.",
        ]
        for text in spared:
            with self.subTest(text=text):
                self.assertEqual(downshift_findings(text), [])

if __name__ == "__main__":
    unittest.main()
