# Belgium (BE) — Country Notes

## Current Match Rate Status

- **58.4%** per unique URL (1,051 / 1,799 mapped) — as of 19 Feb 2026
- Target: **80%**
- Full campaign details and fix plan: see `CAMPAIGN_BE.md` in project root

## Next Actions (priority order)

1. Add `'artikel '` to `NOISE_PHRASE_STARTS` in `content_keyword_extractor.py` (~80–120 URLs)
2. Add `Adsolut_KMO_beheer` → `"Adsolut boekhouding"` in `category_mapping.json` (~60 URLs)
3. Exclude Salesforce CRM tags (`Customers`, `Administration`, `Regular_services`) from `category_mapping.json`
4. Add OSS aangifte / Licenties / Account aanmaken synonyms to `synonyms.json`
5. Run `unmapped_review.html` for remaining triage

## Key Files

| File | Notes |
|------|-------|
| `synonyms.json` | 73+ synonyms applied as of 19 Feb. `product_synonyms` section has `"Adsolut boekhouding": ["Adsolut boekhouden"]` |
| `category_mapping.json` | Missing: `Adsolut_KMO_beheer`, `Accounting`, `ERP`. Exclude: `Customers`, `Administration`, `Regular_services` |
| `taxonomy.xlsx` | Standard BE taxonomy. Missing product families: Superfisc Vennootschapsbelasting, Wedde-administratie |

## Known category_mapping.json Gaps

| Salesforce value | Status | Fix |
|---|---|---|
| `Adsolut_KMO_beheer` | ❌ Missing | Add → `"Adsolut boekhouding"` |
| `Accounting` | ❌ Missing | Add → canonical product name |
| `ERP` | ❌ Missing | Add → canonical product name |
| `Customers` | ❌ Should exclude | Add to exclusion list (Salesforce CRM tag) |
| `Administration` | ❌ Should exclude | Add to exclusion list |
| `Regular_services` | ❌ Should exclude | Add to exclusion list |
| `Accon_Algemene_Vergadering` | ❌ Missing | Add as product alias in `synonyms.json` → `product_synonyms` |

## Community URL

`https://taasupport.wolterskluwer.be/customers/s/article`
