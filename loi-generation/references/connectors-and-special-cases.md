# loi-generation — connectors and special cases

Moved out of `SKILL.md` on 2026-09-22 (body split). Read before Phase 2 when the deal is multi-tenant, vacant, in a state outside the seven-state overlay list, a sale-leaseback, or the seller refuses long proration.

## CONNECTORS USED

## CONNECTORS USED

| Connector | Tool | Purpose |
|---|---|---|
| Notion | `notion-search`, `notion-fetch`, `notion-update-page` | Pull Acquisition Pipeline Tracker, Deal Sourcing Log, Tenant DB |
| HubSpot | `search_crm_objects`, `get_crm_objects` | Pull broker contact details from Broker Relationships |
| Outlook (COM) | `send-via-outlook.ps1` via Desktop Commander `start_process` | Ship mode send after explicit approval (Composio `OUTLOOK_*` retired 2026-06-11) |
| Workspace bash | `python3` with `python-docx` | Document assembly |
| Workspace bash | `soffice` headless | PDF generation |
| Cowork | `present_files` | Deliver outputs |

## SPECIAL CASES

## SPECIAL CASES

### Multi-tenant property
- `{{PROPERTY_TENANCY_PHRASE}}` = `multi-tenant`
- `{{TENANT_DISCLOSURE_PHRASE}}` = `` (empty) OR include short phrase referencing largest tenants
- Conditional §8 (Affiliated Tenant) typically DOES NOT fire (multi-tenant rarely all-affiliated)
- Conditional §9 (Estoppel) — modify to "Seller will cause each Tenant occupying more than [SF threshold] to deliver an estoppel"
- Conditional §11 (Lease Modification) fires; flag in chat that this should be PSA-strengthened with portfolio-wide restrictions

### Vacant property
- All four conditionals DELETE
- `{{TENANT_DISCLOSURE_PHRASE}}` = empty string (resulting opening reads "... acres of land {{PROPERTY_ZONING_PHRASE}}.")
- §4 may include vacant-building maintenance covenant (heat/sprinkler) — the master template already contains this in §7 bullets

### Property in unfamiliar state (not in seven-state overlay list)
- Flag `[FORECAST]` in chat
- Draft generic §6 language with placeholder reading "[STATE]: confirm customary proration method and transfer-tax allocation with local counsel before transmission"
- Do not ship without user verification

### Sale-leaseback indicated
- Tenancy = affiliated single-tenant
- All four conditionals fire
- Add `[SPECULATIVE]` flag in chat: sale-leaseback financing structures often warrant stronger §11 lease-modification restrictions including capped concessions
- Recommend lengthening Study Period to 45 days to allow tenant credit underwriting

### Seller refuses long proration (rare)
- Cite ORC § 5709.01 et seq. and Franklin County Bar custom in pushback memo
- Fall-back: short proration with Seller credit for prior year unpaid taxes (preserve buyer-protective substance)
