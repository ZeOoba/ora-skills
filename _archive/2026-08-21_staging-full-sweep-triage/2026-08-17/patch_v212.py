# -*- coding: utf-8 -*-
"""register-scheduled-task v2.11 -> v2.12. Exact-anchor patch; asserts every replacement lands."""
import io, re, sys

SK = r"C:\Users\Owner\ora-skills\register-scheduled-task\SKILL.md"
IH = r"C:\Users\Owner\ora-skills\register-scheduled-task\references\incident-history.md"

def rd(p):
    return io.open(p, encoding="utf8").read()

def wr(p, s):
    io.open(p, "w", encoding="utf8", newline="\n").write(s)

s = rd(SK)
orig = s

def sub(old, new, label):
    global s
    assert s.count(old) == 1, "ANCHOR FAIL (%d hits): %s" % (s.count(old), label)
    s = s.replace(old, new)

# --- 1. frontmatter description: trim to make room, add the new rule + trigger vocab ---
sub("a cloud-vs-on-device surface note for the registry MCP tools, an id-collision "
    "fleet-resolution safety rule (never test via a live delete), and the registration QC gate. "
    "v2.11 (2026-08-17)",
    "a cloud-vs-on-device surface note, an id-collision safety rule (never test via a live "
    "delete), a bounded-pause rule (pause all routines until X, resume, un-pause) requiring a "
    "resume registered per fleet, same pass, and the registration QC gate. "
    "v2.12 (2026-08-17)",
    "frontmatter description")

sub("# Register Scheduled Task (ORA) \u2014 v2.11",
    "# Register Scheduled Task (ORA) \u2014 v2.12",
    "title heading")

# --- 2. new section, inserted between "Update / pause / retire" and "Concurrent-writer check" ---
NEW = u"""## Bounded pause — the resume is part of the pause, not a follow-up

- **Rule:** a pause with a stated or implied end ("until Friday," "for two weeks," "while I'm out") is NOT complete until its resume task is registered — or confirmed already registered — in the SAME supervised session, on the SAME surface, in the SAME pass. Bulk is the aggravating factor, not the trigger: one task paused "until Friday" fails identically. A genuinely open-ended pause has no resume to register — say that explicitly rather than skipping the step silently.
- **"Pause all routines" is FLEET-AMBIGUOUS — resolve it before acting.** The instruction names no fleet, so enumerate BOTH registries, state which are in scope, and register one resume per fleet in scope. A resume task cannot reach the other fleet's registry (`update_scheduled_task` resolves session-local — see PATH-DISAMBIGUATOR). Reporting "N tasks paused" after touching one fleet reads as complete and is the exact shape of the root incident below.
- **Never blanket-pause the detectors.** `ora-cowork-heartbeat` (dead-man chain → Notion `35c6ecd8…` → GitHub watchdog) and `automation-health-monitor` are what would otherwise surface a failed resume — and BOTH live on LAMS, so a LAMS-wide pause silences the detector for its own failure. Either carve them out of the pause, or state plainly in the same turn that the dead-man chain and health monitor are down for the window and will not report the gap.
- **Verify before reporting done:** `list_scheduled_tasks` shows the resume task for EACH paused fleet — id, `fireAt` (a one-time resume carries `fireAt`, not `cronExpression`/`nextRunAt`), and an id list matching exactly what was paused — pasted in the SAME response that reports the pause complete. If the current surface cannot reach the MCP tools for either half, STOP per Rule 1 and name which half is missing; never report "N tasks paused" without either a registered resume or an explicit flag that none exists.
- **A resume does NOT re-stamp `[MODEL:]` dates.** Re-enabling returns a task to tag scope, which makes it DUE for a currency check — it is not itself an observation. A resume task must not bump `checked`/`set` dates on the tasks it flips; that fabricates a verification (`memory/feedback_verified_null_vs_inferred_null.md`). This QUALIFIES the PAUSE bullet's "re-tag in the same pass" above: that binds a hand re-enable where the model IS observed, not an automated bulk resume.
- Root incident (2026-08-17) + the verified fleet asymmetry it left behind: `references/incident-history.md` § Bounded pause.

"""

sub("## Concurrent-writer check (before any registration/recovery/bulk-retire session)",
    NEW + "## Concurrent-writer check (before any registration/recovery/bulk-retire session)",
    "new section insert")

# --- 3. QC gate ---
sub("· automation-health-monitor coverage flagged for its next list revision.",
    "· **for any bounded pause: a resume task verified present for EVERY paused fleet, "
    "or its absence flagged same-turn** · automation-health-monitor coverage flagged for its "
    "next list revision.",
    "QC gate")

# --- 4. changelog ---
CL = u"""- **v2.12 (2026-08-17):** Added "Bounded pause — the resume is part of the pause, not a follow-up." A pause with a stated end must register its resume in the same supervised session/surface/pass, per fleet; "pause all routines" is fleet-ambiguous and must be resolved against both registries before acting; the heartbeat/health-monitor detectors must not be swept into a blanket pause without saying so; and a resume must NOT re-stamp `[MODEL:]` dates (which qualifies v2.8's re-enable re-tag rule — that binds a hand re-enable, not an automated bulk resume). Root incident: a 2026-08-17 "pause all routines until Friday 5pm" was executed on CC/MCP with a resume registered (`ora-routine-pause-resume-08-21`, fires 2026-08-21 17:00 ET), while the LAMS/Cowork counterpart pause landed with NO resume — verified same day: 35/40 CC tasks disabled with a resume pending, 27/28 LAMS tasks disabled with none, including `ora-cowork-heartbeat` and `automation-health-monitor` themselves. Doc-only; no registration, cron, or archive-first-delete-second logic changed.
"""

sub("## Changelog\n\n- **v2.11 (2026-08-17):**",
    "## Changelog\n\n" + CL + "- **v2.11 (2026-08-17):**",
    "changelog")

# --- assertions ---
b = re.match(r"^---\n(.*?)\n---\n", s, re.S).group(1)
name = re.search(r"^name:\s*(\S+)\s*$", b, re.M).group(1)
desc = re.search(r"^description:\s*(.*?)\s*$", b, re.M | re.S).group(1)
problems = []
if name != "register-scheduled-task":
    problems.append("name %r != dir" % name)
if len(desc) > 1024:
    problems.append("description %d/1024 OVER" % len(desc))
if problems:
    print("FAIL:", "; ".join(problems)); sys.exit(1)

wr(SK, s)
print("OK  name=%s  description=%d/1024" % (name, len(desc)))
print("SKILL.md %d -> %d bytes" % (len(orig.encode("utf8")), len(s.encode("utf8"))))
