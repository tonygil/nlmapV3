# Features Guide

Detailed reference for GUI features, reports, and output formats.
See main `CLAUDE.md` for architecture and quick reference.

---

## Keyword Recommendations (Output Sheet)

The main taxonomy match output includes a second sheet "Keyword Recommendations" analysing every unmatched keyword.

**Data capture:** Near-miss data collected during `find_topic_matches()` via `track_near_misses=True`. Keywords scoring ≥50 but below threshold are tracked, along with product-filtered entries. Avoids re-running fuzzy matching post-hoc.

**Key instance variables:**
- `self._keyword_near_misses` (dict) — accumulated during `process_matching()`, keyed by keyword lowercase
- `self._recommendations_df` (DataFrame) — generated in `save_output()`, stored for GUI access

**Sheet columns (v3.17 — Priority first, colour coded):**

| Column | Description |
|--------|-------------|
| `Priority` | HIGH / MEDIUM / LOW — row colour: green / amber / gray |
| `Action` | "Add synonym" / "Review synonym" / "Consider synonym" / "Cross-product" / "New topic?" |
| `Keyword` | The unmatched keyword |
| `Frequency` | How many URLs had this unmatched keyword |
| `Topic` | Closest taxonomy topic by score |
| `Score` | The fuzzy score it achieved |
| `In_Synonyms` | Yes/No — already a synonym for the target topic |
| `Product` | Product the nearest topic belongs to |
| `Domain` | Domain the nearest topic belongs to |
| `Segment` | Segment the nearest topic belongs to |
| `Rejection_Reason` | "Below threshold (78% < 80%)" / "Product filtered" / "No close match (<50%)" |
| `Full_Recommendation` | Full recommendation text (verbose) |
| `URL_1` … `URL_N` | All stored sample URLs (up to 10) in blue, wrap-enabled |

**Priority classification:**

| Priority | Criteria |
|----------|----------|
| HIGH | Score >= (threshold - 5) AND frequency >= 3 |
| MEDIUM | Score >= (threshold - 15) AND frequency >= 2, OR product-filtered, OR frequency >= 5 with no close match |
| LOW | Score >= 50 |
| NOISE | Everything else (filtered from output) |

**Post-run review dialog (v3.16):** After matching, `_show_synonym_review_dialog()` opens automatically if HIGH/MEDIUM near-misses exist that aren't in synonyms.json. Per-row Approve/Dismiss treeview. "Show URLs" popup with up to 5 clickable URLs. Approve calls `_apply_synonyms_batch()`.

**Key methods:**
- `find_topic_matches(..., track_near_misses=True)` — returns `(matches, near_misses)` tuple
- `generate_keyword_recommendations()` — processes `_keyword_near_misses` into DataFrame (Priority-first layout)
- `_format_recommendations_sheet()` — applies Excel colour coding + frozen header
- `_show_synonym_review_dialog(rec_df, near_misses_dict, output_file)` — interactive post-run review
- `_apply_synonyms_batch(df)` — core batch insert into synonyms.json (also used by One-Click Apply)

---

## Reports Tab

Scrollable layout with compact cards for quick reports and a full-width Topic Recommendations section.

**Quick Reports (3-column layout):**

| Report | Button Color | Output |
|--------|--------------|--------|
| Proposed Synonyms | Blue | 5-sheet Excel with synonym suggestions |
| Match Quality | Purple | 5-sheet Excel with relevance analysis |
| Unmapped Reasons | Orange | 5-sheet Excel with failure diagnostics |

**Synonym Report sheets:**
1. All Proposed Synonyms (with Already_Added column)
2. HIGH Priority (score ≥85%, freq ≥50)
3. Summary by Topic
4. NEW Only (not in synonyms.json)
5. Unmapped Keywords

**Match Quality Report sheets:**
1. All Matches (with Rank_In_URL, Relevance)
2. Top N Per URL
3. Match Statistics
4. Low Confidence
5. Relevance Summary

**One-Click Apply (Proposed Synonyms):** After generating the report, dialog offers to apply HIGH priority NEW synonyms directly to synonyms.json, open in Excel, or skip.

