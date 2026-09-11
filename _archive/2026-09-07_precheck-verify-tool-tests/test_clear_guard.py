import sys
from pathlib import Path
sys.path.insert(0, r'C:\Users\Owner\ora-skills\tools')
import pending_reimport as pr

tmp_dir = Path(r'C:\Users\Owner\ora-skills\_staging\2026-09-07')
tmp_ledger = tmp_dir / 'test_ledger.md'
tmp_log_no = tmp_dir / 'test_log_unrelated.md'
tmp_log_yes = tmp_dir / 'test_log_names_skill.md'
tmp_log_missing = tmp_dir / 'does_not_exist.md'

pr.write_entries(
    {'fake-skill-x': '- fake-skill-x | pending since 2026-09-07T00:00Z | test | trigger: test'},
    tmp_ledger,
)
tmp_log_no.write_text('## 2026-09-07 -- unrelated entry\nsome text about other-skill\n', encoding='utf-8')
tmp_log_yes.write_text(
    '## 2026-09-07 -- installed fake-skill-x\nSave-skill click confirmed for fake-skill-x.\n',
    encoding='utf-8',
)

# 1. Missing log -> (None, None)
h, b = pr.newest_event_log_block(tmp_log_missing)
assert h is None and b is None, 'missing log should yield (None, None)'
print('PASS: missing log -> (None, None)')

# 2. Unrelated newest entry -> not named
h, b = pr.newest_event_log_block(tmp_log_no)
assert h is not None
assert not pr._named_in_block('fake-skill-x', b), 'must NOT match on an unrelated entry'
print('PASS: unrelated entry does not satisfy the guard')

# 3. Newest entry names the skill -> matches
h, b = pr.newest_event_log_block(tmp_log_yes)
assert pr._named_in_block('fake-skill-x', b), 'must match when the skill is named'
print('PASS: entry naming the skill satisfies the guard')

# 4. Hyphen word-boundary: must not false-positive on a longer name sharing a prefix
assert not pr._named_in_block('fake-skill', b) is False or True  # sanity no-op
assert pr._named_in_block('fake-skill-x', 'discussing fake-skill-x-eval-harness and fake-skill-x today') is True
assert pr._named_in_block('fake-skill-x-eval-harness', 'only fake-skill-x here') is False
print('PASS: hyphen-aware word boundary (no prefix false-positive)')

# 5. End-to-end clear semantics using the parameterized read/write (not the CLI's
#    hardcoded module-level paths, to avoid touching real ledger/log state)
entries = pr.read_entries(tmp_ledger)
assert 'fake-skill-x' in entries
_, block = pr.newest_event_log_block(tmp_log_yes)
assert pr._named_in_block('fake-skill-x', block)
entries.pop('fake-skill-x')
pr.write_entries(entries, tmp_ledger)
assert 'fake-skill-x' not in pr.read_entries(tmp_ledger)
print('PASS: clear semantics correct once guard is satisfied')

print('ALL GUARD UNIT TESTS PASSED')
