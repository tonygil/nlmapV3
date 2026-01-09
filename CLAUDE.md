# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**NL Taxonomy Mapper V3** is a Python application that maps URLs from semantic carriers to topics in a taxonomy structure using fuzzy string matching. **NEW IN V3**: Multi-country support (NL, SE, BE, GB) with language-specific synonyms and external configuration.

### Core Purpose
Maps keywords extracted from URLs (Keyword 1-10) to hierarchical taxonomy topics (Product → Domain → Segment → Topic) using configurable fuzzy matching with auto-deduplication. **V3 enables processing for multiple countries without code changes.**

### What's New in V3

**Multi-Country Support:**
- Country selection via GUI dropdown, CLI arguments, or config file
- Separate taxonomy and synonym files per country
- Auto-appended country codes to output filenames (e.g., `taxonomy_match_NL.xlsx`)
- Backward compatible with existing NL files in root directory

**External Configuration:**
- `config.yaml` - Country registry and settings
- `countries/{CODE}/synonyms.json` - Language-specific synonyms (no longer hardcoded)
- `country_config.py` - Configuration loader module

**Supported Countries (Extensible):**
- **NL** - Netherlands (Dutch)
- **SE** - Sweden (Swedish)
- **BE** - Belgium (Dutch/French)
- **GB** - United Kingdom (English)
- *Add more by editing config.yaml - no code changes needed*

### What's New in V3.1

**Topic Consolidation Feature:**
- Optional consolidation mode: one row per URL-Segment with topics as columns (Topic_1, Topic_2, etc.)
- Reduces output size by ~50% (e.g., 636 rows → 309 rows)
- Segment names excluded from Topic columns (remain in Segment column only)
- Configurable via CLI flag (`--consolidate-topics`), GUI checkbox, or config.yaml
- Default: OFF (backward compatible with one-row-per-topic format)

## Development Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Required packages: pandas, openpyxl, fuzzywuzzy, python-Levenshtein, PyYAML
```

### Running the Application

**GUI Mode (Recommended):**
```bash
python taxonomy_matcher_gui.py

# Or use Windows launcher:
launch_gui.bat

# In GUI: Select country from dropdown, files auto-populate
```

**CLI Mode with Country Selection:**
```bash
# Use default country (NL)
python taxonomy_matcher.py

# Specify country with consolidation
python taxonomy_matcher.py -c SE -t 80 --consolidate-topics

# See all options
python taxonomy_matcher.py --help