Note: the **post-run review dialog** (`_show_synonym_review_dialog`, v3.16) is the primary synonym workflow — appears automatically after every match run with per-row approve/dismiss. Reports tab One-Click Apply is a secondary path.

---

## Synonym Assistant

Dedicated tab for reviewing and applying synonyms directly in the GUI (full-screen layout).

**File Inputs:**
- **Match File** (filtered output) — gap analysis: finds never-matched topics, suggests keywords from URLs
- **Semantic File** (optional) — keyword analysis: compares keywords against taxonomy topics
- **Taxonomy File** (required) — taxonomy to analyze against

**Topic Scope:**
- **Never-Matched Only** (default) — topics that never matched any URL
- **All Topics** — all taxonomy topics (useful when topics like IFRS/FRS have some matches but need more synonyms)

**Analysis Modes:**

| Mode | Input Files | What It Does |
|------|-------------|--------------|
| Gap Analysis | Match File + Taxonomy | Never-matched topics, suggests keywords from URL paths |
| Keyword Analysis | Semantic File + Taxonomy | Compares keywords against topics for synonym candidates |
| Combined | Match + Semantic + Taxonomy | Both analyses merged |

**Features:** Priority/Min Score/NEW only/Topic Scope filters · Treeview with Topic, Synonym, Score, Frequency, Priority · Click to toggle selection · Select All / Deselect All · Preview before applying · Apply adds to synonyms.json with backup.

**Key methods:**
- `_refresh_synonym_assistant()` — analyzes files, populates treeview (supports both modes and scopes)
- `_apply_selected_synonyms()` — applies selected items via batch insert
- `_apply_synonyms_batch(df)` — core batch insert method (also used by One-Click Apply)

---

## Post-Processing (Output Cleanup)

`post_processor.py` cleans raw matching output by applying quality filters. GUI: "Clean Output" button or CLI.

```bash
python post_processor.py -i taxonomy_match_GB.xlsx -o cleaned.xlsx --max-rank 3 --frequency-threshold 0.2
```

**Filter Rules (applied in order):**
1. **URL-Product Validation** — checks if assigned Product appears in URL path
2. **URL-Content Confidence** — scores rows as High/Medium/Low/None based on product + topic presence in URL
3. **Topic Frequency Penalty** — flags topics appearing in >20% of URLs (likely over-broad synonyms)
4. **Rank Trim** — removes ranks 4-5 unless "Best Match" or "Highly Relevant"
5. **Duplicate Segment Cleanup** — keeps only highest-ranked row per URL+Segment
6. **URL Cleaning** — decodes %252B etc. for better keyword extraction

**Output columns added:** `URL_Confidence` (High/Medium/Low/None), `Filter_Action` (kept/removed), `Filter_Reason`, `Topic_Frequency_Penalty`

**Output:** Two sheets — "Cleaned" (kept rows) and "Removed" (filtered rows with reasons). Always creates new file — never modifies input.
- Post-processor: `{input}_cleaned.xlsx`
- URL filter: `{input}_filtered.xlsx`

---

## URL Anchor Cleanup

URL anchors (`#elm-main-content`, `#title`, `#Guidelines`) are **automatically stripped before matching**.

1. `taxonomy_matcher.py` — `clean_url()` strips anchors before any URL processing (keyword extraction, relevance calculation, deduplication)
2. `post_processor.py` — safety net for files created before this feature

Result: `page#elm-main-content` and `page#title` deduplicate as the same URL; anchor text is excluded from keyword extraction.

---

## URL Pattern Filtering (GB-specific)

`post_processor.py` includes URL exclusion patterns for filtering out non-content URLs. GUI: "Filter URL Patterns" button.

**GUI Workflow:**
1. Click "Filter URL Patterns" → file picker
2. Dialog shows anchor cleanup info and exclusion patterns
3. Click "View" to see up to 20 sample URLs matching each pattern
4. Uncheck patterns you don't want to apply
5. Click "Apply" → outputs `{filename}_filtered.xlsx`

```bash
python post_processor.py -i taxonomy_match_GB.xlsx --preview-patterns
python post_processor.py -i taxonomy_match_GB.xlsx --url-patterns special_pages shallow_nav -o filtered.xlsx
python post_processor.py -i taxonomy_match_GB.xlsx --all-patterns -o filtered.xlsx
python post_processor.py -i taxonomy_match_GB.xlsx --no-anchor-cleanup -o filtered.xlsx
```

