# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

**Companion files** (read on demand — not auto-loaded):
- `CAMPAIGN_BE.md` — BE 80% campaign: full unmapped breakdown, root causes, fix tables
- `FEATURES_GUIDE.md` — Keyword Recommendations sheet, Reports, Synonym Assistant, Debug Mode, Gap Analysis Report
- `ARCHITECTURE_DETAIL.md` — Performance optimizations, Strict Content Matcher (deprecated), Content-Based Topic Matcher
- `SALESFORCE_WORKFLOW.md` — Salesforce CSV workflow (Method A/B), Data_Categories__c, community URLs, NLUrl internals

---

## Future Investigation

### Mapping Matcher Advisor Agent 💡 IDEA

The current improvement process is highly iterative and manual:
1. Run matcher → check match rate → identify unmapped reasons → edit synonyms/category_mapping/noise phrases → re-run → repeat

This would benefit from an **AI advisor agent** that guides the user through the full optimisation loop automatically.

**What it would do:**
- Ingest the gap analysis report + unmapped output file
- Diagnose unmapped reasons by category (product filter / no match / no keywords / noise)
- Prioritise fixes by estimated URL yield (biggest wins first)
- Suggest specific edits: exact synonym pairs, category_mapping entries, noise phrases
- Validate suggestions against article content (Summary/Description) before proposing
- Apply fixes (patch files) and trigger a re-run, then report delta
- Repeat until target match rate reached or no further gains possible

**Key inputs the agent would need:**
- `taxonomy_match_{CC}.xlsx` (Results sheet — unmapped rows)
- `TAXONOMY_GAP_ANALYSIS_REPORT_{CC}.xlsx` (near-misses, never-matched topics)
- `countries/{CC}/synonyms.json`, `category_mapping.json`
- `taxonomy.xlsx` (full topic list)
- Target match rate (e.g. 80%)

**Key tools the agent would use:**
- `apply_synonym_patch.py` — apply synonym changes
- `apply_url_exclusions.py` — remove noise URLs from denominator
- `unmapped_review.html` exports — category fixes, synonym patches, noise phrases
- Gap Analysis report generation

**Design considerations:**
- Should work per-country (BE, GB, NL, SE have different languages/taxonomies)
- Needs to distinguish between fixable unmapped (synonyms, product mapping) and genuinely unmappable (off-topic content)
- Could run as a Claude Code sub-agent or as a standalone CLI tool
- The iterative human-in-the-loop aspect (confirming suggestions) is important — agent should show evidence before applying

---

## Active Issues

### BE Match Rate Campaign 🔄 IN PROGRESS (target: 80%)

**Current state** (20 Feb 2026, run 11:58): **68.1%** per unique URL · 1,210 / 1,777 mapped · 567 unmapped · need 212 more for 80%

**Remaining ⬜ actions:**
- ⬜ Add `Adsolut_KMO_beheer` → `"Adsolut boekhouding"` in `countries/BE/category_mapping.json` (~60 URLs, 118 product issues remain)
- ⬜ Exclude Salesforce CRM tags (`Customers`, `Administration`, `Regular_services`) from category_mapping (~18 off denominator)
- ⬜ Add `'artikel '` + stopword pairs (`'van een'`, `'bij het'`, `'van het'`) to `NOISE_PHRASE_STARTS` in `content_keyword_extractor.py` (~80–120 URLs)
- ⬜ Add OSS aangifte / Licenties / Account aanmaken synonyms to `countries/BE/synonyms.json` (~70 URLs)
- ⬜ Run `unmapped_review.html` triage for remaining unmapped

Full breakdown and fix tables: `CAMPAIGN_BE.md`

### Artikelen disambiguation ⚠️ PARTIALLY RESOLVED
Navigation noise fix applied (v3.19). Re-run needed to verify near-miss count drops from 614 to <50. Optional: add compound synonyms (`artikelenbeheer`, `artikel aanmaken`) to `countries/BE/synonyms.json`. Details: `CAMPAIGN_BE.md`.