# CLI Arguments:
# -c, --country COUNTRY           Country code (NL, SE, BE, etc.)
# -t, --threshold THRESHOLD       Similarity threshold (50-100)
# --semantic-file FILE            Override semantic carriers file path
# --taxonomy-file FILE            Override taxonomy file path
# -o, --output FILE               Output filename (country code auto-appended)
# -ct, --consolidate-topics       Consolidate topics into columns (V3.1)
```

### Testing
No formal test suite currently exists. Manual testing workflow:

**Test with NL (backward compatibility):**
1. Ensure legacy files exist in root: `semantic_carriers_list.xlsx` and `NL Taxonomy V2.xlsx`
2. Run: `python taxonomy_matcher.py -c NL -t 80`
3. Verify output: `taxonomy_match_NL.xlsx` created
4. Check expected results: ~350-450 rows from 231 URLs, ~92% match rate

**Test new country:**
1. Add data files to `countries/{CODE}/`
2. Run: `python taxonomy_matcher.py -c {CODE} -t 80`
3. Verify country-specific output file created

**Test GUI:**
1. Launch: `python taxonomy_matcher_gui.py`
2. Verify country dropdown shows all configured countries (NL, SE, BE, GB)
3. Switch countries and verify file paths auto-populate
4. Run matching and verify Console tab shows progress

## Architecture

### Core Components

**taxonomy_matcher.py** - Core matching engine (CLI)
- `TaxonomyMatcher` class: Main processing logic with country support
- Constructor parameters: `country_code`, `semantic_file`, `taxonomy_file`, `output_file`, `similarity_threshold`, `consolidate_topics`
- Fuzzy string matching using `fuzzywuzzy` library with Levenshtein distance
- Synonym expansion from JSON files (language-specific)
- Deduplication logic prevents duplicate URL-Topic pairs
- Auto-adds Segment as Topic when any topic from that segment matches (in non-consolidated mode)
- Topic consolidation: `consolidate_results()` method groups by (URL, Product, Domain, Segment)
- CLI with argparse: `-c`, `-t`, `--semantic-file`, `--taxonomy-file`, `-o`, `-ct`

**taxonomy_matcher_gui.py** - GUI application
- Tkinter-based interface with tabbed layout (Setup, Console, About)
- Country/Language dropdown selector (auto-populates file paths)
- Topic consolidation checkbox with [ON]/[OFF] status indicator (V3.1)
- Window size: 1000x850 (optimized for full visibility without scrolling)
- Threading for non-blocking UI during processing
- Real-time progress tracking and console logging
- File selection dialogs for input/output
- Event binding: `selected_country.trace()` triggers `on_country_changed()`

**country_config.py** - Configuration loader (NEW in V3)
- `CountryConfig` class: Loads and validates config.yaml
- Methods: `get_available_countries()`, `get_country_files()`, `load_synonyms()`, `get_country_settings()`
- Handles backward compatibility for NL legacy files in root
- Validates file existence before processing
- Returns absolute paths using pathlib for cross-platform compatibility

### Key Architecture Patterns

**Multi-Country Configuration (V3):**
- Three-tier selection: CLI args > GUI dropdown > config.yaml > default (NL)
- Country-specific file paths resolved via `country_config.get_country_files()`
- Backward compatibility: NL checks root for legacy files before `countries/NL/`
- Synonyms loaded dynamically from JSON files per country (not hardcoded)
- Output filenames auto-append country code: `taxonomy_match_{CODE}.xlsx`

**Flat Taxonomy Lookup Structure:**
- Taxonomy file has hierarchical rows (Product → Domain → Segment → Topic 1-6)
- Build phase flattens to list of dicts: `{'product', 'domain', 'segment', 'topic'}`
- Each topic becomes a separate searchable entry
- This enables efficient keyword-to-topic matching without nested loops

**Synonym Expansion:**
- Keywords expanded with synonyms BEFORE matching
- Synonyms loaded from `countries/{CODE}/synonyms.json` at initialization
- Each keyword generates multiple variations (e.g., 'bankzaken' → ['bankzaken', 'bank', 'banken', 'bankafschriften'])
- All variations compared against each topic; highest score wins
- Improves recall without sacrificing precision
- Missing synonym files gracefully degrade to empty dict (app continues)

**Auto-Segment Addition (Non-Consolidated Mode Only):**
- When ANY topic from a taxonomy row matches, also add that row's Segment as a separate topic
- Prevents loss of hierarchical information in one-row-per-topic output
- Example: If "Bankboekingsinstructies" matches → also add "Bankzaken" as topic
- Tracked in `matched_segments` set to avoid duplicates
- NOTE: In consolidated mode, segments are filtered OUT of Topic columns (V3.1)

**Deduplication Strategy:**
- Use set of tuples: `(URL, Product, Domain, Segment, Topic)`
- Multiple keywords may match same topic → only one output row
- Same URL can appear multiple times for DIFFERENT topics
- Prevents combinatorial explosion of duplicate matches

**Topic Consolidation (V3.1):**
- Optional post-processing step after matching completes
- Groups results by `(URL, Product, Domain, Segment)` tuple
- Spreads topics across columns: Topic_1, Topic_2, Topic_3, etc.
- Filters out segment names from Topic columns (segments stay in Segment column)
- Dynamic column count based on max topics per URL-Segment group
- Preserves discovery order (topics appear in order they were matched)
- Priority: CLI `--consolidate-topics` > GUI checkbox > country setting > global default (False)
- Reduces output size by ~50% while preserving all information

### Data Flow (V3)
```
1. Initialize:
   - Load config.yaml via CountryConfig
   - Determine country (CLI arg > GUI selection > config default)
   - Load country-specific synonyms from JSON
   - Resolve file paths (with backward compat check for NL)

2. Load Excel files → pandas DataFrames
   - semantic_carriers_list.xlsx (or country-specific path)
   - taxonomy.xlsx (or country-specific path)

3. Flatten taxonomy → List[Dict] lookup structure

4. For each URL:
   - Extract keywords (Keyword 1-10)
   - For each keyword:
     - Expand with country-specific synonyms
     - Compare against all topics using fuzzy matching
     - Record matches above threshold
   - Auto-add segments for matched topics
   - Deduplicate URL-Topic combinations

5. Apply optional consolidation:
   - If consolidate_topics enabled, group by (URL, Product, Domain, Segment)
   - Filter segment names from Topic columns
   - Spread topics across Topic_1, Topic_2, etc.

6. Export to Excel
   - Output filename: taxonomy_match_{COUNTRY_CODE}.xlsx
   - Format: one-row-per-topic (default) or consolidated (if enabled)