**Default Patterns:**

| Pattern Name | Regex | Description |
|--------------|-------|-------------|
| `special_pages` | `/Special:` | Special pages (login/search/password) |
| `shallow_nav` | (complex) | Shallow navigation pages (depth 1-2) |
| `edit_mode` | `[?&]action=edit` | Edit mode URLs |
| `root_domain` | `^https?://[^/]+/?#?$` | Root domain only |
| `go_redirects` | `/@go/` | Redirect shortcuts |
| `archive_pages` | `/Archive/` | Archived content |
| `media_repo` | `/Media_Repo` | Media repository |

**Adding patterns (code):** Edit `URL_EXCLUSION_PATTERNS` in `post_processor.py`:
```python
URL_EXCLUSION_PATTERNS = [
    ('pattern_name', r'regex_pattern', 'Human-readable description'),
]
```

**Custom patterns (GUI, no code):** Enter text in "URL contains:" → Validate → Add. Session-only (not persisted). Applied as Rule 7 after built-in patterns.

---

## Remap URLs Feature

"🔄 Remap URLs" button in Setup tab — re-runs taxonomy matching on a filtered subset against a new taxonomy.

**Use case:** After cleaning/filtering output, remap those URLs against an updated taxonomy.

**Workflow:**
1. Click "🔄 Remap URLs" (cyan button)
2. Select: Filtered File (URLs to process), Semantic File (for keywords), New Taxonomy, Output File
3. Click "▶ Run Remap"

Extracts unique URLs from filtered file, filters semantic carriers to those URLs, creates temp file, runs standard matching. Supports any number of Topic columns (dynamically detected).

---

## Content Keywords Extractor

"🔍 Extract Keywords" button in Setup tab — extracts keywords from content columns to generate a clean keywords file.

**Use case:** When you have URLs + content but need Keyword columns for Remap URLs.

**Key principle:** Ignores any existing Keyword columns in input. Output contains ONLY freshly extracted keywords from actual content.

**Output naming:** `Content_Keywords_{mode}_{datetime}.xlsx` where mode = `crawl` or `text`.

**Workflow:**
1. Click "🔍 Extract Keywords" (teal button)
2. Select: Input File (any Excel with URL/Title/Summary/Description columns), Taxonomy File (optional, for ranking), Output File
3. Optionally check "🌐 Crawl URLs for content"
4. Click "▶ Extract Keywords"
5. Use output as Semantic File in "Remap URLs"

**Crawl option (powered by Trafilatura):** 10 concurrent threads · three-tier extraction (own heuristic → readability-lxml → jusText) · strips nav/ads/cookies/footers · falls back to columns if page thin (<100 chars) · falls back to `requests` if trafilatura not installed.

**URL Path Intelligence:**
1. Double URL decoding — `%252BGains` → `%2BGains` → `+Gains` → `Gains`
2. Separator splitting — splits on `_`, `-`, `+`
3. Numeric prefix removal — `15Journals` → `Journals`, `010_Overview` → `Overview`
4. CamelCase splitting — `ChartOfAccounts` → `Chart Of Accounts`
5. HTML entity cleanup — `&nbsp;`, `&amp;` decoded; `nbsp`, `amp` in stopwords

**Output columns:** URL · Title · Summary · Description · Product (preserved if present) · Keyword 1–12

**CLI:**
```python
from content_keyword_extractor import ContentKeywordExtractor

extractor = ContentKeywordExtractor(taxonomy_file="taxonomy.xlsx", threshold=80)
# Or with crawling:
extractor = ContentKeywordExtractor(taxonomy_file="taxonomy.xlsx", crawl_urls=True, max_workers=10)
extractor.process_file(input_file="input.xlsx", output_file="output_keywords.xlsx")
```

**Example transformation:**
```
Input:  URL=https://site.com/CCH_iFirm/15Journals  Title=Journals and Advisor Journals
Output: Keyword 1=journals  Keyword 2=advisor journals  Keyword 3=journal postings  ...
```

---

