# BE Match Rate Campaign

**Target: 80% per unique URL** (authoritative view: Gap Analysis dashboard, not save_output() logs)

## Current State (20 Feb 2026, 11:58 run) ← LATEST

- Match rate: **68.1%** per unique URL
- Mapped: 1,210 / 1,777 unique URLs
- Unmapped: **567 unique URLs** — 27 taxonomy topics never matched
- Topics covered: 103 / 130 (79%)
- Output: `TAXONOMY_GAP_ANALYSIS_REPORT_20thFeb_11_58.xlsx`
- To reach 80%: need **212 more URLs** mapped (target: 1,422 / 1,777)

**What drove 58.4% → 68.1% (+9.7pp):**
- v3.27 bug fix: NaN/empty semantic product not treated as wildcard in fast-path — articles with no Salesforce product category were only matched against empty-product taxonomy entries instead of all topics. 325 product-filtered rows → 118 remaining.

## Previous State (19 Feb 2026, 10:53 run)

- Match rate: **58.4%** per unique URL / ~61% per row
- Mapped: 1,051 / 1,799 unique URLs
- Unmapped: **748 unique URLs** — 28 taxonomy topics never matched

**What drove the jump 26% → 58%:**
- v3.25 critical bug fix: `_product_alias_map` was bypassed in `find_topic_matches()` fast-path — “Adsolut boekhouden” articles got empty candidate list, silently unmapping ~641 rows
- v3.24: NaN product → wildcard, 40 synonyms, noise phrases
- 73-synonym patch: only +22 URLs (remaining unmapped are product-filtered or below threshold, not synonym gaps)

---

## Remaining Actions ⬜

| Fix | Files to edit | Est. URLs unlocked |
|-----|-------|-----------|
| Add `'artikel '` + stopword pairs (`'van een'`, `'bij het'`, `'van het'`, `'uit hoe'`) to `NOISE_PHRASE_STARTS` | `content_keyword_extractor.py` | ~80–120 |
| Add `Adsolut_KMO_beheer` → `"Adsolut boekhouding"` | `countries/BE/category_mapping.json` | ~60 |
| Exclude `Customers`, `Administration`, `Regular_services` (Salesforce CRM tags) | `category_mapping.json` | ~18 off denominator |
| Add `Accounting`, `ERP`, `Accon_*` to mapping | `countries/BE/category_mapping.json` | ~9 |
| Add OSS aangifte synonyms (`btw aangifte voor/van`, `personenbelasting een aangifte`) | `countries/BE/synonyms.json` | ~35–40 |
| Add Licenties / Account aanmaken / Klantenbeheer synonyms | `countries/BE/synonyms.json` | ~35–45 |
| **Total estimated** | | **~237–292 URLs** → ~72–74% |

After quick wins, use `unmapped_review.html` triage for remaining (~30–50 off denominator via Remove, +30–40 via Fix Product, +20–30 via Add Synonym) → **80%+ target**.

---

## Unmapped Breakdown (748 URLs)

Source file: `taxomony_match_BE_19_10_22thFeb_BE.xlsx`

| Root Cause | Unique URLs | % of Unmapped | Fix Type |
|---|---|---|---|
| No matches above 80% threshold | 440 | 59% | Noise filter + synonyms |
| Product filter: nan | 169 | 23% | Missing category_mapping entries |
| Product filter: Adsolut KMO-beheer | 60 | 8% | Not in category_mapping.json |
| Product filter: other (17 product values) | 36 | 5% | Mix |
| Product filter: Adsolut boekhouden | 36 | 5% | Alias resolves but topics still below threshold |
| Product filter: ExpertM | 13 | 2% | Keywords below threshold |
| No keywords extracted | 1 | <1% | Data corruption (HTML in URL field) |

### Root Cause 1: No matches above threshold (440 URLs)

Top unmatched keywords — boilerplate noise not yet in `NOISE_PHRASE_STARTS`:

| Keyword | URLs | Pattern |
|---|---|---|
| dit artikel leest | 78 | “artikel *” variant not blocked |
| dit artikel vindt | 53 | “artikel *” variant not blocked |
| van een | 46 | stopword pair |
| bij het | 39 | stopword pair |
| raadpleeg dit artikel | 31 | partially blocked (“raadpleeg” alone blocked, “raadpleeg dit” not) |
| dit artikel legt | 30 | “artikel *” variant |
| artikel biedt een | 29 | “artikel *” variant |
| artikel voor / wanneer / indien | 60+ | “artikel *” variants |

**Fix:** Add `'artikel '` (with trailing space) to `NOISE_PHRASE_STARTS` — one entry catches ALL “artikel *” noun-phrase variants. Existing entries only cover verb-forms. Also add: `'van een'`, `'bij het'`, `'van het'`, `'uit hoe'`.

**HIGH priority near-misses (75–79%, just below threshold):**

| Topic | Total Freq | Top Keywords |
|---|---|---|
| Artikelen | 61 | `artikel indien` (78%), `artikel willen` (78%), `artikel kunt` (76%), `article` (75%) |
| OSS aangifte | 38 | `btw aangifte voor/van` (75%), `personenbelasting een aangifte` (75%) |
| Licenties | 21 | `van klanten` (75%), `voor meerdere klanten` (75%), `klanten gelijktijdig` (75%) |
| Account aanmaken | 19 | `kan aanmaken` (78.6%), `accon kunt aanpassen` (77.8%) |
| SODA bestanden | 6 | 2 keywords |
| Leveranciersbeheer | 6 | 2 keywords |
| Klantenbeheer | 4 | `kan beheerd` (75%) |
| CODA bestanden | 4 | `controle bestanden` (75%) |

Add these via `synonym_review.html` or directly in `countries/BE/synonyms.json`.

### Root Cause 2: Product filter: nan (169 URLs)

NaN product treated as wildcard (v3.24) but keywords don't match any topic above threshold. Product families **not in BE taxonomy at all**:

| Family | Est. URLs | Fix |
|---|---|---|
| Superfisc Vennootschapsbelasting | ~29 | Add to taxonomy OR map to existing product |
| Wedde-administratie | ~20 | Add to taxonomy OR map to existing product |
| Release Notes (generic) | ~10 | Likely exclude — navigation pages |
| Beroepskosten zelfstandigen | ~5 | Add to taxonomy |
| Cloud AVD | ~4 | Add to taxonomy |

These won't be fixed by synonyms — the taxonomy product doesn't exist.

