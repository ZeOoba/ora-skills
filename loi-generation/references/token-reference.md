# loi-generation — TOKEN REFERENCE (canonical list)

Moved out of `SKILL.md` on 2026-09-22 (body split). Read before Phase 3 token resolution. The skill must resolve every token below before saving the file.

## TOKEN REFERENCE (canonical list)

These are the tokens that appear in the master template. The skill is responsible for resolving every one before saving the file.

### Date and money
| Token | Example | Source |
|---|---|---|
| `{{LOI_DATE}}` | `May 15, 2026` | Today's date (or user-specified) |
| `{{OFFER_EXPIRATION_DATE}}` | `May 22, 2026` | LOI_DATE + 7 calendar days, business-day-adjusted |
| `{{PURCHASE_PRICE_WORDS}}` | `One Million Four Hundred Thousand and 00/100` | User / OM offer |
| `{{PURCHASE_PRICE_NUMERIC}}` | `1,400,000.00` | Same |
| `{{EMD_WORDS}}` | `One Hundred Thousand and 00/100` | User or ORA standard |
| `{{EMD_NUMERIC}}` | `100,000.00` | Same |
| `{{EMD_DUE_DAYS_WORDS}}` | `two (2)` | Deposit due window after PSA execution — DEFAULT two (2) for all-cash certainty signaling; SINGLE SOURCE: feeds §1 AND any PSA-deferral mention. Root cause of the 470 McCormick §1-vs-§10 conflict |

### Time periods (all phrased as `[word] (digit)`)
| Token | Example |
|---|---|
| `{{STUDY_PERIOD_WORDS}}` | `thirty (30)` |
| `{{CLOSING_DAYS_WORDS}}` | `fifteen (15)` |
| `{{EXCLUSIVITY_DAYS_WORDS}}` | `sixty (60)` or `thirty (30)` |
| `{{PSA_DRAFT_DAYS_WORDS}}` | `ten (10) business` |
| `{{PSA_EXECUTE_DAYS_WORDS}}` | `fifteen (15) calendar` |

### Property
| Token | Example |
|---|---|
| `{{PROPERTY_STREET_ADDRESS}}` | `1333 Research Road` |
| `{{PROPERTY_CITY}}` | `Gahanna` |
| `{{PROPERTY_STATE_FULL}}` | `Ohio` |
| `{{PROPERTY_STATE_ABBR}}` | `OH` |
| `{{PROPERTY_ZIP}}` | `43230` |
| `{{PROPERTY_COUNTY}}` | `Franklin County` |
| `{{PROPERTY_SF}}` | `19,018` |
| `{{PROPERTY_ACRES}}` | `2.46` |
| `{{PROPERTY_USE_TYPE}}` | `industrial` or `industrial / warehouse` or `flex` |
| `{{PROPERTY_TENANCY_PHRASE}}` | `vacant` / `single-tenant` / `multi-tenant` |
| `{{PROPERTY_ZONING_PHRASE}}` | `zoned M2 Manufacturing` — VERBATIM from the OM/listing. Body sentence reads "...acres of land {{PROPERTY_ZONING_PHRASE}}", so the value should read naturally after "land" (e.g. `zoned M2 Manufacturing`, `zoned CC`). Never invent a designation not in the marketing materials or a verified GIS pull — if unknown, ask rather than defaulting to a generic phrase. |
| `{{ENTITY_INTEREST_TYPE}}` | `membership interests` / `equity interests` / `partnership interests` per Decision Rule 0 |
| `{{PROPERTY_JURISDICTION_PHRASE}}` | `the City of Gahanna and Franklin County` |
| `{{KNOWN_CONDITION_CARVEOUT}}` | `(except for the roof, which the parties acknowledge is approximately twenty-one (21) years old and approaching the end of its useful life)` or empty |

### Seller / broker
| Token | Example |
|---|---|
| `{{SELLER_ENTITY_NAME}}` | `BUCKEYE ELM HOLDINGS CO LLC` (preserve original capitalization) |
| `{{SELLER_BROKER_FULL_NAME}}` | `David Ludwig` |
| `{{SELLER_BROKER_FIRM}}` | `Coldwell Banker, Ludwig Real Estate Group` |
| `{{SELLER_BROKER_ADDRESS_1}}` | `8800 Lyra Drive, Suite 600` |
| `{{SELLER_BROKER_ADDRESS_2}}` | `Columbus, Ohio 43240` |
| `{{SELLER_BROKER_SALUTATION}}` | `David` |

### Tenant (only if conditional §8 / §10 fires)
| Token | Example |
|---|---|
| `{{TENANT_NAME}}` | `Buckeye Elm Contracting, LLC` |
| `{{TENANT_DISCLOSURE_PHRASE}}` | Arm's-length: `, leased to Buckeye Elm Contracting, LLC (the "Tenant")`. Affiliated: `, leased to Buckeye Elm Contracting, LLC, an affiliate of Seller`. Never end in a trailing comma — a period follows immediately in the template. |

### Buyer signatory
| Token | Example |
|---|---|
| `{{BUYER_SIGNATORY_NAME}}` | `Gabriel Goldberg` |
| `{{BUYER_SIGNATORY_TITLE}}` | `Authorized Representative` |
