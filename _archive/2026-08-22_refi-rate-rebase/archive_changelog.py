import io, os, re, sys
SK = r"C:\Users\Owner\ora-skills\acquisition-underwriting\SKILL.md"
OLD = r"C:\Users\Owner\ora-skills\acquisition-underwriting\versions\CHANGELOG-v3.2-v4.7.md"
NEW = r"C:\Users\Owner\ora-skills\acquisition-underwriting\versions\CHANGELOG-v3.2-v4.9.md"

s = io.open(SK, encoding="utf8", newline="").read().replace("\r\n", "\n")

def take(tag):
    m = re.search(r"^\*\*" + re.escape(tag) + r" \(\d{4}-\d{2}-\d{2}\):\*\*.*?$", s, re.M)
    assert m, "anchor missing: " + tag
    return m.group(0)

v49, v48 = take("v4.9"), take("v4.8")

# 1. strip the two paragraphs (plus their trailing blank line) out of SKILL.md
for para in (v49, v48):
    before = s
    s = s.replace(para + "\n\n", "", 1)
    assert s != before, "removal failed"

# 2. append them to the archive, verbatim
arch = io.open(OLD, encoding="utf8", newline="").read().replace("\r\n", "\n")
assert "**v4.8 (2026-08-03):**" not in arch, "archive already carries the v4.8 entry"
arch = arch.replace("# acquisition-underwriting — archived version history (v3.2 through v4.7)",
                    "# acquisition-underwriting — archived version history (v3.2 through v4.9)", 1)
arch = arch.rstrip("\n") + (
    "\n\n**v4.8 and v4.9 appended 2026-08-22** — the inline block had grown to seven revisions "
    "against this file's own \"four most recent stay inline\" policy (set at v4.9 itself). Verbatim; "
    "every operating rule both revisions introduced is independently restated in the body sections of "
    "`SKILL.md`.\n\n" + v49 + "\n\n" + v48 + "\n")
io.open(NEW, "w", encoding="utf8", newline="\n").write(arch)

# 3. repoint the two references
a = "Revision history through v4.7 is archived at `versions/CHANGELOG-v3.2-v4.7.md`"
b = "Revision history through v4.9 is archived at `versions/CHANGELOG-v3.2-v4.9.md`"
assert a in s; s = s.replace(a, b, 1)

m = re.search(r"^\*\*Earlier revisions v4\.6–v4\.7 archived\*\*.*?$", s, re.M)
assert m, "earlier-revisions pointer missing"
s = s.replace(m.group(0),
  "**Earlier revisions v4.6–v4.9 archived** to `versions/CHANGELOG-v3.2-v4.9.md` "
  "(v4.6–v4.7 on 2026-08-13; v4.8–v4.9 on 2026-08-22, restoring this file's own "
  "\"four most recent stay inline\" policy) — provenance only, every operative number/rule "
  "independently restated in its own section below.", 1)

# 4. version bump
a = "# Acquisition Underwriting — Oxford Realty Advisors (v4.14 — Buy Box & Scorecard v1.1)"
assert a in s
s = s.replace(a, "# Acquisition Underwriting — Oxford Realty Advisors (v4.15 — Buy Box & Scorecard v1.1)", 1)

# 5. consumer-sweep rule, anchored before the zoning-letter bullet
anchor = "- Zoning letter from municipality pre-LOI."
assert anchor in s
rule = (
 "- **Conventions-change consumer sweep (v4.15) — a constant changed here is not a constant changed "
 "everywhere.** Whenever any number in this UNDERWRITING CONVENTIONS section moves (refi rate, "
 "amortization, term, financing cost, exit-cap table, RCT version), the change is not complete until a "
 "sweep confirms every consumer carries it. Three places to check, in order: (i) **sibling skills** — "
 "grep `ora-skills` for the old value; (ii) **live workbooks** — the `Inputs` tab of every model under "
 "`Business\\Investment Candidates -- 2026`, since a model built before the change keeps the old value "
 "silently and its DSCR/IRR/proceeds stay stale; (iii) **`target-markets.json`**, where the market-level "
 "constants live. Report what was found and what was left alone; a model belonging to a closed or passed "
 "deal is a historical record and is rebased only on Gabriel's instruction, never by default. Origin "
 "(2026-08-22, refi 7.00%→6.50%): the doctrine edit took minutes, and the sweep then found ten live "
 "workbooks still on 7.00% with no mechanism that would ever have surfaced them. **Corollary — a "
 "repeated per-deal override IS the drift signal.** That same sweep found four models already at 6.5%, "
 "one labelled \"Refi rate (Gabriel-directed override, 2026-07)\": doctrine had been trailing actual "
 "practice by about a month, and nothing was watching for it. When a sweep finds the same constant "
 "overridden by hand on two or more deals, raise it as a QUESTIONS FOR GABRIEL item proposing the "
 "doctrine change — do not keep overriding.\n")
s = s.replace(anchor, rule + anchor, 1)

# 6. v4.15 changelog entry
anchor = "**v4.14 (2026-08-22):**"
assert anchor in s
entry = (
 "**v4.15 (2026-08-22):** Two housekeeping items, no doctrine math touched. **(1) Inline changelog "
 "restored to policy** — v4.8 and v4.9 moved verbatim to `versions/CHANGELOG-v3.2-v4.9.md` (renamed from "
 "`-v4.7`). The inline block had reached seven revisions against the \"four most recent stay inline\" rule "
 "this file set for itself at v4.9, and the excess was being paid on every single invocation. "
 "**(2) New UNDERWRITING CONVENTIONS rule: conventions-change consumer sweep** — a constant changed in "
 "this section is not changed until sibling skills, live workbook `Inputs` tabs, and `target-markets.json` "
 "have been checked, with a corollary that two or more hand overrides of the same constant is itself the "
 "signal to change doctrine. Both items came out of the 2026-08-22 refi-rate change (v4.13), where the "
 "edit itself was trivial and the ten stale workbooks behind it were found only because someone went "
 "looking. **No scorecard weight, Stage 1 floor, or governor constant (DSCR 1.25x / per-property LTV 65% / "
 "portfolio-aggregate LTV 40%) changed.**\n\n")
s = s.replace(anchor, entry + anchor, 1)

io.open(SK, "w", encoding="utf8", newline="\n").write(s)
print("OK: SKILL.md rewritten; archive ->", os.path.basename(NEW))
print("inline revisions now:", re.findall(r"^\*\*(v4\.\d+) \(", s, re.M))
