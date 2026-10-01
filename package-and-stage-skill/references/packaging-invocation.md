# Step 3 — canonical invocation and resource lint

Moved verbatim from `SKILL.md` (v1.36 core/reference split, no rule changed). `SKILL.md` keeps each rule's headline as a stub; this file holds the full wording. Read the relevant section BEFORE acting.

## Detail (was SKILL.md step 3 lines 105–113)

   **Canonical invocation (copy, don't re-derive).** Write the script with Desktop Commander `write_file` to an absolute path under the repo or `_staging` (never a temp path the host can't resolve), then run it:
   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File "<absolute-path-to-script>.ps1"
   ```
   Inside the `.ps1`, use one `Set-Location` line (or fully-qualified paths) — Windows PowerShell 5.1 has no `&&` statement separator and throws `InvalidEndOfLine` on `cmd1 && cmd2`. `$` variables and multi-statement logic are unrestricted inside the file.

   **`Start-Process -ArgumentList` splits on spaces — and EVERY ORA root has spaces (v1.27).** Pass ONE pre-formatted string with every path quoted inside it, never the array form — the array form does not error, it runs against the wrong target (`C:\Users\Owner\OneDrive` instead of the Business tree) and prints a confident result. Sanity-check the item count any detached job reports before believing its verdict. **Read references/host-shell-snippets.md § Start-Process -ArgumentList before writing any detached PowerShell job.**

   **Resource-lint any skill that ships `scripts/`, before packaging (v1.27):** `python tools/script_resource_lint.py <skill>`. Flags `openpyxl.load_workbook()` without `read_only=True`, unbounded `pandas.read_*`, whole-file `.read()`, materialised recursive walks, and the `Start-Process -ArgumentList` array form. Advisory, not blocking; silence a deliberate hit with `# resource-ok: <reason>` on the flagged line. No other gate looks at resource behaviour — "it only reads files" is not a resource argument. Incident (9.1 GB, model-bulk-edit v1.0): `references/incident-history.md` § Resource lint.