---

## Quick Reference (Critical Facts)

⚠️ **MUST KNOW before modifying code:**
1. **Product column handling:**
   - Salesforce CSV Import: Product extracted from Data_Categories__c and used for multi-product matching
   - Regular semantic files: Product column ignored during matching
   - Output Product/Domain/Segment always come from taxonomy matches
2. **Output is always consolidated** — one row per URL-Segment with Topic_1, Topic_2, etc. columns
3. **No auto-segment addition** — only topics from taxonomy file appear in output
4. **Topics are never created** — all topics must exist in taxonomy Topic columns
5. **Synonyms affect matching** — control which topics match by editing `countries/{CODE}/synonyms.json`
6. **Hybrid relevance** — Top_Relevance uses BOTH similarity score AND URL content analysis
7. **rapidfuzz is used** — NOT fuzzywuzzy (50x faster, API compatible)
8. **ContentKeywordExtractor deduplicates by URL** — Unless Product column exists (v3.13 fix)
9. **Data_Categories__c enables multi-product matching** — One article can match multiple products via row expansion
10. **Source-aware matching (v3.15)** — Title keywords use lower threshold (max(70, threshold-10)); URL keywords get "Low Trust" at 80-84%; requires `Source N` columns in semantic file
11. **URL nav words suppressed from URL extraction (v3.18)** — `_URL_NAV_STOPWORDS` / `URL_NAV_STOPWORDS` filter Salesforce community path scaffolding; does NOT affect content column extraction
12. **Content boilerplate filtered before matching** — `NOISE_PHRASE_STARTS` in `content_keyword_extractor.py` removes CMS action language and Dutch UI chrome phrases before fuzzy matching
13. **Match rate is counted two ways** — `save_output()` logs = per-row (includes multi-product duplicates). Gap Analysis dashboard = per-unique-URL. For BE these differ by ~3pp. Always use Gap Analysis as authoritative.
14. **`product_synonyms` JSON structure** — stored as `{canonical_product: [alias1, alias2]}` in `synonyms.json`. At runtime reversed into `_product_alias_map = {alias.lower(): canonical}` for O(1) lookup.
15. **Synonym backups created automatically** — `apply_synonym_patch.py` writes `countries/{CODE}/synonyms_backup_YYYYMMDD_HHMMSS.json` before each patch.

---

## Project Overview

**NL Taxonomy Mapper V3** maps URLs from semantic carriers to taxonomy topics using fuzzy string matching. Multi-country support (NL, SE, BE, GB) with language-specific synonyms and external configuration.

**Core Purpose:** Maps keywords (Keyword 1-12 + optional Summary) to hierarchical taxonomy (Product → Domain → Segment → Topic) using fuzzy matching with auto-deduplication.

---

## Development Commands

```bash
# Setup
pip install -r requirements.txt
# Required: pandas, openpyxl, rapidfuzz, PyYAML
# Optional (for URL crawling): pip install trafilatura requests

# Run GUI
python taxonomy_matcher_gui.py
# Or: launch_gui.bat  (Python discovery: venv/Scripts/python.exe -> python -> py launcher -> C:\Python314/312/311 -> %LOCALAPPDATA%\Programs\Python\Python314/312/311)

# Run CLI
python taxonomy_matcher.py -c GB -t 80
# CLI args: -c COUNTRY, -t THRESHOLD, --semantic-file, --taxonomy-file, -o OUTPUT, --use-summary, --debug, --max-rows, --url-filter

# Build exe
build.bat
```

---

## Versioning

**IMPORTANT:** Update version when making changes to the application.

Edit the top of `taxonomy_matcher_gui.py`:
```python
VERSION = "3.28"           # Increment for each release
VERSION_DATE = "2026-02-20"    # Update to release date
VERSION_NOTES = "Short description of change"
```

The version displays in the window title and About tab.

---

## Version History (Last 10)

