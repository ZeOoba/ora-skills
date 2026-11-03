"""Tests for tools/package_batch.py (step order, guards, stop-on-failure)."""
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import package_batch as pb  # noqa: E402


class FakeRunner:
    def __init__(self, fail_on=None, dirty="", rc=7):
        self.calls, self.fail_on, self.dirty, self.rc = [], fail_on, dirty, rc

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if cmd[:2] == ["git", "-C"] and "status" in cmd:
            return types.SimpleNamespace(returncode=0, stdout=self.dirty, stderr="")
        if cmd[:2] == ["git", "-C"]:
            return types.SimpleNamespace(returncode=0, stdout="abc123 head", stderr="")
        step = Path(cmd[1]).name + ":" + (cmd[2] if len(cmd) > 2 else "")
        rc = self.rc if self.fail_on and self.fail_on in step else 0
        return types.SimpleNamespace(returncode=rc, stdout="", stderr="")

    def tool_calls(self):
        return [c for c in self.calls if c[0] != "git"]


class PackageBatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = str(Path(self.tmp.name) / "out")
        self.skill = next(p.parent.name for p in sorted(pb.REPO.glob("*/SKILL.md")))

    def tearDown(self):
        self.tmp.cleanup()

    def test_steps_in_order_with_package_paths_for_precheck(self):
        steps = pb.build_steps(self.out, ["s1", "s2"])
        self.assertEqual([s[0] for s in steps], ["baseline", "package", "emit", "precheck"])
        pre = steps[-1][1]
        self.assertEqual([Path(p).name for p in pre[3:]], ["s1.skill", "s2.skill"])
        self.assertNotIn("baseline", [s[0] for s in pb.build_steps(self.out, ["s1"], baseline=False)])

    def test_empty_skill_list_is_refused(self):
        r = FakeRunner()
        self.assertEqual(pb.main([self.out], runner=r), 2)
        self.assertEqual(r.tool_calls(), [])   # never reaches package_skills (which would package ALL)

    def test_unknown_option_and_bad_names_are_refused(self):
        self.assertEqual(pb.main([self.out, self.skill, "--bogus"], runner=FakeRunner()), 2)
        self.assertEqual(pb.main([self.out, "no-such-skill-xyz"], runner=FakeRunner()), 2)
        self.assertEqual(pb.main([self.out, "../" + self.skill], runner=FakeRunner()), 2)

    def test_dirty_skill_is_refused_unless_allowed(self):
        r = FakeRunner(dirty=" M x/SKILL.md\n")
        self.assertEqual(pb.main([self.out, self.skill], runner=r), 2)
        self.assertEqual(r.tool_calls(), [])
        self.assertEqual(pb.main([self.out, self.skill, "--allow-dirty"], runner=FakeRunner(dirty="M")), 0)

    def test_stops_at_first_failing_step(self):
        r = FakeRunner(fail_on="package_skills.py")
        self.assertEqual(pb.main([self.out, self.skill], runner=r), 7)
        names = [Path(c[1]).name for c in r.tool_calls()]
        self.assertEqual(names, ["reimport_correlate.py", "package_skills.py"])

    def test_happy_path_runs_all_four(self):
        r = FakeRunner()
        self.assertEqual(pb.main([self.out, self.skill, self.skill], runner=r), 0)
        self.assertEqual(len(r.tool_calls()), 4)
        self.assertEqual(r.tool_calls()[1][-1], self.skill)   # de-duplicated

    def test_stale_package_in_out_dir_is_refused(self):
        Path(self.out).mkdir(parents=True)
        (Path(self.out) / "other-skill.skill").write_bytes(b"x")
        r = FakeRunner()
        self.assertEqual(pb.main([self.out, self.skill], runner=r), 2)
        self.assertEqual(r.tool_calls(), [])   # emit would have hashed other-skill into HANDOFF

    def test_same_batch_package_in_out_dir_is_allowed(self):
        Path(self.out).mkdir(parents=True)
        (Path(self.out) / f"{self.skill}.skill").write_bytes(b"x")   # rerun overwrites it
        self.assertEqual(pb.main([self.out, self.skill], runner=FakeRunner()), 0)

    def test_out_dir_colliding_with_a_skill_dir_is_refused_before_baseline(self):
        r = FakeRunner()
        self.assertEqual(pb.main([str(pb.REPO / self.skill), self.skill], runner=r), 2)
        self.assertEqual(pb.main([str(pb.REPO), self.skill], runner=r), 2)
        self.assertEqual(r.tool_calls(), [])

    def test_allow_dirty_reaches_package_skills_shared_deps(self):
        r = FakeRunner()
        self.assertEqual(pb.main([self.out, self.skill, "--allow-dirty"], runner=r), 0)
        self.assertIn("--allow-dirty-shared", r.tool_calls()[1])
        r = FakeRunner()
        pb.main([self.out, self.skill], runner=r)
        self.assertNotIn("--allow-dirty-shared", r.tool_calls()[1])

    def test_guard_checks_shared_root_deps(self):
        skill = next(s for s in sorted(pb.SHARED_ROOT_DEPS) if (pb.REPO / s / "SKILL.md").is_file())
        dep = pb._dep_pair(pb.SHARED_ROOT_DEPS[skill][0])[0]
        r = FakeRunner()
        self.assertEqual(pb.guard([skill], runner=r), [])
        status = [c for c in r.calls if "status" in c]
        self.assertEqual(len(status), 1)
        self.assertIn(dep, status[0])

    def test_signal_killed_step_maps_to_shell_code(self):
        r = FakeRunner(fail_on="package_skills.py", rc=-9)
        self.assertEqual(pb.main([self.out, self.skill], runner=r), 137)


if __name__ == "__main__":
    unittest.main()
