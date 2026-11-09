"""verified-deal-recon references copy: a vintage-ramp floor miss caps the verdict at NEEDS_MORE.

Gabriel in-turn ruling 2026-11-08 (ORA skills medium triage, vdr-synthesis-below-replacement-pursue
+ X4): missing the ratified vintage-ramp floor caps the pre-screen verdict at NEEDS_MORE whatever the
value-add upside. The synthesis prompt in verified-deal-recon/references/verified-deal-recon.js used
to read "below-replacement OR clear value-add upside -> PURSUE", contradicting the floor its own recon
prompt states. The ~/.claude workflow copy is fixed in ora-claude-config (fix/vdr-pursue-floor); this
copy matches its wording and its post-synthesis cap.

Two layers: the prompt text (static) and the cap (the script run under node with mocked agents, the
same mock technique as ora-claude-config's workflows/_tests/test-verified-deal-recon.mjs). node is
on ubuntu-latest and the self-hosted Windows runner; a missing node fails, it never skips.
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / 'verified-deal-recon' / 'references' / 'verified-deal-recon.js'

HARNESS = r"""
import { readFileSync } from 'node:fs';
const [scriptPath, synthJson] = process.argv.slice(2);
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
let src = readFileSync(scriptPath, 'utf8').replace(/^export\s+/m, '');
const calls = [];
const synth = JSON.parse(synthJson);
const canned = {
  recon: { snapshot: 'S', fitVsBox: 'fits', rentComps: 'rc', saleComps: 'sc', submarket: 'sub', demand: ['d'],
           basisRead: 'b', redFlags: [], recommendation: { verdict: 'PURSUE', oneLineWhy: 'w' }, sources: [] },
  synthesis: synth,
};
const agent = async (prompt, opts = {}) => {
  calls.push({ label: opts.label, prompt });
  if (opts.label in canned) return canned[opts.label];
  if (String(opts.label).startsWith('verify:')) {
    return { lens: opts.label, claimsChecked: [], flipsRecommendation: false, lensVerdict: 'holds' };
  }
  throw new Error('no canned response for ' + opts.label);
};
const parallel = (thunks) => Promise.all(thunks.map((t) => t().catch(() => null)));
const noop = () => {};
const fn = new AsyncFunction('agent', 'parallel', 'pipeline', 'phase', 'log', 'args', 'budget', 'workflow', src);
const result = await fn(agent, parallel, noop, noop, noop, { property: '1 Test St, Columbus OH', today: '2026-11-08' },
                        { total: null, spent: () => 0, remaining: () => Infinity }, noop);
const synthCall = calls.find((c) => c.label === 'synthesis');
console.log(JSON.stringify({ result, synthPrompt: synthCall ? synthCall.prompt : null }));
"""


def synthesis(**over):
    base = {'verdict': 'PURSUE', 'oneLineThesis': 't', 'snapshot': 's', 'basisRead': 'b',
            'basisClearsFloor': 'YES', 'killRisks': [], 'preMortem': 'p', 'openItems': ['x'],
            'confidence': 'medium'}
    base.update(over)
    return {k: v for k, v in base.items() if v is not None}


class FloorCapRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which('node')
        if not cls.node:
            raise AssertionError('node is required for this suite (present on ubuntu-latest and the self-hosted runner)')
        cls.tmp = tempfile.TemporaryDirectory()
        cls.harness = Path(cls.tmp.name) / 'harness.mjs'
        cls.harness.write_text(HARNESS, encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_with(self, synth):
        out = subprocess.run([self.node, str(self.harness), str(SCRIPT), json.dumps(synth)],
                             capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout.strip().splitlines()[-1])

    def test_pursue_that_misses_the_floor_is_capped(self):
        for state in ('NO', 'UNKNOWN', None):
            got = self.run_with(synthesis(basisClearsFloor=state))
            self.assertEqual(got['result']['brief']['verdict'], 'NEEDS_MORE', state)
            self.assertEqual(got['result']['verdictCap']['to'], 'NEEDS_MORE', state)
            self.assertIn('vintage-ramp floor', got['result']['brief']['openItems'][-1])

    def test_lowercase_pursue_is_still_capped(self):
        got = self.run_with(synthesis(verdict='pursue', basisClearsFloor='NO'))
        self.assertEqual(got['result']['brief']['verdict'], 'NEEDS_MORE')

    def test_pursue_that_clears_the_floor_stands(self):
        got = self.run_with(synthesis(basisClearsFloor='YES'))
        self.assertEqual(got['result']['brief']['verdict'], 'PURSUE')
        self.assertIsNone(got['result']['verdictCap'])

    def test_pass_and_needs_more_pass_through(self):
        for verdict in ('PASS', 'NEEDS_MORE'):
            got = self.run_with(synthesis(verdict=verdict, basisClearsFloor='NO'))
            self.assertEqual(got['result']['brief']['verdict'], verdict)
            self.assertIsNone(got['result']['verdictCap'])

    def test_ledger_row_carries_the_capped_verdict(self):
        got = self.run_with(synthesis(basisClearsFloor='NO'))
        self.assertIn('| NEEDS_MORE |', got['result']['ledgerRowDraft'])

    def test_synthesis_prompt_makes_the_floor_necessary(self):
        prompt = self.run_with(synthesis())['synthPrompt']
        self.assertIn('Clearing the floor is NECESSARY for PURSUE; value-add upside never substitutes for it.', prompt)
        self.assertIn('NEEDS_MORE at most, regardless of value-add upside', prompt)


class PromptText(unittest.TestCase):
    def setUp(self):
        self.text = SCRIPT.read_text(encoding='utf-8')

    def test_upside_alone_never_reaches_pursue(self):
        self.assertNotRegex(self.text, re.compile(r'value-add upside\s*->\s*PURSUE', re.I))
        self.assertNotIn('below-replacement OR clear value-add upside', self.text)

    def test_schema_requires_basis_clears_floor(self):
        self.assertIn("basisClearsFloor:{type:'string', enum:['YES','NO','UNKNOWN']}", self.text)
        self.assertRegex(self.text, r"required:\['verdict','oneLineThesis','snapshot','basisRead','basisClearsFloor'")

    def test_recon_and_lens_state_the_cap(self):
        self.assertIn('a floor miss caps the recommendation at NEEDS_MORE regardless of value-add upside', self.text)
        self.assertIn('A floor miss caps the verdict at NEEDS_MORE but is not an automatic kill.', self.text)
        self.assertNotRegex(self.text, r'prefer >=\s*25% below')


if __name__ == '__main__':
    unittest.main()