| Version | Date | Key Changes |
|---------|------|-------------|
| 3.28 | 2026-02-20 | Remove `post_processor.py`; URL Pattern Filter now runs directly in GUI (anchor strip + URL pattern removal only, no rank trim side effects). |
| 3.27 | 2026-02-20 | Fix NaN/empty semantic product treated as wildcard in fast-path. |
| 3.26 | 2026-02-19 | `Suggested_Product` column on "Product filter excluded" unmapped rows — best-scoring unfiltered topic's product. `unmapped_review.html` Fix Product panel pre-populated from this value. |
| 3.25 | 2026-02-19 | **Critical BE fix**: `_product_alias_map` bypassed in `find_topic_matches()` fast-path — aliases like "Adsolut boekhouden" returned `[]`, silently unmapping ~641 articles. Fix: resolve alias before `_product_lookup` call. |
| 3.24 | 2026-02-18 | Empty/NaN product treated as wildcard; `'dit artikel'`, `'raadpleeg'`, `'van artikelen'`, `'een overzicht van'` added to `NOISE_PHRASE_STARTS`; 40 synonyms added to BE. |
| 3.23 | 2026-02-18 | `product_synonyms` in `synonyms.json`; `_product_alias_map` O(1) lookup; BE `category_mapping.json` typo fixed (841 rows unblocked). |
| 3.22 | 2026-02-18 | `NOISE_PHRASE_STARTS` also applied in `extract_summary_terms()` — Dutch UI phrases were leaking via Summary column. |
| 3.21 | 2026-02-18 | Top results per URL default 3→6; `save_output()` logs 4-step progress `[1/4]`–`[4/4]`. |
| 3.20 | 2026-02-18 | Gap Report: synonym thresholds now relative to main threshold; Progress sheet added (`gap_analysis_progress.json`). |
| 3.19 | 2026-02-18 | Synonym Assistant aligned with matcher threshold; `fuzzywuzzy` → `rapidfuzz` in 4 report functions. |
| 3.18 | 2026-02-17 | `_URL_NAV_STOPWORDS` / `URL_NAV_STOPWORDS` suppress Salesforce community path words from URL keyword extraction. |
| 3.17 | 2026-02-17 | Keyword Recommendations sheet: Priority-first columns, colour coding, frozen header, all URLs shown (up to 10). |

**Current stable version:** 3.28 · ❌ Strict Match hidden (v3.12+) — poor output quality, use crawler keywords instead.

---

## Architecture

### Core Files

| File | Purpose |
|------|---------|
| `taxonomy_matcher.py` | Core matching engine, CLI, `TaxonomyMatcher` class (rapidfuzz + LRU caching) |
| `taxonomy_matcher_gui.py` | Tkinter GUI — Setup, Console, Synonym Editor, Synonym Assistant, Reports, About tabs. Strict Match hidden v3.12. |
| `content_keyword_extractor.py` | Extracts keywords from URL/Title/Summary/Description. Skips URL deduplication when Product column exists (v3.13). |
| `salesforce_csv_processor.py` | Processes Salesforce Knowledge CSV exports (482+ cols), extracts Data_Categories__c, converts Lightning URLs, expands multi-product rows |
| `convert_salesforce_urls.py` | Converts Lightning URLs to public community URLs, extracts URLs from HTML anchor tags |
| `strict_content_matcher.py` | ⚠️ HIDDEN — generates topics from page content, no taxonomy needed. Hidden v3.12 (90% noise). See `ARCHITECTURE_DETAIL.md` |
| `content_topic_matcher.py` | Compares taxonomy matches with content-derived topics. See `ARCHITECTURE_DETAIL.md` |
| `generate_topic_recommendations.py` | Topic gap analysis report (8 sheets). See `FEATURES_GUIDE.md` |
| `generate_taxonomy_gap_analysis.py` | Taxonomy gap analysis: phantom/never-matched topics, synonym recommendations (8 sheets). See `FEATURES_GUIDE.md` |
| `remove_top_level_pages.py` | Filters MindTouch "Topic Hierarchy" nav pages (GB only). See `FEATURES_GUIDE.md` |
| `country_config.py` | Loads config.yaml, resolves country-specific paths |
| `config.yaml` | Country registry & settings |
| `synonym_review.html` | Standalone browser tool — reads Keyword Recommendations sheet; exports `synonym_patch_{CC}_{date}.json` |
| `unmapped_review.html` | Standalone browser triage tool — reads Results sheet; 5 per-row actions (Noise/Product/Synonym/Remove/Skip); 4 export types |
| `apply_synonym_patch.py` | Merges `synonym_patch_*.json` into `countries/{CODE}/synonyms.json` with backup; `--dry-run` supported |
| `apply_url_exclusions.py` | Filters semantic Excel using `unmapped_exclusions_*.json`; writes `{stem}_filtered.xlsx`; `--dry-run` supported |
| `countries/{CODE}/synonyms.json` | Language-specific synonyms + `product_synonyms` section |
| `countries/{CODE}/category_mapping.json` | Maps Salesforce Data_Categories__c values to taxonomy products (v3.13) |
| `countries/{CODE}/domains.json` | Keyword→domain mapping for `strict_content_matcher.py` only — NOT used by main matcher |
| `countries/{CODE}/segments.json` | Keyword→segment mapping for `strict_content_matcher.py` only — NOT used by main matcher |