## Import from Taxonomy (Synonym Editor)

"📥 Import from Taxonomy" button in Synonym Editor imports missing topics from a taxonomy file.

**Use case:** Taxonomy has topics not yet in synonyms.json — they can't have synonyms added via the editor until imported.

**Workflow:** Synonym Editor tab → select country → "📥 Import from Taxonomy" → select taxonomy → dialog shows topics missing from synonyms.json → select topics → "📥 Import Selected" → Save changes.

---

## Debug Mode & Row Limiting

```bash
python taxonomy_matcher.py -c GB --debug --max-rows 5 --url-filter "Journals"
python taxonomy_matcher.py -c GB --debug
python taxonomy_matcher.py -c GB --max-rows 10 --url-filter "iFirm"
```

**Parameters:**

| Parameter | CLI Flag | GUI Control | Default | Description |
|-----------|----------|-------------|---------|-------------|
| `debug` | `--debug` | Checkbox | False | Per-keyword trace: synonym expansion, fuzzy scores, match/reject reasons |
| `max_rows` | `--max-rows N` | Spinbox | 0 (all) | Limit to first N rows (applied after URL filter) |
| `url_filter` | `--url-filter TEXT` | Entry field | '' (all) | Only process URLs containing this text (case-insensitive) |
| `top_n` | `--top-n N` | Slider (1–10) | **6** (v3.21) | Max rows per URL in consolidated output |

**Filter ordering:** URL filter applied first, then max_rows limits within filtered set.

**Debug trace example:**
```
[DEBUG] === URL: https://site.com/CCH_iFirm/15Journals ===
[DEBUG] Product: CCH iFirm Accounts Production
[DEBUG] Keywords (3): ['journals', 'advisor journals', 'journal postings']
[DEBUG]   KW 'journals' -> expanded with: ['journal entries', 'journal postings']
[DEBUG]     MATCH: 'Journals' score=100 (CCH iFirm Accounts Production/Data Entry)
[DEBUG]   KW 'advisor journals' -> no synonym expansion
[DEBUG]     NO MATCH (below 80% threshold) -- Nearest miss: 'Journals' score=72
```

**GUI:** Controls in Matching Settings card under "Testing & Debug". Output in Console tab.

---

## Topic Recommendations Report

`generate_topic_recommendations.py` — analyzes match results against taxonomy. GUI: Reports tab → Topic Recommendations Report.

```bash
python generate_topic_recommendations.py
# Edit MATCH_FILE, TAXONOMY_FILE, OUTPUT_FILE, DOCUMENT_SOURCE_FILE at top of file
```

**Output (8-sheet Excel):**
1. **Executive Summary** — key metrics (match rate, gaps, issues)
2. **Data Quality Issues** — typos, reference errors, spacing in taxonomy
3. **Product Gap Analysis** — products with insufficient topic coverage (URL:Topic ratio)
4. **Topic Recommendations** — Status: `Existing (Product)`, `Existing (General)`, `Existing (Other)`, `New`
5. **Suggested New Topics** — topics found in URLs but not in taxonomy
6. **URLs by Product** — URL counts per product
7. **Impact Summary** — expected improvements if recommendations implemented
8. **Topics to Add** — specific topics to add for each gap product

**Status values:** `Existing (Product)` · `Existing (General)` · `Existing (Other)` · `New` (not in taxonomy — consider adding)

**Key Functions (for imports):**
```python
from generate_topic_recommendations import (
    analyze_data_quality, analyze_product_gaps, generate_topic_recommendations,
    generate_suggested_new_topics, generate_urls_by_product, generate_impact_summary,
    generate_topics_to_add, generate_executive_summary, sanitize_dataframe
)
```

---

## Taxonomy Gap Analysis Report

`generate_taxonomy_gap_analysis.py` — phantom topics, never-matched topics, synonym recommendations. GUI: Reports tab → Taxonomy Gap Analysis Report.

```bash
python generate_taxonomy_gap_analysis.py
# Edit MATCH_FILE, TAXONOMY_FILE, SEMANTIC_FILE (optional), OUTPUT_FILE at top
# Tip: Run in a separate terminal while GUI is busy (e.g., while matching runs)
```