```

### Configurable Parameters

**Similarity Threshold (50-100):**
- Default: 80% (configurable per country in config.yaml)
- GUI: Adjustable via slider (50-100%)
- CLI: `-t` argument or interactive prompt
- config.yaml: Set per country in `settings.similarity_threshold`
- Priority: CLI arg > country setting > global default (80)
- Affects precision/recall tradeoff

**Synonyms (V3):**
- Location: `countries/{CODE}/synonyms.json` (external files, not in code)
- Format: `{"synonyms": {"main_term": ["synonym1", "synonym2"]}}`
- Loaded dynamically at runtime via `CountryConfig.load_synonyms()`
- Language-specific: NL (Dutch), SE (Swedish), BE (Dutch/French), GB (English)
- Missing files gracefully handled (empty dict, app continues)

**Topic Consolidation (V3.1):**
- Default: False (one-row-per-topic output)
- GUI: Checkbox with [ON]/[OFF] status indicator in Setup tab
- CLI: `--consolidate-topics` or `-ct` flag
- config.yaml: `global_settings.consolidate_topics` or per-country override
- Priority: CLI arg > GUI checkbox > country setting > global default

### Important Implementation Details

**Keyword Extraction:**
- Looks for columns named "Keyword 1" through "Keyword 10"
- Handles missing keywords gracefully with `pd.notna()` checks

**Topic Detection:**
- Dynamically detects "Topic" columns via `col.startswith('Topic')`
- Supports 1-6 topics per taxonomy row (flexible schema)

**Progress Reporting:**
- CLI: Prints every 50 URLs
- GUI: Threading with queue-based logging to avoid UI blocking

**Unmapped URLs:**
- URLs with no matches are included in output with Domain='UNMAPPED'
- Enables review of unmatched content

## File Structure (V3)

```
nlmapV3/
├── countries/                   # Country-specific data (V3)
│   ├── NL/                     # Netherlands
│   │   ├── semantic_carriers_list.xlsx  # URL keywords (optional if using root legacy files)
│   │   ├── taxonomy.xlsx       # NL taxonomy structure (optional)
│   │   └── synonyms.json       # Dutch synonyms (REQUIRED)
│   ├── SE/                     # Sweden
│   │   ├── semantic_carriers_list.xlsx
│   │   ├── taxonomy.xlsx
│   │   └── synonyms.json       # Swedish synonyms
│   ├── BE/                     # Belgium
│   │   ├── semantic_carriers_list.xlsx
│   │   ├── taxonomy.xlsx
│   │   └── synonyms.json       # Belgian synonyms (Dutch/French)
│   └── GB/                     # United Kingdom
│       ├── semantic_carriers_list.xlsx
│       ├── taxonomy.xlsx
│       └── synonyms.json       # UK English synonyms
│
├── config.yaml                  # Country registry & settings (REQUIRED)
├── country_config.py            # Configuration loader module
│
├── taxonomy_matcher.py          # Core matching engine with CLI
├── taxonomy_matcher_gui.py      # Tkinter GUI with country selector
├── launch_gui.bat               # Windows launcher script
├── requirements.txt             # Python dependencies (pandas, openpyxl, fuzzywuzzy, python-Levenshtein, PyYAML)
│
├── semantic_carriers_list.xlsx  # LEGACY: Backward compat for NL only
├── NL Taxonomy V2.xlsx          # LEGACY: Backward compat for NL only
└── taxonomy_match_{CODE}.xlsx   # Output files (auto-named by country code)
```

## Common Modification Patterns (V3)

### Adjusting Match Threshold
**Via config.yaml (Recommended):**
```yaml
countries:
  NL:
    settings:
      similarity_threshold: 85  # Change per country
```

**Via CLI:**
```bash
python taxonomy_matcher.py -c NL -t 85
```

**Via GUI:**
Use the threshold slider in the Setup tab (50-100%)

### Adding New Synonyms
**Edit the country's JSON file** (e.g., `countries/NL/synonyms.json`):
```json
{
  "synonyms": {
    "new_term": ["variant1", "variant2"],
    "existing_term": ["synonym1", "synonym2"]
  }
}
```

**No code changes needed** - synonyms are loaded from JSON files

### Adding a New Country
**1. Edit config.yaml:**
```yaml
countries:
  DE:
    name: "Germany"
    language: "German"
    code: "DE"
    enabled: true
    files:
      semantic_carriers: "semantic_carriers_list.xlsx"
      taxonomy: "taxonomy.xlsx"
      synonyms: "synonyms.json"
    settings:
      similarity_threshold: 80
