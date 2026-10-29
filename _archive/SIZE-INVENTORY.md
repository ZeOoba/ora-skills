# _archive size inventory (files over 500 KB)

Generated 2026-10-29 from the tracked tree at the time of this commit. Threshold: > 500 KB (512,000 bytes), all tracked files in the repo, not only `_archive/`. Report only: nothing was removed, moved or rewritten.

**Removal needs the owner's explicit decision.** The owner's standing rule is never delete (move to archive), and git history keeps every blob regardless, so deleting a working-tree file would not shrink clone size. Any future clean-up (for example a history rewrite) is a separate decision for Gabriel.

| Path | Bytes | sha256 | Byte-identical copy elsewhere in tree |
|---|---:|---|---|
| `_archive/2026-08-21_repo-first-rescue-triage/loi-generation-merged-3c477f5/rescued-copy/templates/LOI_Master_Template_Condensed.docx` | 2,873,271 | `789e6d86f19999d266430f6329b579d635d8e2bf4e4d07b69c58a1833b659ece` | no |
| `loi-generation/templates/LOI_Master_Template_Condensed.docx` | 2,873,197 | `bad3af53f0ff7928a237820d20032ca2b16788ef880aff6799418975c5318689` | no |
| `_archive/2026-08-22_eventlog-localmainlog-splice/new_blob.bin` | 1,383,803 | `c1124d6eb751741fb034331692e4d1a3ec3ed0f497a49e4c9dbb034b95f16c36` | no |
| `_archive/2026-08-22_eventlog-register-scheduled-task-splice/new_blob.bin` | 1,380,220 | `02b2a52c93a7fddd2cb483058e912a9226585b5b09cbe2e710815859a8360d19` | no |
| `_archive/2026-08-21_eventlog-isolated-commit-splice/new_blob.bin` | 1,377,449 | `94c31d898919bf72fd1cb2ea6af60d72b18b5e66c906a77d7a344bc02488302b` | no |
| `_archive/2026-08-16_eventlog-commit-scratch/el_base_plus_mine_py.md` | 1,187,019 | `62968d4c1c6849ca37eb9949f38b3e273dbbc3cb42e3b49ca64523f6831fd89c` | no |
| `_archive/2026-08-16_eventlog-commit-scratch/el_base_plus_mine_UNEXECUTED-ATTEMPT.md` | 1,185,089 | `25a651a7fe742d1830d9665d7350c760c71998002e53e230c40edd73fac6b831` | `_archive/2026-08-16_eventlog-commit-scratch/el_base_py.md`, `_archive/2026-08-16_eventlog-commit-scratch/true_blob.md`, `_archive/2026-08-21_staging-full-sweep-triage/2026-08-16/el_base_v2.md` |
| `_archive/2026-08-16_eventlog-commit-scratch/el_base_py.md` | 1,185,089 | `25a651a7fe742d1830d9665d7350c760c71998002e53e230c40edd73fac6b831` | `_archive/2026-08-16_eventlog-commit-scratch/el_base_plus_mine_UNEXECUTED-ATTEMPT.md`, `_archive/2026-08-16_eventlog-commit-scratch/true_blob.md`, `_archive/2026-08-21_staging-full-sweep-triage/2026-08-16/el_base_v2.md` |
| `_archive/2026-08-16_eventlog-commit-scratch/true_blob.md` | 1,185,089 | `25a651a7fe742d1830d9665d7350c760c71998002e53e230c40edd73fac6b831` | `_archive/2026-08-16_eventlog-commit-scratch/el_base_plus_mine_UNEXECUTED-ATTEMPT.md`, `_archive/2026-08-16_eventlog-commit-scratch/el_base_py.md`, `_archive/2026-08-21_staging-full-sweep-triage/2026-08-16/el_base_v2.md` |
| `_archive/2026-08-21_staging-full-sweep-triage/2026-08-16/el_base_v2.md` | 1,185,089 | `25a651a7fe742d1830d9665d7350c760c71998002e53e230c40edd73fac6b831` | `_archive/2026-08-16_eventlog-commit-scratch/el_base_plus_mine_UNEXECUTED-ATTEMPT.md`, `_archive/2026-08-16_eventlog-commit-scratch/el_base_py.md`, `_archive/2026-08-16_eventlog-commit-scratch/true_blob.md` |
| `_archive/2026-08-16_eventlog-commit-scratch/el_base_UNEXECUTED-ATTEMPT.md` | 1,176,203 | `e4064de2d1dfb5fa691084abf8c95e4cf88f6164670ae53f0f8be52e52e3925e` | no |
| `_archive/2026-08-21_staging-full-sweep-triage/2026-08-15/head_plus_mine.md` | 1,096,573 | `3a56021b98b27b82966d5694bb7b84977e096c6ab3d5c743a894977781c064ab` | no |
| `_archive/2026-08-21_staging-full-sweep-triage/2026-08-15/head_base.md` | 1,094,178 | `e8e558931a37b31830a70f933bede544cdd3d3cd9f979eeaa3f14a583f0468c1` | no |
| `cowork-settings/fonts/EBGaramond-Regular.ttf` | 851,176 | `684fcc0db2239b43497341d596d68422ea60ef7522cf2e857071ad84e4ade2a4` | no |
| `cowork-settings/fonts/EBGaramond-Italic.ttf` | 754,468 | `b76b365299331ddff5f8077648ef3b6fbb67f3bd15bebb955a42c6e57904aed0` | no |

Notes: the archived `LOI_Master_Template_Condensed.docx` and the live `loi-generation/templates/` copy differ by 74 bytes, so they are near-duplicates, not byte-identical. The live `loi-generation` and `cowork-settings` files above are not archive scratch and are listed for completeness only; they must not be touched by any archive clean-up.
