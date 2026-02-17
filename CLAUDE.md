# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference (Critical Facts)

⚠️ **MUST KNOW before modifying code:**
1. **Product column handling:**
   - Salesforce CSV Import: Product extracted from Data_Categories__c and used for multi-product matching
   - Regular semantic files: Product column ignored during matching
   - Output Product/Domain/Segment always come from taxonomy matches
2. **Output is always consolidated** - one row per URL-Segment with Topic_1, Topic_2, etc. columns
3. **No auto-segment addition** - only topics from taxonomy file appear in output
4. **Topics are never created** - all topics must exist in taxonomy Topic columns
5. **Synonyms affect matching** - control which taxonomy topics match by editing `countries/{CODE}/synonyms.json`
6. **Hybrid relevance** - Top_Relevance uses BOTH similarity score AND URL content analysis
7. **rapidfuzz is used** - NOT fuzzywuzzy (50x faster, API compatible)
8. **ContentKeywordExtractor deduplicates by URL** - Unless Product column exists with multi-product rows (v3.13 fix)
9. **Data_Categories__c enables multi-product matching** - One article can match multiple products via row expansion

## Project Overview

**NL Taxonomy Mapper V3** maps URLs from semantic carriers to taxonomy topics using fuzzy string matching. Multi-country support (NL, SE, BE, GB) with language-specific synonyms and external configuration.

**Core Purpose:** Maps keywords (Keyword 1-12 + optional Summary) to hierarchical taxonomy (Product → Domain → Segment → Topic) using fuzzy matching with auto-deduplication.

## Development Commands

```bash
# Setup
pip install -r requirements.txt
# Required: pandas, openpyxl, rapidfuzz, PyYAML
# Optional (for URL crawling): pip install trafilatura requests

# Run GUI
python taxonomy_matcher_gui.py
# Or: launch_gui.bat

# Run CLI
python taxonomy_matcher.py -c GB -t 80

# CLI args: -c COUNTRY, -t THRESHOLD, --semantic-file, --taxonomy-file, -o OUTPUT, --use-summary, --debug, --max-rows, --url-filter

# Build exe
build.bat
```

## Versioning

**IMPORTANT:** Update version when making changes to the application.

Edit the top of `taxonomy_matcher_gui.py`:
```python
VERSION = "3.12"           # Increment for each release
VERSION_DATE = "2026-02-11"    # Update to release date
VERSION_NOTES = "Hidden Strict Match button (poor quality output)"
```

The version displays in:
- Window title: "NL Taxonomy Mapper V3.12"
- About tab: Shows version, date, and change notes

## Version History (Recent Changes)

| Version | Date | Key Changes |
|---------|------|-------------|
| 3.15 | 2026-02-17 | Source-aware keyword matching — Title keywords use lower threshold (max(70, threshold-10)) and boosted relevance. URL keywords get "Low Trust" label at 80-84%. ContentKeywordExtractor outputs Source 1-12 columns. |
| 3.14 | 2026-02-17 | Removed exact match bypass — all topics now go through fuzzy threshold. Cannot rely on URL path for product. Green cell highlighting removed. |
| 3.13 | 2026-02-13 | Data_Categories__c support, multi-product expansion, HTML cleaning fixes, ContentKeywordExtractor deduplication fix |
| 3.12 | 2026-02-11 | Hidden Strict Match button (poor quality output - 90% noise, HTML contamination) |
| 3.11 | 2026-02-11 | Domain & Segment Editor tab for strict content match configuration |
| 3.10 | (previous) | One-Click Apply for synonym recommendations |

**Current stable version:** 3.15

**Deprecated features:**
- ❌ Strict Match (v3.12+): Hidden due to poor quality output. Use crawler keywords instead.

## Architecture

### Core Files

| File | Purpose |
|------|---------|
| `taxonomy_matcher.py` | Core matching engine, CLI, `TaxonomyMatcher` class (uses rapidfuzz + LRU caching) |
| `taxonomy_matcher_gui.py` | Tkinter GUI (Setup, Console, Synonym Editor, Synonym Assistant, Reports, About tabs) with Remap URLs, Extract Keywords, Import SF CSV, Import from Taxonomy, and One-Click Apply features. Note: Strict Match button hidden in v3.12 due to poor quality output |
| `content_keyword_extractor.py` | Extracts keywords from URL/Title/Summary/Description (uses Trafilatura for crawling, CamelCase/numeric prefix URL parsing). NOTE: Skips URL deduplication when Product column exists (v3.13) |
| `salesforce_csv_processor.py` | Processes Salesforce Knowledge CSV exports (482+ columns), extracts Data_Categories__c, converts Lightning URLs, expands multi-product rows |
| `convert_salesforce_urls.py` | Converts Lightning URLs to public community URLs, extracts URLs from HTML anchor tags |
| `strict_content_matcher.py` | Alternative matcher: generates topics FROM page content (Title, Summary, Description, URL), maps to taxonomy structure where possible |
| `content_topic_matcher.py` | Content-based topic analysis: compares original taxonomy matches with topics derived from URL/Title/Summary/Description content |
| `generate_topic_recommendations.py` | Topic gap analysis and recommendations report generator (8 sheets) |
| `generate_taxonomy_gap_analysis.py` | Taxonomy gap analysis: phantom topics, never-matched, synonym recommendations (7 sheets) |
| `remove_top_level_pages.py` | Filters out top-level/landing pages (containing "Topic Hierarchy" template) from URL spreadsheets |
| `post_processor.py` | Output quality filters (URL validation, rank trimming, deduplication) |
| `country_config.py` | Loads config.yaml, resolves country-specific paths |
| `config.yaml` | Country registry & settings |
| `countries/{CODE}/synonyms.json` | Language-specific synonyms |
| `countries/{CODE}/category_mapping.json` | Maps Salesforce Data_Categories__c values to taxonomy products (v3.13) |

### Key Methods (taxonomy_matcher.py)

| Method | Purpose |
|--------|---------|
| `expand_with_synonyms()` | Bidirectional synonym expansion |
| `should_match_product()` | Product filtering logic |
| `find_topic_matches()` | Fuzzy matching with `fuzz.ratio()` |
| `extract_summary_terms()` | Extracts 2-3 word phrases from Summary column (no single words) |
| `extract_keywords()` | Extracts Keywords 1-12 + optional Summary terms |
| `consolidate_results()` | Groups by URL-Segment, spreads topics to columns |
| `extract_url_keywords()` | Parses URL path for relevance calculation (CamelCase split, numeric prefix strip, double-decode) |
| `calculate_relevance()` | Hybrid score + URL content analysis |

### Data Flow

```
1. Load config.yaml → determine country → load synonyms.json
2. Load semantic_carriers.xlsx and taxonomy.xlsx
3. Flatten taxonomy → List[Dict] with {product, domain, segment, topic}
4. For each URL:
   - Extract Keyword 1-12 (Product column IGNORED)
   - If --use-summary enabled: extract 2-3 word phrases from Summary (not single words)
   - Expand keywords with synonyms (bidirectional, word boundary enforced)
   - Fuzzy match against all topics (threshold ≥80)
   - Record matches with taxonomy Product/Domain/Segment
   - Deduplicate (URL, Product, Domain, Segment, Topic)
5. Consolidate: group by (URL, Product, Domain, Segment) → Topic_1, Topic_2, etc.
6. Export: taxonomy_match_{CODE}.xlsx
```

### Key Architecture Patterns

**Synonym Expansion (Bidirectional with word boundary rules):**
- **Direction 1** (topic→synonyms): If keyword contains topic name as complete word(s) AND keyword is >= topic length → add all synonyms. Example: keyword `"security mapping"` contains topic `"Security"` → adds synonyms `["data security", "permissions"]`. But single-word `"data"` does NOT expand via multi-word topic `"Data import"`.
- **Direction 2** (synonym→topic): If keyword exactly equals a synonym → add topic name. Multi-word keywords can also match if synonym is a complete word in them. Example: keyword `"audit workflows"` contains synonym `"workflows"` of topic `"Workflow"` → adds `"workflow"`. But single-word `"data"` does NOT match synonym `"data validation"`.
- **Key function**: `_is_word_match(needle, haystack)` enforces word boundary checks
- **Key rule**: Single-word terms cannot match multi-word synonyms/topics (prevents generic word explosion)

**Product Filtering:**
1. Empty taxonomy Product → matches ANY semantic Product
2. Exact Product match → semantic = taxonomy
3. "Other" semantic Product → matches any taxonomy Product

**Exact Match Bypass — REMOVED in v3.14:**
- ❌ Previously: keywords exactly matching a topic name got score=100 and bypassed the fuzzy threshold
- ❌ Caused false matches: URL slugs like "Fiscaal-dossier" would force-match topic "Fiscaal dossier"
- ✅ All topics now go through normal fuzzy threshold matching (no exceptions)
- ✅ Green cell highlighting removed (was used to flag exact match topics)
- **Cannot rely on URL path for product** — URL slugs contain product/article names that create false exact matches

