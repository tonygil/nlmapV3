# BE Match Rate Campaign

**Target: 80% per unique URL** (authoritative view: Gap Analysis dashboard, not `save_output()` logs)

## Current State (19 Feb 2026, 10:53 run)

- Match rate: **58.4%** per unique URL / ~61% per row
- Mapped: 1,051 / 1,799 unique URLs · Unmapped: **748 unique URLs**
- 28 taxonomy topics still never matched
- Output: `C:/Users/Tony.Gilpin/Downloads/19thFeb/taxomony_match_BE_19_10_22thFeb_BE.xlsx`
- Gap analysis: `TAXONOMY_GAP_ANALYSIS_REPORT_19thFeb10_59.xlsx`

**Match rate counting:** Per-row logs = 2,518 rows (multi-product duplicates included). Gap Analysis = 1,799 unique URLs. Always use Gap Analysis as authoritative.

**What drove the jump 26% → 58%:**
- v3.25 critical bug fix: `_product_alias_map` bypassed in `find_topic_matches()` fast-path — "Adsolut boekhouden" articles got empty candidate list, silently unmapping ~641 rows
- v3.24: NaN product → wildcard, 40 synonyms, noise phrases
- 73-synonym patch: only +22 URLs (remaining unmapped are product-filtered or below threshold, not synonym gaps)

---

## Remaining Actions ⬜

| Fix | Files to edit | Est. URLs unlocked |
|-----|---------------|-------------------|
| Add `'artikel '` + stopword pairs (`'van een'`, `'bij het'`, `'van het'`, `'uit hoe'`) to `NOISE_PHRASE_STARTS` | `content_keyword_extractor.py` | ~80–120 |
| Add `Adsolut_KMO_beheer` → `"Adsolut boekhouding"` | `countries/BE/category_mapping.json` | ~60 |
| Exclude `Customers`, `Administration`, `Regular_services` (Salesforce CRM tags) | `category_mapping.json` | ~18 off denominator |
| Add `Accounting`, `ERP`, `Accon_*` to mapping | `countries/BE/category_mapping.json` | ~9 |
| Add OSS aangifte synonyms (`btw aangifte voor/van`, `personenbelasting een aangifte`) | `countries/BE/synonyms.json` | ~35–40 |
| Add Licenties / Account aanmaken / Klantenbeheer synonyms | `countries/BE/synonyms.json` | ~35–45 |
| **Total estimated** | | **~237–292 URLs** → ~72–74% |

After quick wins, use `unmapped_review.html` triage for the rest (~30–50 off denominator via Remove, +30–40 via Fix Product, +20–30 via Add Synonym) → **80%+ target**.

---

## Unmapped Breakdown (748 URLs)

Source: `taxomony_match_BE_19_10_22thFeb_BE.xlsx`

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
| dit artikel leest | 78 | "artikel *" variant not blocked |
| dit artikel vindt | 53 | "artikel *" variant not blocked |
| van een | 46 | stopword pair |
| bij het | 39 | stopword pair |
| raadpleeg dit artikel | 31 | partially blocked ("raadpleeg" alone blocked, not "raadpleeg dit") |
| dit artikel legt | 30 | "artikel *" variant |
| artikel biedt een | 29 | "artikel *" variant |
| artikel voor / wanneer / indien | 60+ | "artikel *" variants |

**Fix:** Add `'artikel '` (with trailing space) to `NOISE_PHRASE_STARTS` — one entry catches ALL "artikel *" noun-phrase variants. Existing entries only cover verb-forms. Also add: `'van een'`, `'bij het'`, `'van het'`, `'uit hoe'`.

**HIGH priority near-misses (75–79%, just below threshold):**

| Topic | Total Freq | Top Keywords |
|---|---|---|
| Artikelen | 61 | `artikel indien` (78%), `artikel willen` (78%), `artikel kunt` (76%) |
| OSS aangifte | 38 | `btw aangifte voor/van` (75%), `personenbelasting een aangifte` (75%) |
| Licenties | 21 | `van klanten` (75%), `voor meerdere klanten` (75%), `klanten gelijktijdig` (75%) |
| Account aanmaken | 19 | `kan aanmaken` (78.6%), `accon kunt aanpassen` (77.8%) |
| SODA bestanden | 6 | 2 keywords |
| Leveranciersbeheer | 6 | 2 keywords |
| Klantenbeheer | 4 | `kan beheerd` (75%) |
| CODA bestanden | 4 | `controle bestanden` (75%) |

Add via `synonym_review.html` or directly in `countries/BE/synonyms.json`.

### Root Cause 2: Product filter: nan (169 URLs)

