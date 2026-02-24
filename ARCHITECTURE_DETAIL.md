# Architecture Detail

Deep dives into performance, deprecated features, and secondary matchers.
See main `CLAUDE.md` for the primary architecture reference.

---

## Performance Optimizations

The core matching engine uses several optimizations:

**Phase 1 (Foundation):**
1. **rapidfuzz instead of fuzzywuzzy** — ~50x faster fuzzy matching (API compatible)
2. **LRU cache for synonym expansion** — `_expand_keyword_cached()` with 10,000 entry cache
3. **Pre-computed taxonomy structures:**
   - `topic_lower` pre-lowercased in `taxonomy_lookup`
   - `_product_url_forms` for fast product extraction from URLs
   - `_product_lookup` dict for O(1) product filtering
   - `_synonyms_tuple` hashable version for cache compatibility

**Phase 2 (Bottleneck Fixes):**
4. **Product filter before loop** — `find_topic_matches()` filters to product subset BEFORE fuzzy loop, reducing comparisons by 50-80% when product is known
5. **URL keyword extraction cache** — `_url_keywords_cache` dict prevents redundant URL parsing during consolidation
6. **O(1) domain/segment lookup** — `_product_topic_lookup[(product, topic)]` replaces linear scan when reassigning "Something Else" topics
7. **Pre-compiled regex** — `_SEPARATOR_PATTERN` replaces 10-iteration string replace loop in content keyword extraction

**Key cached function:**
```python
@lru_cache(maxsize=10000)
def _expand_keyword_cached(keyword_lower: str, synonyms_tuple: tuple) -> tuple:
    # Module-level cached synonym expansion
```

---

## Excel Data Sanitization

When writing Excel files, use `sanitize_dataframe()` to prevent corruption:
```python
from generate_topic_recommendations import sanitize_dataframe

# Sanitizes before writing - removes control chars, truncates long strings
sanitize_dataframe(df).to_excel(writer, sheet_name='Sheet1', index=False)
```

Fixes the "we found a problem with some content" Excel error by:
- Removing control characters (null bytes, bell, etc.)
- Truncating strings >32000 chars
- Removing problematic Unicode (surrogate pairs)
- Converting None/NaN to empty strings

---

## Strict Content Matcher — HIDDEN (v3.12+)

**Status:** ⚠️ Button commented out in GUI (lines 775-788 of `taxonomy_matcher_gui.py`)

**Why hidden:**
- Poor quality output: 90% noise (generic words like "Customers", "Article")
- HTML contamination: 57% of topics contain HTML tags (e.g., `<b><u>vraag<`, `<img Src=`)
- Product identification failure: uses article titles instead of product names
- Better alternative: Use NLUrl crawler keywords (0% noise, clean extraction)

**To re-enable (if ever needed):** Uncomment lines 775-788 in `taxonomy_matcher_gui.py`

**CLI (still works):**
```bash
python strict_content_matcher.py -c GB --debug --max-rows 10
python strict_content_matcher.py -c GB --semantic-file input.xlsx -o output.xlsx
```

**What it does:** Generates topics purely from page content (Title, Summary, Description, URL path) with NO taxonomy file dependency. Up to 3 ranked rows per URL, 6 topics each.

**Key differences vs main matcher:**

| | Main Matcher | Strict Content Matcher |
|---|---|---|
| Input | Keyword 1-12 + taxonomy file | Semantic file ONLY |
| Synonyms | Yes (bidirectional) | No |
| Domain/Segment | From taxonomy file | Classified from fixed keyword lists |
| Output | One row per URL-Segment | Up to 3 ranked rows per URL |
| UNMAPPED | Common | Rare (only if all content columns empty) |

**Fixed Domain set:** Accounting, Client Communication, General, Practice Administration, Taxation, Welcome

**Country data files used:** `countries/{CODE}/domains.json` (keyword→domain) and `countries/{CODE}/segments.json` (keyword→segment). These are NOT used by the main taxonomy matcher.

**Key methods:**