**Output (8-sheet Excel):**
1. **Executive Summary** — match rate, topic coverage + noise-filtering note
2. **Phantom Topics** — topics in matches but NOT in taxonomy (data quality issue)
3. **Never-Matched Topics** — taxonomy topics that never matched any URL
4. **Taxonomy Comparison** — compare two taxonomy files (if COMPARISON_TAXONOMY_FILE set)
5. **Synonym Recommendations** — suggested keywords for never-matched topics (HIGH/MEDIUM/LOW)
6. **Product Breakdown** — URL and match stats by product
7. **Action Items** — prioritized recommendations (P1-CRITICAL, P1-HIGH, P2-MEDIUM, P3-LOW)
8. **Progress** *(v3.20)* — full run history from `gap_analysis_progress.json`

**Synonym Recommendations columns:** `Taxonomy_Topic` · `Status` · `Suggested_Synonyms` · `Priority` · `Sample_URL_1`–`Sample_URL_5`

**Thresholds (v3.20 — relative to main matcher threshold):**
```python
THRESHOLD = 80                 # Match your main matcher threshold
SYNONYM_SCORE_THRESHOLD = 60   # Runtime: max(50, THRESHOLD - 20)
HIGH_PRIORITY_SCORE = 75       # Runtime: THRESHOLD - 5
MEDIUM_PRIORITY_SCORE = 65     # Runtime: THRESHOLD - 15
MIN_KEYWORD_FREQUENCY = 3
COUNTRY_CODE = ''              # Optional: tag runs e.g. 'GB', 'BE'
```
GUI version reads threshold from main threshold slider automatically.

**Progress tracking:** Each run appends to `gap_analysis_progress.json`. Columns: `run_datetime`, `country_code`, `match_rate_pct`, `total_urls`, `mapped_urls`, `unmapped_urls`, `never_matched_topics_count`, `phantom_topics_count`, `total_taxonomy_topics`, `threshold_used`. Resets cleanly if file corrupted or missing.

**Noise-filtering note (v3.20):** Executive Summary includes `=== KEYWORD NOISE FILTERING ===` section listing Dutch UI chrome phrases and English CMS gerunds filtered by `NOISE_PHRASE_STARTS` — prevents readers mistaking filtered phrases for missing synonym opportunities.

---

## Custom Taxonomy File Persistence

The GUI remembers the last used taxonomy file per country in `config.yaml`:

```yaml
last_used_files:
  GB:
    taxonomy: "C:\\path\\to\\custom_taxonomy.xlsx"
```

After successful matching, the taxonomy file path is saved. Next session auto-loads it. Blue indicator shows "Using: [filename]" with "Reset to Default" button. Reset clears saved path and reverts to `countries/{CODE}/taxonomy.xlsx`.

**Methods in `country_config.py`:**
- `save_last_used_taxonomy(country_code, path)` — save custom path
- `get_last_used_taxonomy(country_code)` — get saved path (or None)
- `clear_last_used_taxonomy(country_code)` — reset to default

---

## Remove Top Level Pages

`remove_top_level_pages.py` — filters MindTouch "Topic Hierarchy" navigation pages from URL spreadsheets (GB userdocs site only).

**Detection:** Fetches each URL, checks page source for "Topic Hierarchy" (MindTouch template metadata: `templatePath: MindTouch/IDF3/Views/Topic_hierarchy`).

```bash
python remove_top_level_pages.py -i input.xlsx -o output.xlsx
python remove_top_level_pages.py -i input.xlsx  # auto-names output with _no_top_level suffix
```

**CLI args:** `-i INPUT` · `-o OUTPUT` · `--tag TEXT` (default: "Topic Hierarchy") · `--workers N` (default: 10)

**Performance:** 10 concurrent threads, ~15 URLs/sec. Full GB dataset of 2,648 unique URLs ≈ 3 minutes.

**Output:** Two sheets — "Content Pages" (kept) and "Removed Top Level" (for review).

**Typical results (GB, Feb 2026):** 6,036 rows → 293 unique top-level URLs found (11%) → 574 rows removed → 5,462 kept.

**Error handling:** URLs that fail to fetch (timeouts, errors) are kept in output (not removed).