**Utilities:**

| Utility | Purpose | Usage |
|---------|---------|-------|
| `restructure_taxonomy.py` | Convert Product 1-N cols → single Product column | `python restructure_taxonomy.py -i input.xlsx` |
| `convert_salesforce_urls.py` | Test Lightning → public URL conversion | `python convert_salesforce_urls.py -i input.csv -c BE` |
| `salesforce_csv_processor.py` | Process SF CSV (CLI mode) | `python salesforce_csv_processor.py -i input.csv -o output.xlsx -c BE` |
| `synonym_validator.py` | Validate synonym JSON; coverage stats, cross-topic duplicates, similar keys | `python synonym_validator.py countries/BE/synonyms.json` |
| `link_extractor.py` | Extract hyperlinks from match output URLs; 6-sheet Excel. Edit `INPUT_FILE`/`OUTPUT_FILE` at top. | `python link_extractor.py` |
| `generate_country_guides.py` | Generate `TAXONOMY_TOOLS_GUIDE_{BE/NL/SE}.html` from base BE guide | `python generate_country_guides.py` |

### Key Methods (taxonomy_matcher.py)

| Method | Purpose |
|--------|---------|
| `expand_with_synonyms()` | Bidirectional synonym expansion |
| `should_match_product()` | Product filtering logic |
| `find_topic_matches(source=)` | Fuzzy matching with `fuzz.ratio()`. `source` param ('title'/'url'/'summary'/'description'/'unknown') adjusts threshold and relevance label (v3.15) |
| `extract_summary_terms()` | Extracts 2-3 word phrases from Summary column (no single words) |
| `extract_keywords()` | Returns `(keywords, sources)` tuple; reads `Source N` columns if present (v3.15) |
| `consolidate_results()` | Groups by URL-Segment, spreads topics to columns; `top_n` (default 6) limits rows per URL |
| `save_output()` | Writes Results + Keyword Recommendations sheets; 4-step progress logging (v3.21) |
| `extract_url_keywords()` | Parses URL path for relevance; filters `_URL_NAV_STOPWORDS` (v3.18) |
| `calculate_relevance(source=)` | Hybrid score + URL content analysis + source-aware label (v3.15) |
| `generate_keyword_recommendations()` | Builds `_recommendations_df` from `_keyword_near_misses` |
| `_format_recommendations_sheet()` | Applies openpyxl colour coding + frozen header to Keyword Recommendations sheet |

### Data Flow

