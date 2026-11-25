---
name: "ora-business-search"
description: "Use before browsing, listing or grepping ORA's OneDrive Business folder for any fact, document or file: query the full-text index first, then fall back to Microsoft 365 search."
---

# ORA Business folder: search the index first

The OneDrive `Business` folder (~11,000 documents: property folders, corporate records, leases, loans, PM reports, investment candidates) has a full-text index. Query it **before** any `ls`, `find`, folder walk or file-by-file reading. Reading files through the desktop mount costs 0.3–2 s each (OneDrive downloads them first); one index query searches everything indexed in under a second.

## Location
| Surface | Path |
|---|---|
| Cowork / device_bash (folder connected) | `$HOME/mnt/Business/_Search Index/` |
| Windows | `C:\Users\Owner\OneDrive - Oxford Capital Partners\Business\_Search Index\` |
| WSL | `/mnt/c/Users/Owner/OneDrive - Oxford Capital Partners/Business/_Search Index/` |

If the Business folder is not connected, ask Gabriel to connect it ("Add folder" in the desktop app) or go straight to step 3.

## Procedure
1. **Search the index** with `search.py` (read-only; safe while OneDrive syncs):
   ```
   cd "$HOME/mnt/Business/_Search Index"
   python3 search.py "exact phrase" "second phrase"        # each argument is a phrase; all must match
   python3 search.py "AEP OR Evergy" --folder "1100 Rarig"  # FTS5: OR, NOT, prefix*, NEAR(a b, 10)
   python3 search.py roof warranty --ext pdf -n 30
   python3 search.py Lamar --names                           # file/folder names only
   python3 search.py --status                                # coverage
   ```
   Run several targeted queries (entity names, defined terms, account numbers, addresses, counterparties) before concluding something is absent. Try synonyms and prefixes (`recapt*`, `"Site Access Fee"`, `"duration of the Company"`).
2. **Read only the hits.** Open the specific files the index returned to confirm wording and cite them. Never cite a snippet alone for a legal or financial term; read the clause.
3. **Fall back to Microsoft 365 search** when a hit is tagged `pending`, `deferred_large` or `needs_ocr`, when the index finds nothing, or when the folder is not connected. Use the M365 connector's SharePoint/OneDrive search (`mcp__ms365__sharepoint_search`, loaded via ToolSearch). Microsoft indexes file contents server-side, so it covers files the local index has not read yet. Read results with `mcp__ms365__read_resource`.
4. **Browse folders only as a last resort.** If you do, say so, and note which files were unreadable (scanned images, etc.).

## Reading result tags
| Tag | Meaning | Action |
|---|---|---|
| (none) / ok | Full text indexed | Trust the hit; read the file to cite |
| ok_ocr | Text recovered by OCR | Verify numbers against the page image |
| needs_ocr | Scanned PDF, name only | Use M365 search or OCR the file |
| deferred_large | Over 5 MB, name only | Use M365 search or read the file directly |
| pending | Not yet read | Use M365 search |
| dup | Identical copy indexed elsewhere | Hits show the indexed copy; the same file exists in other folders |

The index is a snapshot: check `--status` for the last scan date. Anything changed after that date may be stale or missing, so confirm recent items (last few weeks) in M365 search or the file itself.

## Maintenance (only when asked, or when the index is clearly stale)
`build_index.py` in the same folder updates the index incrementally and can resume after interruption:
```
python3 build_index.py "<Business path>" business_fts.sqlite --scan            # new, changed or deleted files
python3 build_index.py "<Business path>" business_fts.sqlite --budget 140      # extract text; repeat until pending = 0
python3 build_index.py "<Business path>" business_fts.sqlite --large --budget 140
python3 build_index.py "<Business path>" business_fts.sqlite --ocr --budget 140
```
Rules:
- Build in a **local working copy** (e.g. `$HOME/fts/`), never inside the OneDrive folder.
- Copy the finished `.sqlite` back into `_Search Index`. Writes to the mount run at ~0.6 MB/s, so copy in resumable `dd` chunks (`iflag=skip_bytes oflag=seek_bytes conv=notrunc`), `cmp` the result, then rename it into place.
- In device_bash, keep each pass under ~150 s. Background processes do not survive between calls.
- Never delete files in the Business folder without Gabriel's explicit request.

## Report back
State which method found the answer (index, M365 search or direct read), cite file paths, and list anything that could not be confirmed.