**Topic Consolidation:**
- Groups by (URL, Product, Domain, Segment)
- Spreads topics across Topic_1, Topic_2, etc.
- Filters segment names from Topic columns
- Always enabled (no toggle)

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

## Input/Output Specs

**semantic_carriers_list.xlsx (or crawler output):**
- Required: URL, Keyword 1-12 (with space)
- Optional: Summary (for `--use-summary` mode), Product, Title, Word Count, etc.

**taxonomy.xlsx:**
- Required: Product, Domain, Segment, Topic 1 through Topic N
- Topics detected dynamically via `col.startswith('Topic')`

**Output (taxonomy_match_{filename}_{CODE}.xlsx):**
- Note: Output filename includes the input filename stem and country code suffix (e.g., `taxonomy_match_semantic_GB.xlsx`)
- Columns: URL, Title, Description, Summary, Product, Domain, Segment, Topic_1...Topic_N, Top_Score, Top_Relevance, Unmapped_Reason, Unmatched_Keywords, Rank
- Title, Description, Summary are carried through from the input semantic file (if present)
- One row per URL-Segment combination
- Unmatched_Keywords: comma-separated list of keywords that did not match any taxonomy topic above the threshold (empty if all keywords matched)
- Unmapped URLs: Domain='UNMAPPED', Top_Score=0, Unmapped_Reason explains why, Unmatched_Keywords lists all keywords

**Unmapped_Reason values:**
- `No keywords extracted from row` - Keyword 1-12 are all empty
- `No matches above {threshold}% threshold` - Keywords exist but no fuzzy matches
- `Product filter excluded matches (semantic Product: X)` - Matches found but filtered by product

## Keyword Recommendations (Output Sheet)

The main taxonomy match output includes a second sheet "Keyword Recommendations" that analyzes every unmatched keyword and provides actionable recommendations.

**Data capture:** Near-miss data is collected during `find_topic_matches()` via `track_near_misses=True`. Keywords scoring >= 50 but below threshold are tracked, along with product-filtered entries. This avoids re-running fuzzy matching post-hoc.

**Key instance variables:**
- `self._keyword_near_misses` (dict) - Accumulated during `process_matching()`, keyed by keyword lowercase
- `self._recommendations_df` (DataFrame) - Generated in `save_output()`, stored for GUI access

**Sheet columns:**
| Column | Description |
|--------|-------------|
| `Keyword` | The unmatched keyword |
| `Frequency` | How many URLs had this unmatched keyword |
| `Nearest_Topic` | Closest taxonomy topic by score |
| `Nearest_Score` | The fuzzy score it achieved |
| `Rejection_Reason` | "Below threshold (78% < 80%)" / "Product filtered" / "No close match (<50%)" |
| `Recommendation` | "Add as synonym to [Topic]" / "Consider new topic" / "Noise - ignore" |
| `Target_Product` | Product the nearest topic belongs to |
| `Target_Domain` | Domain the nearest topic belongs to |
| `Target_Segment` | Segment the nearest topic belongs to |
| `Priority` | HIGH / MEDIUM / LOW (NOISE filtered out) |
| `Already_In_Synonyms` | Yes/No - already a synonym for the target topic |
| `Sample_URL_1-3` | Up to 3 sample URLs containing this keyword |

**Priority classification:**
| Priority | Criteria |
|----------|----------|
| HIGH | Score >= (threshold - 5) AND frequency >= 3 |
| MEDIUM | Score >= (threshold - 15) AND frequency >= 2, OR product-filtered, OR frequency >= 5 with no close match |
| LOW | Score >= 50 |
| NOISE | Everything else (filtered from output) |

**One-Click Apply:** After matching completes in the GUI, if HIGH priority synonym recommendations exist, a dialog offers to apply them directly to synonyms.json. Uses the existing `_apply_synonyms_batch()` method.

**Key methods:**
- `find_topic_matches(..., track_near_misses=True)` - Returns `(matches, near_misses)` tuple
- `generate_keyword_recommendations()` - Processes `_keyword_near_misses` into DataFrame
- `_show_keyword_rec_apply_dialog()` - GUI dialog for One-Click Apply

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
Then create `countries/DE/` with the three files.

### Add Synonyms
Edit `countries/{CODE}/synonyms.json`:
```json
{"synonyms": {"TopicName": ["synonym1", "synonym2"]}}
```
Or use GUI: Synonym Editor tab → select topic → Bulk Import

### Adjust Threshold
- config.yaml: `settings.similarity_threshold: 85`
- CLI: `-t 85`
- GUI: threshold slider

### Change Fuzzy Algorithm
In `find_topic_matches()` method, `fuzz.ratio()` is used. Alternatives:
- `fuzz.partial_ratio()` - substring matching (looser)
- `fuzz.token_sort_ratio()` - word order independent
- `fuzz.token_set_ratio()` - subset matches

## Reports Tab

The Reports tab uses a scrollable layout with compact cards for quick reports and a full-width section for Topic Recommendations.

**Quick Reports (3-column layout):**

| Report | Button Color | Output |
|--------|--------------|--------|
| Proposed Synonyms | Blue | 5-sheet Excel with synonym suggestions |
| Match Quality | Purple | 5-sheet Excel with relevance analysis |
| Unmapped Reasons | Orange | 5-sheet Excel with failure diagnostics |

**Synonym Report:** Compares keywords with taxonomy topics:
1. All Proposed Synonyms (with Already_Added column)
2. HIGH Priority (score ≥85%, freq ≥50)
3. Summary by Topic
4. NEW Only (not in synonyms.json)
5. Unmapped Keywords

**Match Quality Report:** Analyzes match relevance:
1. All Matches (with Rank_In_URL, Relevance)
2. Top N Per URL
3. Match Statistics
4. Low Confidence
5. Relevance Summary

**One-Click Apply (Proposed Synonyms):**
After generating the Proposed Synonyms report, a dialog appears offering:
- **Apply All HIGH Priority** - Directly adds HIGH priority NEW synonyms to synonyms.json
- **Review in Excel** - Opens the report in Excel for manual review
- **Skip** - Closes without applying

This eliminates the manual Excel → copy → paste workflow for adding synonyms.

## Synonym Assistant

Dedicated tab for reviewing and applying synonyms directly in the GUI (full-screen layout).

**File Inputs:**
- **Match File** (filtered output) - For gap analysis: finds never-matched topics and suggests keywords from URLs
- **Semantic File** (optional) - For keyword analysis: compares keywords against taxonomy topics
- **Taxonomy File** (required) - The taxonomy to analyze against

**Topic Scope:**
- **Never-Matched Only** (default) - Only analyzes topics that never matched any URL
- **All Topics** - Analyzes all taxonomy topics (useful when topics like IFRS/FRS have some matches but need more synonyms)

**Analysis Modes:**
| Mode | Input Files | What It Does |
|------|-------------|--------------|
| Gap Analysis | Match File + Taxonomy | Finds topics that never matched any URL, suggests keywords from URL paths |
| Keyword Analysis | Semantic File + Taxonomy | Compares keywords against topics to find potential synonyms |
| Combined | Match + Semantic + Taxonomy | Both analyses merged, best of both worlds |

**Features:**
- **Filter controls**: Priority (HIGH/MEDIUM/LOW/ALL), Min Score, NEW only checkbox, Topic Scope selector
- **Treeview**: Displays suggestions with Topic, Synonym, Score, Frequency, Priority
- **Selection**: Click rows to toggle selection (checkmark indicates selected)
- **Batch operations**: Select All, Deselect All
- **Preview**: Shows exactly which synonyms will be added to which topics
- **Apply**: Adds selected synonyms to synonyms.json with backup

**Key methods:**
- `_refresh_synonym_assistant()` - Analyzes files and populates treeview (supports both modes and topic scopes)
- `_apply_selected_synonyms()` - Applies selected items via batch insert
- `_apply_synonyms_batch(df)` - Core batch insert method (also used by One-Click Apply)

## Post-Processing (Output Cleanup)

The `post_processor.py` module cleans raw matching output by applying quality filters. Access via GUI "Clean Output" button or CLI.

**CLI usage:**
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

**Output columns added:**
- `URL_Confidence`: High (product + topic in URL), Medium (product only), Low (topic only), None (neither)
- `Filter_Action`: kept/removed
- `Filter_Reason`: why row was removed
- `Topic_Frequency_Penalty`: True if Topic_1 is generic (>20% of URLs)

**Output file:** Two sheets — "Cleaned" (kept rows) and "Removed" (filtered rows with reasons)