```
1. Load config.yaml -> determine country -> load synonyms.json
2. Load semantic_carriers.xlsx and taxonomy.xlsx
3. Flatten taxonomy -> List[Dict] with {product, domain, segment, topic}
4. For each URL:
   - Extract Keyword 1-12 (Product column IGNORED for regular semantic files)
   - If --use-summary: extract 2-3 word phrases from Summary (not single words)
   - Expand keywords with synonyms (bidirectional, word boundary enforced)
   - Fuzzy match against all topics (threshold >=80)
   - Record matches with taxonomy Product/Domain/Segment
   - Deduplicate (URL, Product, Domain, Segment, Topic)
5. Consolidate: group by (URL, Product, Domain, Segment) -> Topic_1, Topic_2, etc.
6. Export: taxonomy_match_{CODE}.xlsx
```

### Key Architecture Patterns

**Synonym Expansion (Bidirectional with word boundary rules):**
- **Direction 1** (topic→synonyms): If keyword contains topic name as complete word(s) AND keyword >= topic length → add all synonyms. Example: `"security mapping"` contains topic `"Security"` → adds synonyms. But `"data"` does NOT expand via multi-word topic `"Data import"`.
- **Direction 2** (synonym→topic): If keyword exactly equals a synonym → add topic name. Multi-word keywords can match if synonym is a complete word in them. But `"data"` does NOT match synonym `"data validation"`.
- **Key function**: `_is_word_match(needle, haystack)` enforces word boundary checks
- **Key rule**: Single-word terms cannot match multi-word synonyms/topics (prevents generic word explosion)

**Product Filtering:**
1. Empty taxonomy Product → matches ANY semantic Product
2. Exact Product match → semantic = taxonomy
3. "Other" semantic Product → matches any taxonomy Product
4. Product aliases resolved via `_product_alias_map` before `_product_lookup` (v3.25)

**Exact Match Bypass — REMOVED in v3.14:** All topics now go through normal fuzzy threshold matching. Cannot rely on URL path for product.

**URL Nav Stopwords (v3.18):**
- `_URL_NAV_STOPWORDS` in `taxonomy_matcher.py` — applied in `extract_url_keywords()` (relevance scoring)
- `URL_NAV_STOPWORDS` in `content_keyword_extractor.py` — merged with `STOPWORDS` only inside `extract_from_url()`, NOT applied to content columns
- Contains: `artikelen`, `nlcommunity`, `customers`, `lightning`, `knowledge`, `wktaaeu`, `taasupport`, `wolterskluwer`, `userdocs`, plus generic nav words
- **To add new nav words: edit both constants (keep them in sync)**

**Noise Phrase Filter — `NOISE_PHRASE_STARTS` (content_keyword_extractor.py):**

Prefix blocklist applied during keyword extraction from **content columns only** (Title, Summary, Description). `_is_noise_phrase()` rejects a phrase if:
1. It starts with any entry in the list
2. Any individual word equals a single-word entry
3. More than half the words are stopwords
4. Only one meaningful (non-stop) word remains

Two categories of noise:
- Generic CMS gerunds: `'enabling'`, `'providing'`, `'managing'`, `'configuring'`, `'automatically'`
- Dutch Salesforce UI chrome: `'artikel vind'`, `'artikel lees'`, `'artikel legt'`, `'artikel leggen'`, `'alle artikelen'`, etc.

**To add noise phrases:** Edit `NOISE_PHRASE_STARTS` in `content_keyword_extractor.py` (~line 121). Use shortest unambiguous prefix — single-word entries filter regardless of word position. Does NOT affect URL path extraction (handled by `URL_NAV_STOPWORDS`).

**Source-Aware Matching (v3.15):**
- Title source: effective threshold = `max(70, threshold - 10)`, relevance boosted
- URL source: normal threshold, label "Low Trust" at 80-84%
- Summary/Description/unknown: normal threshold and relevance

**Hybrid Relevance:**

| Relevance | Criteria |
|-----------|----------|
| Best Match | Score ≥90% AND topic in URL |
| Highly Relevant | Score ≥85% AND topic in URL |
| Relevant | Score <85% BUT topic in URL |
| Somewhat Relevant | Score ≥90% but NOT in URL |
| Tangential | Score ≥85% but NOT in URL |
| Low Relevance | Score 80-84% and NOT in URL |
| Weak | Score <80% |
| Unmapped | No matches (score = 0) |