NaN product treated as wildcard (v3.24) but keywords still don't match above threshold. Product families **not in BE taxonomy at all**:

| Family | Est. URLs | Fix |
|---|---|---|
| Superfisc Vennootschapsbelasting | ~29 | Add to taxonomy OR map to existing product |
| Wedde-administratie | ~20 | Add to taxonomy OR map to existing product |
| Release Notes (generic) | ~10 | Likely exclude — navigation pages |
| Beroepskosten zelfstandigen | ~5 | Add to taxonomy |
| Cloud AVD | ~4 | Add to taxonomy |

These won't be fixed by synonyms — the taxonomy product doesn't exist.

### Root Cause 3: Adsolut KMO-beheer (60 URLs)

`Adsolut_KMO_beheer` not in `countries/BE/category_mapping.json`. Fix:
```json
"Adsolut_KMO_beheer": "Adsolut boekhouding"
```

### Root Cause 4: Other product values (36 URLs)

| Product Value | URLs | Action |
|---|---|---|
| `Customers`, `Administration`, `Regular_services` | 7+7+4 | **Exclude** — Salesforce internal CRM tags, not content categories |
| `Accounting`, `ERP` | 2+2 | **Add to category_mapping.json** |
| `Fiscalc_Fiches`, `Fiscale_bijlage_PB`, `Fiscale_Simulaties` | 3+2+1 | **Add to taxonomy or category_mapping** |
| `Accon_Algemene_Vergadering`, `Accon_Publicaties` | 3+2 | **Add product aliases** in `synonyms.json` → `product_synonyms` |
| `Adsolut Personenbelasting`, `Adsolut Jaarrekening` | 3+2 | **Already in taxonomy** — check exact canonical name match |
| `Fiscaal dossier` | 3 | **In taxonomy** — check space vs underscore |
| `Roboto`, HTML garbage | 2 | **Data corruption** — exclude |
| `All`, `ongeacht de sector`, `Tutto`, `Kluwer_Office` | 4 | **Add to category_mapping.json** or exclude |

---

## Triage Tool Fix Loop

```
unmapped_review.html decisions:
  -> noise_additions      -> NOISE_PHRASE_STARTS in content_keyword_extractor.py -> re-run
  -> category_fixes       -> countries/BE/category_mapping.json -> re-run
  -> synonym_patch        -> python apply_synonym_patch.py -i patch.json -> re-run
  -> unmapped_exclusions  -> python apply_url_exclusions.py -i exclusions.json -> filtered semantic -> re-run
```

---

## Artikelen Topic Disambiguation — PARTIALLY RESOLVED

"Artikelen" is both a real taxonomy topic (KB article management feature) AND a noise source — every Salesforce community page has "artikel*" phrases in extracted text.

**Three contexts:**
1. URL scaffold (`/s/article/`) → filtered by `_URL_NAV_STOPWORDS` (v3.18) ✅
2. Navigation noise (Dutch UI action phrases) → `NOISE_PHRASE_STARTS` (v3.19) ✅
3. Real content (Artikelenbeheer feature docs) → should match ✅

**Remaining steps:**
- Re-run BE match, verify near-miss count drops from 614 to <50
- Optional: add compound synonyms to `countries/BE/synonyms.json`: `"artikel aanmaken"`, `"artikel publiceren"`, `"artikel importeren"`, `"artikelenbeheer"`
- Diagnostic: generic Title ("Artikelen", "Alle artikelen") = nav page; specific Title ("Een artikel aanmaken in Adsolut") = real content

---

## Historical Progress

| Date | Event | Rate |
|---|---|---|
| 18 Feb baseline | Almost no synonyms | 24% |
| 18 Feb | Product mapping fixes (v3.23/v3.24) | 26% |
| 19 Feb | Product alias bug fixed (v3.25) | **58.4%** |
| 19 Feb | 73-synonym patch applied | +22 URLs |
| Target | Noise + category_mapping + synonym fixes | **80%** |

## Completed ✅

- `dit artikel` / `raadpleeg` noise phrases → `NOISE_PHRASE_STARTS` (v3.24)
- 40 synonyms for top 8 topics (v3.24)
- NaN product → wildcard (v3.24)
- Adsolut boekhouden alias bug fixed (v3.25) ← **the big one**
- 73 synonyms applied via `synonym_patch_BE_2026-02-19.json`
- Unmapped breakdown researched (this document)
- `unmapped_review.html` triage tool built (v3.26) — Suggested_Product shown in blue 💡, Fix Product panel pre-filled
- `synonym_review.html` standalone browser tool
- `TAXONOMY_TOOLS_GUIDE.html` 4-part stakeholder guide (BE/NL/SE via `generate_country_guides.py`)
