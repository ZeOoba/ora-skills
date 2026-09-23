"""Tests for reimport_cycle.gate_failures (pure gate logic)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reimport_cycle as rc  # noqa: E402

SKILL = "loi-generation"  # exists in the repo
clean = lambda s: False  # noqa: E731
dirty = lambda s: True  # noqa: E731
no_plugin = lambda s: None  # noqa: E731


def test_clean_standalone_passes():
    assert rc.gate_failures(SKILL, no_plugin, clean, set(), "") == []


def test_plugin_member_stops():
    bad = rc.gate_failures(SKILL, lambda s: "ora-ops", clean, set(), "")
    assert any("plugin member" in b for b in bad)


def test_dirty_tree_stops():
    assert any("dirty" in b for b in rc.gate_failures(SKILL, no_plugin, dirty, set(), ""))


def test_missing_skill_stops():
    assert any("SKILL.md" in b for b in
               rc.gate_failures("no-such-skill-xyz", no_plugin, clean, set(), ""))


def test_cache_ahead_stops_only_consumer():
    rep = f"  target-markets.json: CACHE-AHEAD {SKILL}"
    assert rc.gate_failures(SKILL, no_plugin, clean, {SKILL}, rep)
    assert rc.gate_failures(SKILL, no_plugin, clean, set(), rep) == []


def test_ok_dep_report_passes_consumer():
    rep = f"  target-markets.json: OK\n     in sync: {SKILL}"
    assert rc.gate_failures(SKILL, no_plugin, clean, {SKILL}, rep) == []


def test_every_bad_label_stops():
    for lbl in rc.BAD_DEP_LABELS:
        assert rc.gate_failures(SKILL, no_plugin, clean, {SKILL}, f"dep: {lbl} {SKILL}")
