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
    r"\b(review\w*|refut\w*|mandates?|adversarial|critic\w*|second[- ]opinion|verifier)\b", re.I)
DOWN_MODEL = re.compile(r"\b(?:claude-)?(sonnet|haiku)\b", re.I)
# A prohibition removes only the model(s) it names ("never `sonnet`/`haiku`").
MODEL_PROHIBITION = re.compile(r"never\s+`?(?:sonnet|haiku)`?(?:\s*/\s*`?(?:sonnet|haiku)`?)?", re.I)
# A sentence that says the model is not for review is exempt as a whole.
SENTENCE_EXEMPT = re.compile(
    r"(?:never|not)\s+for\s+(?:a\s+|any\s+)?(?:review|refute)", re.I)
SENTENCE_SPLIT = re.compile(r"(?<=[.;!?])\s+")
# Dated version-history bullets ("- v1.2 (2026-10-30): ...") quote the past.
VERSION_BULLET = re.compile(r"^\s*[-*]\s*\**v\d+(?:\.\d+)+\s*\(\d{4}-\d{2}-\d{2}")
LOOKBACK = 3
HISTORY = re.compile(r"(^|/)(versions|_archive|_staging)/|CHANGELOG", re.I)


def live_markdown():
    out = subprocess.run(["git", "ls-files", "*.md"], cwd=REPO, capture_output=True,
                         text=True, check=True).stdout.split()
    return [p for p in out if not HISTORY.search(p) and not p.startswith(".claude/")]


def downshift_findings(text):
    """Sentences naming sonnet/haiku where a review word sits in the sentence or in the
    LOOKBACK lines before it. Pattern check: it catches common phrasings, not all of them."""
    hits = []
    lines = text.splitlines()
    for n, line in enumerate(lines, 1):
        if VERSION_BULLET.match(line):
            continue
        context = "\n".join(lines[max(0, n - 1 - LOOKBACK):n - 1])
        for sentence in SENTENCE_SPLIT.split(line):
            if SENTENCE_EXEMPT.search(sentence):
                continue
            if not DOWN_MODEL.search(MODEL_PROHIBITION.sub("", sentence)):
                continue
            if REVIEW_WORD.search(sentence) or REVIEW_WORD.search(context):
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
        bad = []
        for rel in live_markdown():
            path = REPO / rel
            if not path.is_file():
                continue
            for n, line in downshift_findings(path.read_text(encoding="utf-8", errors="ignore")):
                bad.append(f"{rel}:{n}: {line}")
        self.assertEqual(bad, [], "review dispatch pinned below Opus:\n" + "\n".join(bad))

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
        ]
        for text in caught:
            with self.subTest(text=text):
                self.assertEqual(len(downshift_findings(text)), 1)
        spared = [
            "Never `sonnet`/`haiku` for a review pass.",
            "The cost downshift to `sonnet`/`haiku` is for search, never for a review or REFUTE pass.",
            'Explore search uses model: "sonnet".',
            "- v1.2.2 (2026-10-30): reviewer runs on sonnet were moved to opus.",
        ]
        for text in spared:
            with self.subTest(text=text):
                self.assertEqual(downshift_findings(text), [])

if __name__ == "__main__":
    unittest.main()