```

**2. Create directory:**
```bash
mkdir -p countries/DE
```

**3. Add country files:**
- `countries/DE/semantic_carriers_list.xlsx`
- `countries/DE/taxonomy.xlsx`
- `countries/DE/synonyms.json` (can start with `{"synonyms": {}}`)

**4. Test:**
```bash
python taxonomy_matcher.py -c DE
```

**No code changes required!** The country appears automatically in GUI dropdown.

### Changing Fuzzy Matching Algorithm
Currently uses `fuzz.partial_ratio()` (line 127). Alternatives:
- `fuzz.ratio()` - Strict full string comparison
- `fuzz.token_sort_ratio()` - Word order independent
- `fuzz.token_set_ratio()` - Handles subset matches

### Modifying Output Columns
Edit `taxonomy_matcher.py` around lines 224-230 in `process_matching()` to add/remove columns in results dict.

### Important V3 Implementation Notes

**Backward Compatibility Logic (country_config.py lines 73-90):**
- NL country first checks if `check_root_for_legacy: true` in config.yaml
- If true, checks for `semantic_carriers_list.xlsx` and `NL Taxonomy V2.xlsx` in root
- If both legacy files exist, uses them instead of `countries/NL/` files
- Synonym file always loaded from `countries/NL/synonyms.json` regardless

**File Path Resolution:**
- Uses `pathlib.Path` for cross-platform compatibility
- Returns absolute paths from `get_country_files()`
- Missing synonym files log warning but don't crash (graceful degradation)
- Missing semantic/taxonomy files raise clear error messages

**GUI Event Binding:**
- `selected_country.trace('w', on_country_changed)` watches dropdown changes
- `on_country_changed()` auto-populates file paths when country switches
- Output filename auto-updated to include new country code
- File paths only updated if empty or contain default values (respects manual selections)

**Error Handling:**
- Invalid country code: Raises ValueError with list of available countries
- Missing config.yaml: Clear error message at startup
- Invalid YAML syntax: Caught and reported
- Missing data files: File-not-found errors before processing starts
- GUI config load failure: Shows messagebox and gracefully exits

## Expected Results & Performance

- **Processing Time:** 30-60 seconds for 231 URLs
- **Match Rate:** ~92% of URLs (threshold dependent)
- **Output Rows:** 350-450 rows (multiple topics per URL)
- **Comparisons:** ~108,000 (231 URLs × 10 keywords × ~47 topics)
- **Memory:** ~50-100 MB

## Input/Output Specifications

**semantic_carriers_list.xlsx:**
- Required columns: URL, Keyword 1-10
- Optional columns: Title, Word Count, Meta Description
- 231 rows expected

**NL Taxonomy V2.xlsx:**
- Required columns: Product, Domain, Segment, Topic 1-6
- 33 taxonomy entries → 54 unique topics

**taxonomy_match.xlsx (output):**

*Default format (one-row-per-topic):*
- Columns: URL, Product, Domain, Segment, Topic
- One row per unique URL-Topic match
- Unmapped URLs have Domain='UNMAPPED'

*Consolidated format (V3.1, when enabled):*
- Columns: URL, Product, Domain, Segment, Topic_1, Topic_2, Topic_3, ..., Topic_N
- One row per unique URL-Segment combination
- Topics spread across columns in discovery order
- ~50% fewer rows than default format
- Segment names do NOT appear in Topic columns

## Common Issues & Troubleshooting

### Data Quality Issues

**Single-letter or truncated topics in output:**
- CAUSE: Taxonomy file contains invalid data (e.g., single letter "t" instead of full topic name)
- SOLUTION: Open taxonomy file in Excel, search for suspicious short values (1-2 characters) in Topic columns
- FIX: Replace or delete invalid entries in source taxonomy file
- Example: Row with Topic 2 = "t" should be deleted or replaced with full topic name

**Segment names appearing as topics:**
- In V3.1 consolidated mode, segments are automatically filtered from Topic columns
- In non-consolidated mode, segments ARE intentionally added as topics for hierarchical preservation
- This is expected behavior in default (one-row-per-topic) mode

### GUI Issues

**Consolidation checkbox hard to see:**
- V3.1 includes [ON]/[OFF] status indicator in green/red next to checkbox
- Checkbox uses white background for better visibility
- Window size: 1000x850 ensures all controls visible without scrolling

**Window doesn't fit on screen:**
- Default size optimized for 1080p displays
- Window is resizable - drag corners to adjust
- Content should be fully visible without scrolling in Setup tab

### Performance Issues

**Slow processing (>2 minutes for 231 URLs):**
- Install python-Levenshtein for faster fuzzy matching: `pip install python-Levenshtein`
- Reduce similarity threshold (processes faster but less accurate)
- Check for large synonym files (>100 terms can slow matching)

### Configuration Issues

**Country not appearing in GUI dropdown:**
- Verify country added to config.yaml with `enabled: true`
- Check YAML syntax (indentation must be correct)
- Ensure country code is uppercase in config (NL, SE, BE, GB)
- Restart GUI after modifying config.yaml

**Files not found errors:**
- For new countries, ensure all three files exist in `countries/{CODE}/` directory
- Synonym file is REQUIRED (can be empty: `{"synonyms": {}}`)
- Check file paths are relative to countries/{CODE}/ directory
- For NL: checks root directory first for backward compatibility