**Important:** Post-processor and URL filter NEVER modify input files. They always create new output files:
- Post-processor: `{input}_cleaned.xlsx`
- URL filter: `{input}_filtered.xlsx`

## URL Anchor Cleanup

**URL anchors (fragments like `#elm-main-content`, `#title`, `#Guidelines`) are automatically stripped BEFORE matching.**

This happens in two places:
1. **taxonomy_matcher.py** - `clean_url()` strips anchors before any URL processing (keyword extraction, relevance calculation, deduplication)
2. **post_processor.py** - Safety net for files created before this feature

This ensures:
- Matching uses clean URLs without navigation anchors
- URLs like `page#elm-main-content` and `page#title` are deduplicated as the same URL
- Keyword extraction doesn't include anchor text

## URL Pattern Filtering (GB-specific)

The `post_processor.py` module includes URL exclusion patterns for filtering out non-content URLs. Access via GUI "Filter URL Patterns" button or CLI.

**GUI Workflow:**
1. Click "Filter URL Patterns" button → file picker opens
2. Progress indicator shows while analyzing file
3. Dialog shows anchor cleanup info (URLs to be cleaned) and exclusion patterns (URLs to be removed)
4. Click "View" to see sample URLs matching that pattern (up to 20)
5. Uncheck patterns you don't want to apply
6. Click "Apply" → outputs `{filename}_filtered.xlsx`

**CLI Usage:**
```bash
# Preview patterns without applying
python post_processor.py -i taxonomy_match_GB.xlsx --preview-patterns

# Apply specific patterns
python post_processor.py -i taxonomy_match_GB.xlsx --url-patterns special_pages shallow_nav -o filtered.xlsx

# Apply all patterns
python post_processor.py -i taxonomy_match_GB.xlsx --all-patterns -o filtered.xlsx

# Disable anchor cleanup (not recommended)
python post_processor.py -i taxonomy_match_GB.xlsx --no-anchor-cleanup -o filtered.xlsx
```

**Default URL Exclusion Patterns:**
| Pattern Name | Regex | Description |
|--------------|-------|-------------|
| `special_pages` | `/Special:` | Special pages (login/search/password) |
| `shallow_nav` | (complex) | Shallow navigation pages (depth 1-2) |
| `edit_mode` | `[?&]action=edit` | Edit mode URLs |
| `root_domain` | `^https?://[^/]+/?#?$` | Root domain only |
| `go_redirects` | `/@go/` | Redirect shortcuts |
| `archive_pages` | `/Archive/` | Archived content |
| `media_repo` | `/Media_Repo` | Media repository |

**Adding New Patterns (Code):**
Edit `URL_EXCLUSION_PATTERNS` in `post_processor.py`:
```python
URL_EXCLUSION_PATTERNS = [
    ('pattern_name', r'regex_pattern', 'Human-readable description'),
    # ... existing patterns
]
```

**Custom Patterns (GUI - No Code Required):**
Users can add custom text-based patterns directly in the URL Pattern Filter dialog:
1. Enter text in "URL contains:" field (e.g., `/Archive/`)
2. Click "Validate" to see match count
3. Click "Add" to add pattern to filter list
4. Pattern appears with checkbox, View button, and remove (✕) button
5. Custom patterns use case-insensitive text matching (not regex)

Custom patterns are applied as Rule 7 after built-in patterns. They are session-only (not persisted).

## Remap URLs Feature

The "🔄 Remap URLs" button in the Setup tab allows re-running taxonomy matching on a filtered subset of URLs against a new taxonomy file.

**Use case:** After cleaning/filtering output, remap those URLs against an updated taxonomy.

**Workflow:**
1. Click "🔄 Remap URLs" (cyan button in Setup tab)
2. Select files:
   - **Filtered File**: Cleaned output with URLs to process
   - **Semantic File**: Original semantic carriers (for keywords)
   - **New Taxonomy**: Updated taxonomy file
   - **Output File**: Where to save results
3. Click "▶ Run Remap"

**How it works:**
- Extracts unique URLs from filtered file
- Filters semantic carriers to only those URLs
- Creates temp file and runs standard matching
- Supports taxonomies with any number of Topic columns (dynamically detected)

## Content Keywords Extractor

The "🔍 Extract Keywords" button in the Setup tab extracts keywords from content columns (URL, Title, Summary, Description) to generate a clean keywords file.

**Use case:** When you have a file with URLs and content but need Keyword columns for Remap URLs.

**Key principle:** Start with a CLEAN keyword list. Any existing Keyword columns in the input file are completely ignored. Output contains ONLY freshly extracted keywords from actual content.

**Output naming convention:** `Content_Keywords_{mode}_{datetime}.xlsx`
- `mode` = `crawl` (fetched live pages) or `text` (used spreadsheet columns)
- `datetime` = `YYYYMMDD_HHMMSS` timestamp of extraction

**Workflow:**
1. Click "🔍 Extract Keywords" (teal button in Setup tab)
2. Select files:
   - **Input File**: Any Excel with URL, Title, Summary, Description columns
   - **Taxonomy File** (optional): For ranking keywords by taxonomy match score
   - **Output File**: Auto-named `Content_Keywords_{mode}_{datetime}.xlsx`, updates when crawl toggled
3. **Optional**: Check "🌐 Crawl URLs for content" to fetch actual page content
4. Click "▶ Extract Keywords"
5. Use the output as Semantic File in "Remap URLs"

**Crawl URLs Option (powered by Trafilatura):**
When enabled, the extractor fetches actual page content using Trafilatura, a multi-algorithm content extraction library (F1=0.958 on benchmarks):
- Uses 10 concurrent threads for speed
- Three-tier extraction: own heuristic → readability-lxml → jusText
- Automatically strips headers, footers, navigation, sidebars, ads, cookie banners
- Falls back to Summary/Description if page returns thin content (<100 chars)
- Falls back to basic `requests` if trafilatura not installed
- Much better keywords than truncated Excel columns

**URL Path Intelligence (v3.5):**
The extractor handles complex CMS URL patterns:
1. **Double URL decoding** - `%252BGains` → `%2BGains` → `+Gains` → `Gains`
2. **Separator splitting** - Splits on `_`, `-`, `+`
3. **Numeric prefix removal** - `15Journals` → `Journals`, `010_Overview` → `Overview`
4. **CamelCase splitting** - `ChartOfAccounts` → `Chart Of Accounts`
5. **HTML entity cleanup** - `&nbsp;`, `&amp;` decoded; `nbsp`, `amp` in stopwords
6. **Smart joining** - Only joins short parts for separator-free segments (prevents `Chart_of` → `chartof`)

**How it works:**
1. Extracts terms from URL path (CamelCase split, numeric prefix stripped, double-decoded)
2. If crawling: fetches page content via Trafilatura and extracts keywords from main body
3. If not crawling: extracts from Title, Summary, Description columns
4. Ranks keywords by taxonomy match score (if taxonomy provided)
5. Filters noise words, generic phrases, and HTML entity fragments
6. Outputs top 12 keywords per row in Keyword 1-12 columns

**Output columns:**
- `URL` - original URL (deduplicated)
- `Title`, `Summary`, `Description` - preserved from input
- `Product` - preserved if present
- `Keyword 1` through `Keyword 12` - freshly extracted keywords

**CLI Usage:**
```python
from content_keyword_extractor import ContentKeywordExtractor

# Without crawling (use columns)
extractor = ContentKeywordExtractor(
    taxonomy_file="taxonomy.xlsx",  # Optional
    threshold=80
)

# With crawling (fetch pages via Trafilatura)
extractor = ContentKeywordExtractor(
    taxonomy_file="taxonomy.xlsx",
    crawl_urls=True,
    max_workers=10  # Concurrent threads
)

extractor.process_file(
    input_file="input.xlsx",
    output_file="output_keywords.xlsx"
)
```

**Example transformation:**
```
Input row:
  URL: https://site.com/CCH_iFirm/15Journals
  Title: Journals and Advisor Journals
  Summary: The Journal screen allows data entry via journals...

Output row:
  URL: (same)
  Keyword 1: journals           (exact taxonomy match, numeric prefix stripped)
  Keyword 2: advisor journals   (taxonomy match from title)
  Keyword 3: journal postings   (from Summary)
  Keyword 4: firm accounts production  (from URL, CamelCase split)
  ...
```

## Import from Taxonomy (Synonym Editor)

The "📥 Import from Taxonomy" button in the Synonym Editor imports missing topics from a taxonomy file.

**Use case:** Taxonomy has topics that aren't in synonyms.json (so they can't have synonyms added via the editor).

**Workflow:**
1. Go to Synonym Editor tab, select country
2. Click "📥 Import from Taxonomy" (purple button)
3. Select taxonomy file
4. Dialog shows topics in taxonomy but missing from synonyms.json
5. Select topics to import (Select All / Deselect All available)
6. Click "📥 Import Selected"
7. Save changes to persist