---

## Input/Output Specs

**semantic_carriers_list.xlsx (or crawler output):**
- Required: URL, Keyword 1-12 (with space)
- Optional: Summary (for `--use-summary` mode), Product, Title, Word Count, etc.

**taxonomy.xlsx:**
- Required: Product, Domain, Segment, Topic 1 through Topic N
- Topics detected dynamically via `col.startswith('Topic')`

**Output (taxonomy_match_{filename}_{CODE}.xlsx):**
- Columns: URL, Title, Description, Summary, Product, Domain, Segment, Topic_1...Topic_N, Top_Score, Top_Relevance, Unmapped_Reason, Suggested_Product, Unmatched_Keywords, Rank
- One row per URL-Segment combination
- `Suggested_Product`: populated only on "Product filter excluded" unmapped rows — the product of best-scoring unfiltered match (v3.26). Empty on all matched rows.
- `Unmatched_Keywords`: comma-separated keywords that didn't match above threshold

**Unmapped_Reason values:**
- `No keywords extracted from row` — Keyword 1-12 all empty
- `No matches above {threshold}% threshold` — Keywords exist but no fuzzy matches
- `Product filter excluded matches (semantic Product: X)` — Matches found but filtered by product

---

## Common Modifications

### Add New Country
```yaml
# config.yaml
countries:
  DE:
    name: "Germany"
    code: "DE"
    enabled: true
    files:
      semantic_carriers: "semantic_carriers_list.xlsx"
      taxonomy: "taxonomy.xlsx"
      synonyms: "synonyms.json"
    settings:
      similarity_threshold: 80
```
Then create `countries/DE/` with taxonomy.xlsx, synonyms.json (`{"synonyms": {}}`), category_mapping.json (`{}`).

### Add Synonyms
Edit `countries/{CODE}/synonyms.json`:
```json
{"synonyms": {"TopicName": ["synonym1", "synonym2"]}}
```
Or: GUI Synonym Editor tab → select topic → Bulk Import.
Or: `synonym_review.html` → select near-misses → export patch → `python apply_synonym_patch.py -i patch.json`

### Add Product Aliases
In `countries/{CODE}/synonyms.json` `product_synonyms` section — key = canonical taxonomy product name, values = aliases:
```json
{"product_synonyms": {"Adsolut boekhouding": ["Adsolut boekhouden"]}}
```

### Adjust Threshold
- config.yaml: `settings.similarity_threshold: 85`
- CLI: `-t 85`
- GUI: threshold slider

### Change Fuzzy Algorithm
In `find_topic_matches()`, `fuzz.ratio()` is used. Alternatives: `fuzz.partial_ratio()` (looser substring), `fuzz.token_sort_ratio()` (word-order independent), `fuzz.token_set_ratio()` (subset matches).

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Wrong Product in output | Product comes from taxonomy, not semantics. Use synonyms to control matches |
| Unexpected topics | Check taxonomy Topic columns — all topics come from there |
| 0 matches / swap error | Files swapped — click "Swap Files" or manually switch |
| Country not in dropdown | Check config.yaml: `enabled: true`, uppercase code, restart GUI |
| Slow processing | Ensure rapidfuzz installed: `pip install rapidfuzz` |
| Empty Topic columns | Segment names filtered from Topic columns (intentional) |
| Crawling disabled | Install trafilatura: `pip install trafilatura` |
| Match rate <30% | Check `Unmapped_Reason`: "Product filter excluded" → fix category_mapping; "No matches" → add synonyms; "No keywords" → content columns empty |
| Multi-product rows lost | Verify deduplication skip in `content_keyword_extractor.py` lines 701-714 |
| Product column garbage | Check temp file: if clean → ContentKeywordExtractor issue; if corrupt → salesforce_csv_processor issue |

For Salesforce-specific troubleshooting see `SALESFORCE_WORKFLOW.md`.

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