| Method | Purpose |
|--------|---------|
| `_clean_title_to_topic()` | Strip action prefixes, product names, trailing noise from title |
| `_extract_url_topics()` | Parse URL path segments into topics |
| `_extract_topic_phrases()` | Clause-aware phrase extraction from text |
| `extract_content_topics()` | Combines title + URL + content sources |
| `_classify_domain()` | Keyword-based domain classification |
| `_classify_segments()` | Returns top 3 segments by keyword score |
| `consolidate_results()` | Splits topics into ranked rows (6 per row, up to 3 ranks) |

**Output filename:** `strict_match_{CODE}.xlsx`

---

## Content-Based Topic Matcher

`content_topic_matcher.py` — analyzes URL content (Title, Description, Summary) to find relevant taxonomy topics independently of keyword matching.

**Use case:** Compare original taxonomy matches with what topics the content actually suggests — identifies mismatches and missing topic coverage.

```bash
python content_topic_matcher.py
# Edit MATCH_FILE, TAXONOMY_FILE, OUTPUT_FILE at top of file
```

**Output columns:**
- `Row_Type` — "Original" (from taxonomy match) or "Content-Based" (new segment rows)
- `Original_Topic_1-5` — topics from original taxonomy matching
- `Content_Topic_1-5` — topics found by analyzing content
- `Content_Segment_1-3` — segments derived from content analysis
- `Topics_Match` — whether original and content-based topics agree

**Key method:** `find_topics_in_content()` — extracts keywords from Summary/Description, fuzzy matches against taxonomy topics.

---

## Strict Content Match vs Taxonomy Matcher Analysis (9 Feb 2026)

Historical comparison reports generated Feb 2026 (stored externally):
- `C:\Users\Tony.Gilpin\Downloads\8thFeb\Strict_Content_Match_Executive_Summary.html` — 12 interactive charts
- `C:\Users\Tony.Gilpin\Downloads\8thFeb\Taxonomy_Side_by_Side_Comparison.html` — product-by-product comparison

**Key findings:**
- Coverage: Strict Match 100% vs Taxonomy Matcher 99.6% (2,648 URLs)
- Topic richness: 5.8 topics/URL (Strict) vs 1.3 (Taxonomy) = 4.5x more
- Taxonomy gaps: 89 of 294 topics (30.3%) never matched any URL
- HTML contamination: Strict Match 57% vs Taxonomy 0%
- Generic noise: Strict Match 90%+ vs Taxonomy 0%

**Conclusion:** Strict Match output is not usable for taxonomy. Use NLUrl crawler keywords for BE/NL/SE; use vmcrawl + taxonomy matcher for GB.

**Strict match mode ranking (best to worst for coverage):**
1. All Options (Title+URL+Content+Crawl) — 100% coverage, 5.8 topics/URL
2. No Crawl (Title+URL+Content) — 100% coverage, 5.5 topics/URL
3. Crawl Only — 98.3% coverage, 5.3 topics/URL
4. Summary/Description Only — 93.7% coverage, 4.6 topics/URL

---

## Critical Bug Fixes Reference

| Bug | Fix Location | Impact |
|-----|--------------|--------|
| Product filter too strict | `should_match_product()` | 64%→95%+ match rate |
| One-way synonym matching | `expand_with_synonyms()` | 45%→60% match rate |
| Substring false positives | Changed to `fuzz.ratio()` | Reduced irrelevant matches |
| Single-word synonym explosion | `_is_word_match()` word boundary rules | "data" no longer matches 14 topics |
| Summary single-word noise | `extract_summary_terms()` phrases only | "guide", "management" no longer hijack results |
| Cross-product exact match | `find_topic_matches()` product filter | "automation" no longer pulls in wrong-product topics |
| Synonym Editor delete fails | `exportselection=False` on Listbox widgets | Delete/edit buttons work |
| Excel "found a problem" error | `sanitize_dataframe()` in report generation | Clean Excel output |
| URL numeric prefixes in keywords | `extract_from_url()` strips leading digits | "15journals" → "journals" |
| CamelCase URLs not split | `_CAMELCASE_PATTERN` regex in extraction | "ChartOfAccounts" → "chart accounts" |
| Double-encoded URLs | `unquote(unquote(url))` in extraction | "%252B" decoded correctly |
| HTML entities in keywords | `_clean_text()` decodes entities + stopwords | "nbsp", "amp" no longer in keywords |
| BE alias product bypass (v3.25) | `find_topic_matches()` pre-filter | ~641 BE articles unmapped → fixed |