## Debug Mode & Row Limiting

Debug mode and row limiting allow faster testing and keyword match tracing.

**CLI Usage:**
```bash
# Debug mode with row limiting
python taxonomy_matcher.py -c GB --debug --max-rows 5 --url-filter "Journals"

# Debug only (full dataset, verbose output)
python taxonomy_matcher.py -c GB --debug

# Row limiting only (no debug trace)
python taxonomy_matcher.py -c GB --max-rows 10 --url-filter "iFirm"
```

**Parameters:**
| Parameter | CLI Flag | GUI Control | Default | Description |
|-----------|----------|-------------|---------|-------------|
| `debug` | `--debug` | Checkbox | False | Per-keyword trace: synonym expansion, fuzzy scores, match/reject reasons |
| `max_rows` | `--max-rows N` | Spinbox | 0 (all) | Limit to first N rows (applied after URL filter) |
| `url_filter` | `--url-filter TEXT` | Entry field | '' (all) | Only process URLs containing this text (case-insensitive, literal match) |

**Filter ordering:** URL filter is applied first, then max_rows limits within the filtered set. So `--url-filter "Journals" --max-rows 5` gives the first 5 Journals URLs.

**Debug trace output example:**
```
[DEBUG] === URL: https://site.com/CCH_iFirm/15Journals ===
[DEBUG] Product: CCH iFirm Accounts Production
[DEBUG] Keywords (3): ['journals', 'advisor journals', 'journal postings']
[DEBUG]   KW 'journals' -> expanded with: ['journal entries', 'journal postings']
[DEBUG]     MATCH: 'Journals' score=100 [EXACT] (CCH iFirm Accounts Production/Data Entry)
[DEBUG]   KW 'advisor journals' -> no synonym expansion
[DEBUG]     NO MATCH (below 80% threshold)
[DEBUG]     Nearest miss: 'Journals' score=72
[DEBUG]   Unmatched keywords: ['advisor journals']
```

**GUI:** Controls are in the Matching Settings card under "Testing & Debug" sub-heading. Debug output appears in the Console tab.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Wrong Product in output | Product comes from taxonomy, not semantics. Use synonyms to control matches |
| Unexpected topics | Check taxonomy Topic columns - all topics come from there |
| 0 matches/swap error | Files swapped - click "Swap Files" button or manually switch |
| Country not in dropdown | Check config.yaml: `enabled: true`, uppercase code, restart GUI |
| Slow processing | Ensure rapidfuzz is installed: `pip install rapidfuzz` (already in requirements.txt) |
| Empty Topic columns | Segment names filtered from Topic columns (intentional) |
| Crawling disabled | Install trafilatura: `pip install trafilatura` (falls back to requests) |

## Topic Recommendations Report

The `generate_topic_recommendations.py` script analyzes match results against taxonomy to identify gaps and recommendations. Also accessible via GUI Reports tab.

**GUI Usage:** Reports tab → Topic Recommendations Report → select files → Generate

**CLI Usage:**
```bash
python generate_topic_recommendations.py
```

**Configuration (edit top of file for CLI):**
```python
MATCH_FILE = r"path\to\taxonomy_match_cleaned.xlsx"
TAXONOMY_FILE = r"path\to\taxonomy.xlsx"
OUTPUT_FILE = "TOPIC_RECOMMENDATIONS.xlsx"
DOCUMENT_SOURCE_FILE = r"path\to\crawler_output.xlsx"  # Optional
```

**Output (8-sheet Excel):**
1. **Executive Summary** - Key metrics (match rate, gaps, issues)
2. **Data Quality Issues** - Typos, reference errors, spacing issues in taxonomy
3. **Product Gap Analysis** - Products with insufficient topic coverage (URL:Topic ratio)
4. **Topic Recommendations** - Topics with Status: `Existing (Product)`, `Existing (General)`, `Existing (Other)`, or `New`
5. **Suggested New Topics** - Topics found in URLs but not in taxonomy
6. **URLs by Product** - Breakdown of URL counts per product
7. **Impact Summary** - Expected improvements if recommendations implemented
8. **Topics to Add** - Specific topics to add for each gap product

**Status column meanings:**
- `Existing (Product)` - Topic defined specifically for this product
- `Existing (General)` - Topic in General domain (shared across all products)
- `Existing (Other)` - Topic exists in other products (shows which products)
- `New` - Topic NOT in taxonomy - consider adding

**Key Functions (for imports):**
```python
from generate_topic_recommendations import (
    analyze_data_quality,
    analyze_product_gaps,
    generate_topic_recommendations,
    generate_suggested_new_topics,
    generate_topics_from_document_source,
    generate_urls_by_product,
    generate_impact_summary,
    generate_topics_to_add,
    generate_executive_summary,
    sanitize_dataframe  # Prevents Excel corruption
)
```

## Taxonomy Gap Analysis Report

The `generate_taxonomy_gap_analysis.py` script provides comprehensive taxonomy coverage analysis focusing on phantom topics, never-matched topics, and synonym recommendations. Also accessible via GUI Reports tab.

**GUI Usage:** Reports tab → Taxonomy Gap Analysis Report → select files → Generate

**CLI Usage:**
```bash
python generate_taxonomy_gap_analysis.py
```

**Tip:** Run CLI scripts in a separate terminal while GUI is busy with another operation (e.g., run gap analysis while taxonomy matching is in progress).

**Configuration (edit top of file for CLI):**
```python
MATCH_FILE = r"path\to\taxonomy_match_cleaned.xlsx"
TAXONOMY_FILE = r"path\to\taxonomy.xlsx"
SEMANTIC_FILE = r"path\to\semantic_carriers.xlsx"  # Optional
COMPARISON_TAXONOMY_FILE = r"path\to\other_taxonomy.xlsx"  # Optional
OUTPUT_FILE = "TAXONOMY_GAP_ANALYSIS_REPORT.xlsx"
```

**Output (7-sheet Excel):**
1. **Executive Summary** - Key metrics (match rate, topic coverage, findings)
2. **Phantom Topics** - Topics appearing in matches but NOT in taxonomy (data quality issue)
3. **Never-Matched Topics** - Taxonomy topics that never matched any URL (need synonyms or review)
4. **Taxonomy Comparison** - Compare current taxonomy vs comparison taxonomy (if provided)
5. **Synonym Recommendations** - Suggested keywords for never-matched topics with priority (HIGH/MEDIUM/LOW)
6. **Product Breakdown** - URL and match statistics by product
7. **Action Items** - Prioritized recommendations (P1-CRITICAL, P1-HIGH, P2-MEDIUM, P3-LOW)

**Synonym Recommendations columns:**
- `Taxonomy_Topic` - Topic that EXISTS in taxonomy but never matched any URL
- `Status` - "In taxonomy - never matched" (confirms it's a real taxonomy topic)
- `Suggested_Synonyms` - Keywords that could be added as synonyms (with frequency counts in parentheses)
- `Priority` - HIGH (score ≥75), MEDIUM (score ≥65), LOW (score <65)
- `Sample_URL_1` through `Sample_URL_5` - Full URLs containing the suggested keywords (clickable in Excel)

**Thresholds (configurable in script):**
```python
SYNONYM_SCORE_THRESHOLD = 60   # Minimum fuzzy match score
HIGH_PRIORITY_SCORE = 75       # HIGH priority threshold
MEDIUM_PRIORITY_SCORE = 65     # MEDIUM priority threshold
MIN_KEYWORD_FREQUENCY = 3      # Minimum keyword occurrences
```

## Custom Taxonomy File Persistence

The GUI remembers the last used taxonomy file per country in `config.yaml`:

```yaml
last_used_files:
  GB:
    taxonomy: "C:\\path\\to\\custom_taxonomy.xlsx"
```

**Behavior:**
- After successful matching, the taxonomy file path is saved to config
- Next session auto-loads the saved taxonomy for that country
- Blue indicator shows "Using: [filename]" with "Reset to Default" button
- Reset clears saved path and reverts to `countries/{CODE}/taxonomy.xlsx`

**Related methods in `country_config.py`:**
- `save_last_used_taxonomy(country_code, path)` - Save custom path
- `get_last_used_taxonomy(country_code)` - Get saved path (or None)
- `clear_last_used_taxonomy(country_code)` - Reset to default

## Critical Bug Fixes Reference

| Bug | Fix Location | Impact |
|-----|--------------|--------|
| Product filter too strict | `should_match_product()` | 64%→95%+ match rate |
| One-way synonym matching | `expand_with_synonyms()` | 45%→60% match rate |
| Substring false positives | Changed to `fuzz.ratio()` | Reduced irrelevant matches |
| Loose synonym substring | Stricter matching in synonym expansion | Precision improvement |
| Single-word synonym explosion | `_is_word_match()` word boundary rules | "data" no longer matches 14 topics via "data validation" etc. |
| Summary single-word noise | `extract_summary_terms()` phrases only | "guide", "management" no longer hijack results |
| Cross-product exact match | `find_topic_matches()` product filter | "automation" no longer pulls in CCH Workflow topics on CCH Audit URLs |
| Synonym Editor delete fails | `exportselection=False` on Listbox widgets | Delete/edit buttons now work |
| Excel "found a problem" error | `sanitize_dataframe()` in report generation | Clean Excel output |
| URL numeric prefixes in keywords | `extract_from_url()` strips leading digits | "15journals" → "journals" |
| CamelCase URLs not split | `_CAMELCASE_PATTERN` regex in extraction | "ChartOfAccounts" → "chart accounts" |
| Double-encoded URLs | `unquote(unquote(url))` in extraction | "%252B" decoded correctly |
| HTML entities in keywords | `_clean_text()` decodes entities + stopwords | "nbsp", "amp" no longer in keywords |

## Performance Optimizations

The core matching engine uses several optimizations:

**Phase 1 (Foundation):**
1. **rapidfuzz instead of fuzzywuzzy** - ~50x faster fuzzy matching (API compatible)
2. **LRU cache for synonym expansion** - `_expand_keyword_cached()` with 10,000 entry cache
3. **Pre-computed taxonomy structures:**
   - `topic_lower` pre-lowercased in `taxonomy_lookup`
   - `_product_url_forms` for fast product extraction from URLs
   - `_product_lookup` dict for O(1) product filtering
   - `_synonyms_tuple` hashable version for cache compatibility

**Phase 2 (Bottleneck Fixes):**
4. **Product filter before loop** - `find_topic_matches()` filters to product subset BEFORE fuzzy matching loop, reducing comparisons by 50-80% when product is known
5. **URL keyword extraction cache** - `_url_keywords_cache` dict prevents redundant URL parsing during consolidation
6. **O(1) domain/segment lookup** - `_product_topic_lookup[(product, topic)]` replaces linear scan when reassigning "Something Else" topics
7. **Pre-compiled regex** - `_SEPARATOR_PATTERN` replaces 10-iteration string replace loop in content keyword extraction

**Key cached function:**
```python
@lru_cache(maxsize=10000)
def _expand_keyword_cached(keyword_lower: str, synonyms_tuple: tuple) -> tuple:
    # Module-level cached synonym expansion
```

## Excel Data Sanitization

When writing Excel files, use `sanitize_dataframe()` to prevent corruption:
```python
from generate_topic_recommendations import sanitize_dataframe

# Sanitizes before writing - removes control chars, truncates long strings
sanitize_dataframe(df).to_excel(writer, sheet_name='Sheet1', index=False)
```

This fixes the "we found a problem with some content" Excel error by:
- Removing control characters (null bytes, bell, etc.)
- Truncating strings >32000 chars
- Removing problematic Unicode (surrogate pairs)
- Converting None/NaN to empty strings

## Strict Content Matcher

The `strict_content_matcher.py` generates topics purely from page content (Title, Summary, Description, URL path) with **NO taxonomy file dependency**. If a user sees a topic in the output, they can find the related page directly.

This is an **alternative output** alongside the main matcher, not a replacement.

**Key differences from main matcher:**
| | Main Matcher | Strict Content Matcher |
|---|---|---|
| Input | Keyword 1-12 + taxonomy file | Semantic file ONLY (no taxonomy) |
| Synonyms | Yes (bidirectional) | No |
| Method | Fuzzy match keywords vs taxonomy topics | Extracts topics from content directly |
| Domain/Segment | From taxonomy file | Classified from fixed keyword lists |
| Product | From taxonomy matches | From semantic file or URL path heuristic |
| Output | One row per URL-Segment | Up to 3 ranked rows per URL (6 topics each) |
| UNMAPPED | Common (no keyword matches) | Rare (only if Title/Summary/Description all empty) |
| Coverage | Depends on synonyms + keywords | Every page with content gets topics |

**Fixed Domain set:** Accounting, Client Communication, General, Practice Administration, Taxation, Welcome

**Fixed Segment set:** ~60 known segments (Tax return management, Accounts production, Setup and configuration, etc.) classified by keyword matching against content + URL path. Defined in `_VALID_SEGMENTS` and `_SEGMENT_KEYWORDS`.

**Multi-rank output (v3.8):** Each URL can produce up to 3 ranked rows with up to 6 topics per row:
- **Rank 1**: Primary segment classification, best topics (title/URL-derived first)
- **Rank 2**: Secondary segment classification, next 6 topics (content-derived overflow)
- **Rank 3**: Tertiary segment classification, remaining topics
- Each rank gets a different segment from `_classify_segments()` (top 3 segment matches by keyword score)
- URLs with ≤6 topics produce only Rank 1; 7-12 topics → Rank 1+2; 13+ → all 3 ranks

**Status:** ⚠️ **HIDDEN IN v3.12** - Button commented out in GUI (lines 775-788 of taxonomy_matcher_gui.py)

**Reason for hiding:**
- Poor quality output: 90% noise (generic words like "Customers", "Article")
- HTML contamination: 57% of topics contain HTML tags (e.g., "<b><u>vraag<", "<img Src=")
- Product identification failure: Uses article titles instead of product names
- Better alternative exists: Use crawler keywords from NLUrl (0% noise, clean extraction)

**To re-enable (if needed):** Uncomment lines 775-788 in taxonomy_matcher_gui.py

**Historical GUI Usage (v3.11 and earlier):** Setup tab → "📋 Strict Match" button → configure sources → Run

**Source Selection (v3.9):** The GUI dialog lets you toggle which sources contribute topics:
- **Title** (default: on) - Extract topics from page title
- **URL Path** (default: on) - Extract topics from URL path segments
- **Content** (default: on) - Extract from Summary/Description columns
- **Crawl URLs** (default: off) - Fetch live page content via Trafilatura for richer topic extraction

At least one source must be selected. The `sources` list is passed to `StrictContentMatcher`.

**CLI Usage:**
```bash
python strict_content_matcher.py -c GB --debug --max-rows 10
python strict_content_matcher.py -c GB --semantic-file input.xlsx -o output.xlsx
```

**Topic extraction algorithm:**
1. **Title** (primary): Strip action prefixes ("Creating a" → "Tax Bundle"), product names, trailing noise
2. **URL path**: Parse segments, strip product/navigation prefixes (Product Information, Product Help), CamelCase split, extract suffix topics (e.g., "CCH_iFirm_Personal_Tax_Data_Entry" → "Data Entry")
3. **Summary + Description**: Clause-aware 2-3 word phrase extraction with aggressive stopword filtering (up to 12 content phrases to fill multiple ranks)
4. Deduplicate, filter covered phrases (e.g., "tax" is covered by "tax bundle")
5. **Domain classification**: Keyword scoring against `_DOMAIN_KEYWORDS` map
6. **Segment classification**: Top 3 segments via `_classify_segments()` scoring against `_SEGMENT_KEYWORDS` map

**Key methods:**
| Method | Purpose |
|--------|---------|
| `_clean_title_to_topic()` | Strip action prefixes, product names, trailing noise from title |
| `_extract_url_topics()` | Parse URL path segments into topics (skips nav/product segments) |
| `_extract_topic_phrases()` | Clause-aware phrase extraction from text |
| `extract_content_topics()` | Combines title + URL + content sources |
| `_classify_domain()` | Keyword-based domain classification from fixed set |
| `_classify_segments()` | Returns top 3 segments by keyword score from fixed set |
| `_extract_product_from_url()` | Heuristic product name from URL path |
| `consolidate_results()` | Splits topics into ranked rows (6 per row, up to 3 ranks) |

**Output format:** URL, Title, Description, Summary, Product, Domain, Segment, Topic_1..6, Source_1..6, Top_Relevance, Unmapped_Reason, Rank
- `Source_1..6` — where each topic came from: "title", "url", or "content"
- `Top_Relevance` — "Best Match" (title), "Highly Relevant" (url), "Content-Derived" (content)
- `Rank` — 1 (primary), 2 (secondary), 3 (tertiary) — each rank may have a different Segment

**Output filename:** `strict_match_{CODE}.xlsx`

## Content-Based Topic Matcher

The `content_topic_matcher.py` script analyzes URL content (Title, Description, Summary) to find relevant taxonomy topics independently of keyword matching.

**Use case:** Compare original taxonomy matches with what topics the content actually suggests - helps identify mismatches and missing topic coverage.

**CLI Usage:**
```bash
python content_topic_matcher.py
```

**Configuration (edit top of file):**
```python
MATCH_FILE = r"path\to\taxonomy_match_GB.xlsx"
TAXONOMY_FILE = r"path\to\taxonomy.xlsx"
OUTPUT_FILE = r"path\to\content_matched_topics.xlsx"
```

**Output columns:**
- `Row_Type`: "Original" (from taxonomy match) or "Content-Based" (new segment rows)
- `Original_Topic_1-5`: Topics from original taxonomy matching
- `Content_Topic_1-5`: Topics found by analyzing content (Summary, Description, Title, URL)
- `Content_Segment_1-3`: Segments derived from content analysis
- `Topics_Match`: Whether original and content-based topics agree

**Key method:**
- `find_topics_in_content()` - Extracts keywords from Summary/Description, fuzzy matches against taxonomy topics

## Remove Top Level Pages

The `remove_top_level_pages.py` script filters out "top level pages" from URL spreadsheets. Top level pages are pages on the `userdocs.wolterskluwer.co.uk` site that contain a MindTouch "Topic Hierarchy" template — these are navigation/landing pages, not content pages.

**Detection method:** Fetches each URL and checks if the page source contains the text "Topic Hierarchy" (appears in MindTouch template metadata as `templatePath: MindTouch/IDF3/Views/Topic_hierarchy`).

**Usage:**
```bash
python remove_top_level_pages.py -i input.xlsx -o output.xlsx
python remove_top_level_pages.py -i input.xlsx  # auto-names output with _no_top_level suffix
```

**CLI args:** `-i INPUT`, `-o OUTPUT`, `--tag TEXT` (default: "Topic Hierarchy"), `--workers N` (default: 10)

**Performance:** Uses 10 concurrent threads, ~15 URLs/sec. Full dataset of 2,648 unique URLs takes ~3 minutes.

**Output:** Two-sheet Excel file:
- **Content Pages** — rows where URL does NOT contain Topic Hierarchy (kept)
- **Removed Top Level** — rows where URL DOES contain Topic Hierarchy (for review)

**Typical results (GB dataset, Feb 2026):**
- Input: 6,036 rows (2,648 unique URLs)
- Top-level pages found: 293 unique URLs (11%)
- Rows removed: 574
- Rows kept: 5,462

**Error handling:** URLs that fail to fetch (timeouts, errors) are kept in the output (not removed). Errors are counted in progress output.

## Strict Content Match vs Taxonomy Matcher Analysis (9 Feb 2026)

Executive summary and side-by-side comparison reports were generated and are stored at:
- `C:\Users\Tony.Gilpin\Downloads\8thFeb\Strict_Content_Match_Executive_Summary.html` - Full executive summary with 12 interactive charts
- `C:\Users\Tony.Gilpin\Downloads\8thFeb\Taxonomy_Side_by_Side_Comparison.html` - Interactive product-by-product comparison with explainer

**Key findings from the analysis:**
- **Taxonomy:** 33 products, 62 segments, 294 topics (file: `C:\Users\Tony.Gilpin\Downloads\6thFeb\Latest Taxonomy 03-02-26 _6thFeb.xlsx`)
- **Strict match outputs (4 modes):** stored in `C:\Users\Tony.Gilpin\Downloads\8thFeb\`
- **Coverage:** Strict Match 100% vs Taxonomy Matcher 99.6% (2,648 URLs)
- **Topic richness:** 5.8 topics/URL (Strict) vs 1.3 (Taxonomy) = 4.5x more
- **Topic discovery:** 19,972 unique auto-topics vs 294 taxonomy topics (68x richer)
- **Taxonomy gaps:** 89 of 294 topics (30.3%) never matched any URL
- **Product overlap:** 26 products in both, 7 taxonomy-only, 30 auto-discovered
- **Segment expansion:** Auto-gen discovers 10x-33x more segments per product than taxonomy
- **Time savings:** 95% reduction in human effort (372 hrs/year vs 18.5 hrs/year)
- **Cost savings:** ~GBP17,675/year at GBP50/hr

**Strict match mode ranking (best to worst):**
1. All Options (Title+URL+Content+Crawl) - 100% coverage, 5.8 topics/URL, 3 ranks
2. No Crawl (Title+URL+Content) - 100% coverage, 5.5 topics/URL, 3 ranks
3. Crawl Only - 98.3% coverage, 5.3 topics/URL, 2 ranks
4. Summary/Description Only - 93.7% coverage, 4.6 topics/URL, 2 ranks

## Salesforce URL Converter

The `convert_salesforce_urls.py` script converts Salesforce Lightning internal URLs (from CSV exports) to public community URLs.

**Problem:** Salesforce exports contain internal href tags like `/lightning/articles/Knowledge/{slug}?language=nl_BE` which are not publicly accessible.

**Solution:** Converts to public URLs like `https://taasupport.wolterskluwer.be/customers/s/article/{slug}?language=nl_BE`

**Supported countries:**
| Country | Community Base URL |
|---------|-------------------|
| BE | `https://taasupport.wolterskluwer.be/customers/s/article` |
| NL | `https://wktaaeu.my.site.com/nlcommunity/s/article` |
| SE | `https://wktaaeu.my.site.com/se/s/article` |

**Usage:**
```bash
# Auto-detect country from filename
python convert_salesforce_urls.py -i crawl_results_nl_BE.csv

# Specify country explicitly
python convert_salesforce_urls.py -i export.csv -c NL

# Custom output path and URL column name
python convert_salesforce_urls.py -i export.csv -c SE -o converted.csv --column "Article URL"
```

**Output:** `{input}_public_urls.csv` (default) or custom path via `-o`

**Adding new countries:** Add the community base URL to `COMMUNITY_BASE_URLS` dict in `convert_salesforce_urls.py`.

**Programmatic usage:**
```python
from convert_salesforce_urls import convert_file
result = convert_file('input.csv', 'output.csv', 'BE')
print(f"Converted {result['converted']} URLs")
```

## Related Projects

| Project | Location | Running At | Purpose |
|---------|----------|------------|---------|
| **NLUrl v2.0** | `C:\url spreasheets\vs_projects\nlurlv2\` | localhost:5000 (dev) / localhost:8080 (prod) | Python/Flask web app. Crawls Salesforce community sites (NL, SE, BE) using Selenium/aiohttp. Extracts frequency-based 2-3 word keywords via n-gram analysis (NOT AI semantic). Outputs Excel with `Keyword 1-15`. Has CLI and Desktop GUI interfaces. |
| **vmcrawl** | (separate project) | localhost:3000 | Node.js/Playwright crawler for GB/UK userdocs.wolterskluwer.co.uk site. Extracts raw HTML and text content. Outputs Excel with URL, HTML, TXT, Title columns. |
| **NLMap v3.12** | `C:\url spreasheets\vs_projects\nlmapV3\` | — (desktop) | Python/Tkinter GUI. Takes output from either crawler. Fuzzy-matches keywords against taxonomy (rapidfuzz). Multi-country (NL, SE, BE, GB). Strict Content Match hidden in v3.12 due to poor quality. |

### Recommended Workflow for Belgium (BE) Data

**Best practice:** Use NLUrl crawler keywords instead of Strict Content Matcher

1. **Extract Keywords (NLUrl v2.0)**
   - Upload Salesforce Knowledge__kav CSV export
   - Crawler extracts Keyword 1-15 from Title/Summary/Description
   - Output: `crawl_results_{lang}.xlsx`

2. **Match to Taxonomy (NLMap v3.12)**
   - Use crawl_results as semantic file
   - CLI: `python taxonomy_matcher.py -c BE --semantic-file crawl_results_nl_BE.xlsx`
   - GUI: Setup tab → select files → Run
   - Output: `taxonomy_match_BE.xlsx`

3. **Post-Process (Optional)**
   - Clean and filter results
   - `python post_processor.py -i taxonomy_match_BE.xlsx --max-rank 3`

**Quality Comparison:**

| Metric | NLUrl Crawler | Strict Content Matcher |
|--------|--------------|------------------------|
| HTML contamination | 0.0% | 57.5% |
| Generic noise ("Customers", "Article") | 0.0% | 100% |
| Product identification | ✅ Correct | ❌ Uses titles |
| Domain relevance | ✅ High | ❌ Low |
| Usable for taxonomy | ✅ Yes | ❌ No |
| Example keywords | "expert m", "factur", "boekhoud" | "<b><u>vraag<", "Customers" |

**Recommendation:** Always use NLUrl crawler keywords when available. Only use Strict Content Matcher for URLs without pre-extracted keywords (e.g., GB userdocs site).

## Salesforce Export Workflow

**Standardized workflow for processing Salesforce Knowledge exports across all countries (BE, NL, SE, and future additions).**

### Overview

Going forward, Salesforce Knowledge exports are the standard format for all countries using Salesforce. The workflow supports two methods:
- **Method A (NLUrl):** Production quality with language-aware keyword extraction
- **Method B (Direct Import):** Convenience feature in NLMap for quick processing

Both methods handle the "482-column mess" from Salesforce exports automatically.

### CSV Format Requirements

**Typical Salesforce Knowledge CSV export:**
- 482+ columns (only first 6 useful, rest are HTML metadata)
- URLs in HTML anchor tags: `<a href="/lightning/articles/Knowledge/{slug}?language=nl_BE">...</a>`
- Essential columns: `Knowledge_Url__c`, `Title`, `Summary`, `Answer__c`/`Description`
- Auto-detection handles column variations and BOM

**Auto-handled issues:**
- ✅ 476+ junk columns (ignored)
- ✅ HTML anchor tag URLs (extracted)
- ✅ Lightning URLs (converted to public community URLs)
- ✅ BOM in headers (stripped)
- ✅ Different column orders (detected)

### Taxonomy Structure Requirements

**REQUIRED structure:**

| Column | Required | Description |
|--------|----------|-------------|
| `Product` | ✅ Yes | Single column with product name |
| `Domain` | ✅ Yes | Domain name |
| `Segment` | ✅ Yes | Segment name |
| `Topic 1` ... `Topic N` | ✅ Yes | Topics (any number, auto-detected) |

**If your taxonomy has `Product 1`, `Product 2`, etc. columns:**

```bash
# Convert to standard format (expands rows)
python restructure_taxonomy.py -i "Taxonomy BE.xlsx" -o "countries/BE/taxonomy.xlsx"
```

**Example conversion:**
```
INPUT (1 row):
Productfamily | Product 1           | Product 2            | Domain | Topic 1
Adsolut       | Adsolut boekhouding | Adsolut Jaarrekening | Welkom | Login

OUTPUT (2 rows):
Product               | Domain | Topic 1
Adsolut boekhouding   | Welkom | Login
Adsolut Jaarrekening  | Welkom | Login
```

### Method A: NLUrl + NLMap (Production Quality)

**Recommended for:** Production use, best keyword quality, language-aware extraction

**Workflow:**
```
Salesforce CSV → NLUrl web app → crawl_results_{lang}.xlsx → NLMap → taxonomy_match_{CODE}.xlsx
```

**Steps:**

1. **Upload to NLUrl** (`http://localhost:5000` or `localhost:8080`)
   - Select Salesforce Knowledge__kav CSV
   - (Optional) Enable "Auto-enrich with Content Topics"
   - Start crawl

2. **Download results**
   - `crawl_results_{lang}.xlsx` contains:
     - URL, Title, Summary, Description
     - Keyword 1-15 (frequency-based n-grams)
     - (Optional) Topic_1-6, Domain, Segment

3. **Match in NLMap**
   ```bash
   # CLI
   python taxonomy_matcher.py -c BE --semantic-file "crawl_results_nl_BE.xlsx"

   # GUI
   # Setup tab → select crawl_results as Semantic File → Run
   ```

**Quality metrics:**
- Keyword quality: 50.7% are 2-3 word phrases
- HTML contamination: 0%
- Generic noise: 0%
- Language-aware: Dutch/French/Swedish stopwords

### Method B: Direct Import in NLMap (Convenience)

**Recommended for:** Quick tests, no NLUrl access, single-tool workflow

**Workflow:**
```
Salesforce CSV → NLMap "Import SF CSV" → taxonomy_match_{CODE}.xlsx
```

**Steps:**

1. **Open NLMap GUI**
   ```bash
   python taxonomy_matcher_gui.py
   ```

2. **Import CSV**
   - Setup tab → Click "📥 Import SF CSV"
   - Select Salesforce CSV file
   - Select country code (BE, NL, SE)
   - (Optional) Select taxonomy for keyword ranking
   - Click "▶ Import CSV"

3. **Process runs automatically:**
   - Auto-detects columns (ignores 476 junk columns)
   - Extracts URLs from HTML anchor tags
   - Converts Lightning URLs to public format
   - Generates Keyword 1-12 from content
   - Creates `Semantic_{country}_{datetime}.xlsx`

4. **Match to taxonomy:**
   - Semantic file auto-populated
   - Click "Run Taxonomy Match"
   - Output: `taxonomy_match_{CODE}.xlsx`

**Quality metrics:**
- Keyword quality: Good (content-based extraction)
- HTML contamination: 0% (BeautifulSoup cleaning)
- Handles missing columns gracefully
- Faster than NLUrl for small datasets

### Quality Comparison

| Feature | Method A (NLUrl) | Method B (Direct Import) | Strict Match (Deprecated) |
|---------|------------------|--------------------------|---------------------------|
| **Keyword source** | Frequency n-grams | Content extraction | Page crawl |
| **Language-aware** | ✅ Yes | Partial | No |
| **Stopword filtering** | ✅ Language-specific | Generic | None |
| **HTML handling** | ✅ Multi-algorithm | BeautifulSoup | Poor (57% contamination) |
| **Keyword count** | 15 | 12 | 6 |
| **2-3 word phrases** | 50.7% | ~40% | N/A |
| **Generic noise** | 0% | <5% | 90%+ |
| **Processing time** | Medium (crawl) | Fast (columns) | Slow (crawl) |
| **Best for** | Production | Quick tests | ❌ Deprecated |

### Data_Categories__c Column Support (v3.13)

**Auto-detected from Salesforce Knowledge exports:**
- **Column:** `Data_Categories__c` (semicolon-separated product/topic categories)
- **Example:** `"Adsolut_Account;ExpertM_Plus;Briljant_Account"`
- **Mapped via:** `countries/{CODE}/category_mapping.json`

**Multi-Product Row Expansion:**

Input (1 URL with multiple categories):
```
URL: article-123
Data_Categories__c: "Adsolut_Account;ExpertM_Plus"
```

Output (2 rows after expansion):
```
Row 1: URL=article-123, Product="Adsolut boekhouden"
Row 2: URL=article-123, Product="ExpertM"
```

**Implementation Details:**
- **Mapping file:** `countries/BE/category_mapping.json`
  - 24 categories mapped to products
  - 8 special tags filtered (All_Products, Technisch, Arial, Known_Issues)
  - 40 unmapped categories use original name
- **Expansion timing:** Happens in `salesforce_csv_processor.py` before keyword extraction
- **Deduplication skip:** ContentKeywordExtractor skips URL deduplication when Product column exists
- **Belgium stats:** ~709 additional rows (1,809 unique URLs → 2,518 total rows)

**Critical Implementation (v3.13 Bug Fix):**

**Problem:** ContentKeywordExtractor always deduplicated by URL, destroying multi-product expansion

**Fix:** Skip deduplication when Product column present (`content_keyword_extractor.py` lines 701-714):
```python
if 'Product' in df.columns and df['Product'].notna().any():
    print("Product column detected - preserving multi-product rows")
    df_deduped = df  # NO deduplication
else:
    df_deduped = df.drop_duplicates(subset=['URL'], keep='first')
```

**Impact:** Multi-product articles now correctly generate multiple rows for taxonomy matching

### Quick Start Guide

#### New Country Setup (30 minutes)

1. **Prepare files:**
   - Salesforce CSV export
   - Taxonomy file (restructure if needed)
   - Community base URL

2. **Add to config.yaml:**
   ```yaml
   countries:
     XX:
       name: "Country Name"
       code: "XX"
       enabled: true
       files:
         semantic_carriers: "semantic_carriers_list.xlsx"
         taxonomy: "taxonomy.xlsx"
         synonyms: "synonyms.json"
       settings:
         similarity_threshold: 80
   ```

3. **Create directory:**
   ```bash
   mkdir countries\XX
   # Add: taxonomy.xlsx, synonyms.json (start with {"synonyms": {}})
   ```

4. **Add community URL** in `convert_salesforce_urls.py`:
   ```python
   COMMUNITY_BASE_URLS = {
       'XX': 'https://your-community.example.com/s/article',
   }
   ```

5. **Test workflow:**
   - Use Method B (Direct Import) for quick validation
   - Verify: URLs converted, keywords extracted, taxonomy matched
   - Match rate should be >50% (improves with synonyms)

**Complete guide:** See `SALESFORCE_COUNTRY_SETUP.md` for detailed step-by-step instructions.

### Community Base URLs (Current)

| Country | Base URL |
|---------|----------|
| BE (Belgium) | `https://taasupport.wolterskluwer.be/customers/s/article` |
| NL (Netherlands) | `https://wktaaeu.my.site.com/nlcommunity/s/article` |
| SE (Sweden) | `https://wktaaeu.my.site.com/se/s/article` |

**To find base URL for new country:**
1. Open published article in Salesforce
2. Click "View as Customer" / "Public Link"
3. Extract: `https://{domain}/s/article` (everything before `/{slug}`)

### Utilities Reference

| Utility | Purpose | Usage |
|---------|---------|-------|
| `restructure_taxonomy.py` | Convert Product 1-5 → Product column | `python restructure_taxonomy.py -i input.xlsx` |
| `convert_salesforce_urls.py` | Test Lightning → public URL conversion | `python convert_salesforce_urls.py -i input.csv -c BE` |
| `salesforce_csv_processor.py` | Process CSV (CLI mode) | `python salesforce_csv_processor.py -i input.csv -o output.xlsx -c BE` |

### Troubleshooting

**Issue: "No Product columns found" during restructure**

**Solution:** Your taxonomy already has correct structure (single `Product` column). Skip restructuring.

---

**Issue: URLs not converted (still `/lightning/...`)**

**Diagnosis:**
```bash
python convert_salesforce_urls.py -i input.csv -c BE -o test.csv
# Check console: "Converted: 0 URLs" vs expected count
```

**Possible causes:**
- Wrong community base URL
- CSV column doesn't contain URLs
- HTML parsing failed (missing beautifulsoup4)

**Fix:**
```bash
pip install beautifulsoup4  # If missing
# Verify community URL is correct
# Check CSV column contains <a href="/lightning/..."> or /lightning/...
```

---

**Issue: Match rate very low (<30%)**

**Diagnosis:** Check `Unmapped_Reason` column in output

**Common reasons:**
- "Product filter excluded" → Wrong product assignments
- "No matches above threshold" → Need more synonyms
- "No keywords extracted" → Content columns empty

**Fix:**
1. Review "Keyword Recommendations" sheet (HIGH priority)
2. Use Synonym Assistant to add recommended synonyms
3. Re-run matching (should improve 10-20%)
4. Iterate 2-3 times for optimal results

---

**Issue: Keywords are generic ("customers", "article")**

**Solution:** Use Method A (NLUrl) instead of Strict Match. NLUrl has language-specific stopword filtering and produces 0% generic noise.

---

**Issue: Multi-product rows lost (output has fewer rows than expected)**

**Symptom:** Import shows "Multi-product expansion: +709 rows" but final output has only 1,809 rows

**Diagnosis:**
```python
import pandas as pd
df = pd.read_excel("output.xlsx")
url_counts = df['URL'].value_counts()
multi = url_counts[url_counts > 1]
print(f"Multi-product URLs: {len(multi)}")  # Should be >0 for Belgium
```

**Root Cause:** ContentKeywordExtractor deduplicated by URL despite Product column

**Fix:** Verify `content_keyword_extractor.py` lines 701-714 has deduplication skip logic:
```python
if 'Product' in df.columns and df['Product'].notna().any():
    df_deduped = df  # Skip deduplication
```

**Expected:** 1,809 unique URLs → 2,518 total rows (709 multi-product)

---

**Issue: Product column has garbage (HTML, font names, random text)**

**Symptom:** Product values like `"Roboto"`, `"sans-serif"`, `"<p>blijft dus..."`, `"00 euro..."`

**Diagnosis - Check temp file:**
```bash
# Look for: _temp_semantic_*.xlsx in output directory
# If temp file Product is correct but output is wrong → ContentKeywordExtractor issue
# If temp file Product has garbage → salesforce_csv_processor issue
```

**Root Cause:** Product column not preserved correctly through keyword extraction

**Fix:** Verify `content_keyword_extractor.py` lines 751-761 preserves Product unconditionally:
```python
if 'Product' in df.columns:
    product_val = row.get('Product') if pd.notna(row.get('Product')) else ''
    output_row['Product'] = product_val
```

**Expected:** Clean product values from `category_mapping.json`: "Adsolut boekhouden", "ExpertM", "Fiscaal dossier"

### Version History

| Version | Date | Changes |
|---------|------|---------|
| v3.13 | 2026-02-13 | Added Salesforce CSV Import feature, restructure_taxonomy.py utility, SALESFORCE_COUNTRY_SETUP.md guide |
| v3.12 | 2026-02-11 | Hidden Strict Match (poor quality for Salesforce data) |
| v3.11 | 2026-02-11 | Domain & Segment Editor |

### Future: NLUrl + NLMap Merge

NLUrl and NLMap are planned to merge into a single application. Currently NLUrl already imports `StrictContentMatcher` from NLMap for topic enrichment, and both share country config (`countries/{CODE}/domains.json`, `segments.json`, `synonyms.json`). A merged tool would provide a single UI for crawling, keyword extraction, taxonomy matching, strict content matching, and domain/segment/synonym editing — eliminating the need to pass Excel files between two separate apps.

### Data Pipeline

```
Salesforce sites (NL, SE, BE):
  Method A (Production):
    NLUrl (localhost:5000) → crawl_results_{lang}.xlsx (Keywords + Summary + Description) → NLMap (taxonomy match)
    NLUrl + Topic Enrichment → enriched Excel (Keywords + Topics + Domains + Segments)

  Method B (Direct Import - v3.13):
    CSV (482 cols) → NLMap "Import SF CSV" → Semantic_{CODE}.xlsx (Data_Categories products) → taxonomy_match_{CODE}.xlsx
    Benefits: One-click, multi-product support, 77% articles get products from Data_Categories__c

GB/UK userdocs site:
  vmcrawl (localhost:3000) → scraped_results.xlsx (raw content) → NLMap (taxonomy match or strict content match)
```

### NLUrl v2.0 Updates (Feb 11, 2026)

**CSV Column Auto-Detection:**
- Automatically detects column structure (Knowledge_Url__c, Title, Summary, Answer__c, Description)
- Handles different Salesforce CSV export formats
- Strips BOM (byte order mark) from headers
- Generates placeholder URLs if URL column is missing
- Shows clear warnings for unexpected column structures

**Version Display:**
- Navbar badge: "v2.0"
- Footer: Full version, date, and release notes
- Context processor injects version into all templates automatically

**Bug Fixes:**
- Fixed URL corruption when CSV has different column order (Title was appearing in URL column)
- Enhanced content column detection (added 'description' alongside 'answer', 'body', 'content')

**Keyword Extraction Method:**
- Source: Title, Meta Description, Summary, Description columns
- Method: Frequency-based n-gram extraction (NOT AI semantic)
- Headings (H1-H6), Bold text (`<strong>`, `<b>`) - high priority
- Bigrams (2-word), Trigrams (3-word), 4-grams - most common phrases
- Stopword filtering, deduplication, optional stemming
- Quality: 50.7% are 2-word phrases, 0% HTML contamination, 0% generic noise

### NLUrl Topic Enrichment Integration (Feb 2026)

NLUrl imports `StrictContentMatcher` from NLMap to enrich crawl output with content-based topics. NLMap itself is not modified.

**Key files in NLUrl:**

| File | Purpose |
|------|---------|
| `backend/topic_enricher.py` | Bridge: imports StrictContentMatcher from NLMap, enriches crawl output Excel |
| `webapp/app.py` | Routes: `/upload_csv`, `/enrich`, `/enrich_stream`, `/download_enriched`; auto-enrich flag |
| `webapp/templates/results.html` | "Enrich with Topics" button, enrichment stats, enriched file download |
| `webapp/templates/index.html` | "Auto-enrich with Content Topics" checkbox in Advanced Options |
| `webapp/static/js/progress.js` | Handles 'enriching' status during auto-enrichment |
| `smart_crawler_multi.py` | `save_to_excel()`/`save_to_csv()` include Summary + Description columns (CSV mode) |
| `backend/crawler_wrapper.py` | `_run_csv_mode()` carries CSV Summary (row[3]) and Answer__c (row[4]) through to output |

**CSV mode data flow:**
```
CSV File (Knowledge__kav)
  Column 2: Title         → Excel "Title"
  Column 3: Summary       → Excel "Summary"
  Column 4: Answer__c     → Excel "Description" (first 5000 chars)
  Answer__c body          → Keywords via n-gram extraction → Excel "Keyword 1-15"

TopicEnricher reads Excel output:
  Title       → extract main topic (_clean_title_to_topic)
  URL         → parse path segments (_extract_url_topics)
  Summary     → extract 2-3 word phrases (_extract_topic_phrases)
  Description → extract 2-3 word phrases (_extract_topic_phrases)
  → Enriched Excel: original columns + Product_Auto, Domain, Segment, Topic_1..6, Source_1..6, Top_Relevance
```

**Two enrichment modes:**
1. **Manual:** Crawl → results page → click "Enrich with Topics" button → progress bar → download enriched Excel
2. **Auto:** Check "Auto-enrich" before crawling → enrichment runs automatically after crawl → results page shows stats + download

**Required packages (NLUrl):** flask, waitress, pandas, rapidfuzz, PyYAML, aiohttp, beautifulsoup4, lxml, rich, openpyxl, nltk, stop-words

**To run NLUrl:**
```bash
cd "C:\url spreasheets\vs_projects\nlurlv2\webapp"
python app.py          # Dev server at localhost:5000
python run_webapp.py   # Production server at localhost:8080
```
