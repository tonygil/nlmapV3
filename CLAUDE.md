# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference (Critical Facts)

⚠️ **MUST KNOW before modifying code:**
1. **Product column in semantics file is NOT used** - output Product/Domain/Segment come from taxonomy matches only
2. **Output is always consolidated** - one row per URL-Segment with Topic_1, Topic_2, etc. columns
3. **No auto-segment addition** - only topics from taxonomy file appear in output
4. **Topics are never created** - all topics must exist in taxonomy Topic columns
5. **Synonyms affect matching** - control which taxonomy topics match by editing `countries/{CODE}/synonyms.json`

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

**Topic Consolidation (Always Enabled):**
- **Output format**: One row per URL-Segment with topics as columns (Topic_1, Topic_2, etc.)
- Reduces output size by ~50% compared to one-row-per-topic format
- Segment names excluded from Topic columns (remain in Segment column only)
- Always enabled by default in config.yaml (`consolidate_topics: true`)
- CLI flag `--consolidate-topics` can override if needed

**File Validation System (Jan 2026):**
- **Instant validation** - Files validated immediately when selected
- **Visual indicators** - ✓ green (valid), ✗ red (invalid), ⚠ yellow (swapped)
- **Smart detection** - Identifies 4 file types: semantic, taxonomy, output, unknown
- **Output file protection** - Prevents using mapping results as input
- **Auto-swap detection** - Detects swapped files with one-click fix button
- **Hover tooltips** - Detailed validation messages on icon hover

**UI Improvements (Jan 2026):**
- **Modern progress bar** - Moved to same row as Run Matching button
- **Beautiful styling** - Green gradient with smooth animations
- **Status indicators** - "⚙ Processing..." → "✓ Completed successfully!"
- **Enhanced buttons** - Added ▶ and ↻ icons

**IMPORTANT CHANGES (Jan 2026):**
- **Auto-segment addition REMOVED**: Segments are no longer automatically added as separate topics
- Fixed consolidation logic to preserve all URL-Segment combinations
- Consolidation now filters out segment-as-topic entries (line ~324-325)
- Rows with zero topics after filtering are skipped (line ~327-329)

### What's New in V3.2

**Reports Tab (Jan 2026):**
- **New GUI tab**: "Reports" tab added between Synonym Editor and About
- **Synonym Report Generator**: Compares semantic keywords with taxonomy topics
- **Output**: 5-sheet Excel report with proposed synonym mappings
- **Purpose**: Helps identify missing synonyms to improve match rates

**Synonym Report Output (5 Sheets):**
1. **All Proposed Synonyms** - Topic, Product, Proposed_Synonym, Match_Score, Keyword_Frequency, Priority, Already_Added
2. **HIGH Priority** - Filtered to score ≥85% and frequency ≥50
3. **Summary by Topic** - Aggregated view of proposals per topic
4. **NEW Only** - Only synonyms NOT yet in synonyms.json (for quick review)
5. **Unmapped Keywords** - High-frequency keywords with no matching topic

**Already_Added Column:** Shows "Yes" or "No" indicating if the proposed synonym already exists in the country's synonyms.json file. This helps avoid adding duplicates and shows progress.

**Synonym Editor Improvements (Jan 2026):**
- **Bulk Import**: New button to paste multiple synonyms at once
- Dialog with text area for copy/paste (one synonym per line)
- "Paste from Clipboard" button for quick import
- Automatic duplicate detection and skipping
- Status feedback showing imported/skipped counts
- **Safety improvements** (critical fixes):
  - `get_synonyms_dict()` helper prevents orphaned dict references that caused data loss
  - Atomic file writes prevent corruption if crash occurs during save
  - Null checks on `current_synonym_file` prevent crashes
  - Auto-updates `total_mappings` and `last_updated` metadata on save
  - Data validation before save ensures `synonyms` key exists and is valid

**Bug Fixes (Jan 2026):**
- **Product filter cross-matching** (CRITICAL FIX): Fixed overly strict Product filtering that blocked valid matches
  - Before: URLs could only match topics from their exact Product (e.g., "CCH Accounts Production" URLs couldn't match "General" topics)
  - After: URLs can match topics from empty-Product rows (shared/generic topics) and their exact Product
  - Impact: Match rate improved from 64% to 95%+ (e.g., 742 unmapped → 98 unmapped)
  - Location: `should_match_product()` method in `taxonomy_matcher.py` (lines 167-195)
- **Bidirectional synonym matching** (CRITICAL FIX): Fixed bug where synonyms weren't mapping keywords to topics
  - Before: Only expanded keywords if they contained the topic name (e.g., "Documents overview" → added synonyms)
  - After: Also maps keywords that match synonyms back to their topic (e.g., "document management" → matches "Documents" topic)
  - Impact: Match rate improved from 45.6% to 60.1% (+573 URLs matched)
  - Location: `expand_with_synonyms()` method in `taxonomy_matcher.py` (lines 132-165)
- **Case-sensitive synonym matching**: Fixed bug where synonyms with different case weren't matching
  - Before: `"Workflow"` wouldn't match `"workflow optimization"`
  - After: Case-insensitive comparison
  - Impact: ~1.5% more URLs matched after fix

## Development Commands

### Setup

**Option 1: Virtual Environment (Recommended for multi-user servers)**
```bash
# Run setup script (creates venv with all dependencies)
setup_environment.bat

# Or manually:
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

**Option 2: System Python**
```bash
pip install -r requirements.txt
```

**Required packages:** pandas, openpyxl, fuzzywuzzy, python-Levenshtein, PyYAML

### Running the Application

**GUI Mode (Recommended):**
```bash
python taxonomy_matcher_gui.py

# Or use Windows launcher (V3.2 - improved):
launch_gui.bat
# - Auto-finds Python in PATH, py launcher, or common install locations
# - Clear error messages if Python not found
# - Auto-navigates to correct directory

# In GUI: Select country from dropdown, files auto-populate
```

**CLI Mode with Country Selection:**
```bash
# Use default country (NL)
python taxonomy_matcher.py

# Specify country and threshold
python taxonomy_matcher.py -c SE -t 80

# See all options
python taxonomy_matcher.py --help

# CLI Arguments:
# -c, --country COUNTRY           Country code (NL, SE, BE, etc.)
# -t, --threshold THRESHOLD       Similarity threshold (50-100)
# --semantic-file FILE            Override semantic carriers file path
# --taxonomy-file FILE            Override taxonomy file path
# -o, --output FILE               Output filename (country code auto-appended)
# -ct, --consolidate-topics       Consolidation (always ON by default)
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

**Test Reports Tab (V3.2):**
1. Launch GUI and select semantic and taxonomy files in Setup tab
2. Navigate to Reports tab
3. Click "Generate Synonym Report" button
4. Select output location in save dialog
5. Verify Excel file created with 5 sheets:
   - All Proposed Synonyms (should have rows, includes Already_Added column)
   - HIGH Priority (filtered subset)
   - Summary by Topic
   - NEW Only (synonyms not yet in synonyms.json)
   - Unmapped Keywords
6. Verify status shows "Report generated successfully!"
7. Verify Already_Added column correctly shows "Yes" for existing synonyms

### Building Standalone Executable

**One-click build:**
```bash
build.bat
```

This creates `dist\NLMap_V3\` folder containing:
- `NLMap_V3.exe` - Main application
- `config.yaml` - Editable settings (must be alongside exe)
- `countries\` - Editable synonyms and data files

**Requirements:**
- PyInstaller (auto-installed by build.bat if missing)

**Distribution:**
- Copy the entire `dist\NLMap_V3\` folder
- Users can edit `config.yaml` and `countries\*.json` without recompiling
- Code changes require running `build.bat` again

**Path Resolution (country_config.py):**
- `get_application_path()` checks: PyInstaller bundle → exe directory → script directory
- Config files must be next to the exe, not bundled inside it

## Architecture

### Core Components

**taxonomy_matcher.py** - Core matching engine (CLI)
- `TaxonomyMatcher` class: Main processing logic with country support
- Constructor parameters: `country_code`, `semantic_file`, `taxonomy_file`, `output_file`, `similarity_threshold`, `consolidate_topics`
- Fuzzy string matching using `fuzzywuzzy` library with Levenshtein distance
- Synonym expansion from JSON files (language-specific)
- Deduplication logic prevents duplicate URL-Topic pairs
- **NO auto-segment addition** - only matches topics from taxonomy file
- Topic consolidation: `consolidate_results()` method groups by (URL, Product, Domain, Segment)
- CLI with argparse: `-c`, `-t`, `--semantic-file`, `--taxonomy-file`, `-o`, `-ct`

**taxonomy_matcher_gui.py** - GUI application
- Tkinter-based interface with tabbed layout (Setup, Console, Synonym Editor, **Reports**, About)
- Country/Language dropdown selector (auto-populates file paths)
- **File validation system** - Instant validation with visual indicators (✓✗⚠)
- **Output always consolidated** - no checkbox needed (simplified UI)
- Window size: 1000x850 (optimized for full visibility without scrolling)
- Threading for non-blocking UI during processing
- Modern progress bar with status text next to Run Matching button
- Real-time progress tracking and console logging
- File selection dialogs for input/output
- Event binding: `selected_country.trace()` triggers `on_country_changed()`
- **File validation components** (lines 71-223):
  - `validate_semantic_file()` - Validates semantic carriers structure
  - `validate_taxonomy_file()` - Validates taxonomy structure
  - `detect_file_swap()` - Detects swapped files
  - `ToolTip` class - Hover tooltips for validation messages
- **Reports tab components** (V3.2):
  - `create_reports_tab()` - Creates Reports tab UI with generate button
  - `generate_synonym_report()` - Generates 5-sheet Excel report comparing keywords to topics
- **Synonym editor enhancements** (V3.2):
  - `bulk_import_synonyms()` - Opens dialog for pasting multiple synonyms at once
  - `get_synonyms_dict()` - Safe getter ensuring 'synonyms' key exists (prevents data loss)
  - `save_synonyms()` - Atomic write with backup, metadata update, and validation

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

**Synonym Expansion (Bidirectional):**
- Keywords expanded with synonyms BEFORE matching
- Synonyms loaded from `countries/{CODE}/synonyms.json` at initialization
- **Bidirectional matching** (V3.2 fix):
  1. If keyword contains topic name → add all synonyms as variations
  2. If keyword matches any synonym → add the topic name as variation
- Example: Synonym file has `"Documents": ["document management", ...]`
  - Keyword "Documents overview" → adds "document management" etc.
  - Keyword "document management" → adds "documents" (matches topic!)
- All variations compared against each topic; highest score wins
- Improves recall without sacrificing precision
- Missing synonym files gracefully degrade to empty dict (app continues)

**Product/Domain/Segment Assignment:**
- **CRITICAL**: The Product column in semantics file is **NOT used** for output
- Output Product/Domain/Segment values come **ONLY from matched taxonomy rows**
- Each matched topic brings its taxonomy row's Product/Domain/Segment metadata
- One URL can match topics from multiple Products → creates multiple output rows
- Synonyms can help control which taxonomy topics match, indirectly affecting Product assignment

**Product Filtering Logic (V3.2 fix):**
- URLs can match taxonomy topics based on these rules:
  1. **Empty taxonomy Product** → matches ANY semantic Product (generic/shared topics)
  2. **Exact Product match** → semantic Product equals taxonomy Product
  3. **"Other" semantic Product** → matches any taxonomy Product
- This allows URLs to match both product-specific and generic topics
- Location: `should_match_product()` in `taxonomy_matcher.py` (lines 167-195)

**Deduplication Strategy:**
- Use set of tuples: `(URL, Product, Domain, Segment, Topic)`
- Multiple keywords may match same topic → only one output row
- Same URL can appear multiple times for DIFFERENT topics
- Prevents combinatorial explosion of duplicate matches

**Topic Consolidation (Always Enabled):**
- Always-on post-processing step after matching completes
- Groups results by `(URL, Product, Domain, Segment)` tuple
- Spreads topics across columns: Topic_1, Topic_2, Topic_3, etc.
- Filters out segment names from Topic columns (segments stay in Segment column)
- Dynamic column count based on max topics per URL-Segment group
- Preserves discovery order (topics appear in order they were matched)
- Default: ON in config.yaml (`consolidate_topics: true`)
- Reduces output size by ~50% while preserving all information

**File Validation System (V3.1):**
- **Instant validation** - Validates on file selection via Browse button
- **Header-only validation** - Reads column names only (fast: <0.1s)
- **Four file types detected**:
  1. **semantic** - Has URL + Keyword columns
  2. **taxonomy** - Has Product/Domain/Segment/Topic columns (NO URL)
  3. **output** - Has URL + Product/Domain/Segment/Topic (rejected as input)
  4. **unknown** - Missing required columns
- **Visual feedback**:
  - ✓ Green checkmark - Valid file structure
  - ✗ Red X - Invalid file or output file
  - ⚠ Yellow warning - Wrong file type (swapped)
- **Hover tooltips** - ToolTip class shows detailed validation messages
- **Auto-swap detection** - Detects when semantic/taxonomy files are swapped
- **One-click fix** - Yellow banner with "Swap Files" button appears when swap detected
- **Pre-run validation** - Enhanced `validate_inputs()` blocks processing if files invalid

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
   - Extract keywords (Keyword 1-10) from semantics file
   - **Note**: Product column in semantics is ignored
   - For each keyword:
     - Expand with country-specific synonyms
     - Compare against all topics using fuzzy matching (threshold ≥ 80)
     - Record matches with their taxonomy Product/Domain/Segment
   - Deduplicate URL-Topic combinations

5. Apply consolidation (always enabled):
   - Group by (URL, Product, Domain, Segment)
   - Filter segment names from Topic columns
   - Spread topics across Topic_1, Topic_2, etc.

6. Export to Excel
   - Output filename: taxonomy_match_{COUNTRY_CODE}.xlsx
   - Format: Consolidated (one row per URL-Segment with Topic_1, Topic_2, etc.)
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

**Topic Consolidation:**
- **Always enabled** - Output is always consolidated format
- config.yaml: `global_settings.consolidate_topics: true` (default)
- GUI: No checkbox - consolidation is automatic
- CLI: `--consolidate-topics` flag available but defaults to True
- Output: One row per URL-Segment with Topic_1, Topic_2, etc. columns

### Important Implementation Details

**Keyword Extraction:**
- **Only reads**: URL and "Keyword 1" through "Keyword 10" from semantics file
- **Ignores all other columns**: Product, Title, Word Count, etc. in semantics
- Handles missing keywords gracefully with `pd.notna()` checks

**Topic Detection:**
- Dynamically detects "Topic" columns via `col.startswith('Topic')`
- Supports 1-9 topics per taxonomy row (flexible schema)
- Each Topic value must be unique (not match Product/Domain/Segment names)

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
├── launch_gui.bat               # Windows launcher (uses venv if available)
├── setup_environment.bat        # Creates virtual environment for multi-user setup
├── build.bat                    # One-click exe build script
├── NLMap_V3.spec                # PyInstaller configuration
├── requirements.txt             # Python dependencies
├── venv/                        # Virtual environment (created by setup_environment.bat)
├── dist/NLMap_V3/               # Built exe output (created by build.bat)
│
├── semantic_carriers_list.xlsx  # LEGACY: Backward compat for NL only
├── NL Taxonomy V2.xlsx          # LEGACY: Backward compat for NL only
└── taxonomy_match_{CODE}.xlsx   # Output files (auto-named by country code)
```

## Using the Synonym Report Generator (V3.2)

The Reports tab provides an automated way to identify missing synonyms:

### How to Generate a Synonym Report
1. Launch GUI: `python taxonomy_matcher_gui.py`
2. In Setup tab, select your semantic and taxonomy files
3. Navigate to the **Reports** tab
4. Click **"Generate Synonym Report"**
5. Choose save location for the Excel report
6. Review the generated report

### Interpreting the Report

**Sheet 1: All Proposed Synonyms**
- Lists all keyword-to-topic matches with fuzzy scores
- Priority column: HIGH (score ≥85%, freq ≥50), MEDIUM (score ≥80%, freq ≥20), LOW (others)
- Use this to see all potential synonym additions

**Sheet 2: HIGH Priority**
- Pre-filtered to show only best candidates
- These are keywords that strongly match topics AND appear frequently
- Start here when adding new synonyms

**Sheet 3: Summary by Topic**
- Shows how many potential synonyms were found per topic
- Topics with many proposals may have common keywords that should be added

**Sheet 4: Unmapped Keywords**
- High-frequency keywords that don't match ANY topic (score <70%)
- These may indicate gaps in your taxonomy, not just missing synonyms
- Consider whether new taxonomy rows are needed

### Example Workflow
1. Generate report for GB country
2. Review HIGH Priority sheet - found 57 candidates
3. Add top 20 matches to `countries/GB/synonyms.json`
4. Re-run matching to verify improvement
5. Repeat until desired match rate achieved

## Taxonomy Gap Analysis Workflow

When analyzing match coverage and identifying missing topics:

### Step 1: Analyze Keyword Frequency
Create analysis script to extract and count all keywords from semantic carriers:
```python
df = pd.read_excel('semantic_carriers_list.xlsx')
keywords = []
for i in range(1, 11):
    col = f'Keyword {i}'
    if col in df.columns:
        keywords.extend(df[col].dropna().tolist())

from collections import Counter
keyword_counts = Counter(keywords)
high_freq = {k: v for k, v in keyword_counts.items() if v >= 50}
```

### Step 2: Identify Gaps
Compare high-frequency keywords against existing taxonomy topics:
- Check if keyword appears in any Topic column
- Flag keywords with no corresponding topic (gap)
- Prioritize by frequency (keywords appearing 100+ times are critical)

### Step 3: Generate Recommendations
Group missing keywords by theme:
- Workflow/Process management
- Data management/security
- Compliance/Regulation
- Client/Contact management
- System administration
- Reporting/Analytics

### Step 4: Create New Taxonomy Rows
For each theme, create new taxonomy row with up to 10 related topics:
```
Product | Domain | Segment | Topic 1 | Topic 2 | ... | Topic 10
```

### Step 5: Test Impact
Re-run matching with expanded taxonomy and verify:
- Match rate improvement (e.g., 94.9% → 96-97%)
- Unmapped URL reduction (e.g., 201 → <100)
- No over-matching (URLs shouldn't match >30 segments)

**Example:** GB taxonomy analysis identified 89 high-frequency keywords (50+ occurrences) with no matching topics. Adding 15 new taxonomy rows with 144 topics improved match rate from 94.9% to 96-97%.

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

**Via GUI Bulk Import (Recommended):**
1. Launch GUI and go to Synonym Editor tab
2. Select country from dropdown
3. Select the topic you want to add synonyms to
4. Click "Bulk Import" button (purple)
5. Paste your synonyms (one per line) or click "Paste from Clipboard"
6. Click "Import All" - duplicates are automatically skipped
7. Click "Save Changes" to persist

**Via JSON file directly** (e.g., `countries/NL/synonyms.json`):
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
- `selected_country.trace_add('write', on_country_changed)` watches dropdown changes
- Uses `trace_add()` instead of deprecated `trace()` for Python 3.14/Tcl 9 compatibility
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
- **Required columns**: URL, Keyword 1-10 (with space: "Keyword 1" not "Keyword1")
- **Optional columns** (ignored by code): Product, Title, Word Count, Meta Description, etc.
- Variable row count (e.g., NL: ~231, GB: ~3955)

**Taxonomy file (e.g., NL Taxonomy V2.xlsx):**
- **Required columns**: Product, Domain, Segment, Topic 1 through Topic N
- Topic columns detected dynamically (supports Topic 1-9)
- Variable entries (e.g., NL: 33 entries → 54 topics, GB: 57 entries → 224 topics)

**taxonomy_match.xlsx (output):**

**Always Consolidated Format:**
- Columns: URL, Product, Domain, Segment, Topic_1, Topic_2, Topic_3, ..., Topic_N
- One row per unique URL-Segment combination
- Topics spread across columns in discovery order
- ~50% fewer rows than one-row-per-topic format
- Segment names do NOT appear in Topic columns (filtered automatically)
- Unmapped URLs have Domain='UNMAPPED' with empty topic columns

## Common Issues & Troubleshooting

### File Validation Issues

**Output file showing as valid taxonomy file:**
- FIXED in V3.1 - Output files are now detected and rejected
- Output files have URL + Product/Domain/Segment/Topic columns
- Validation shows red ✗ with message: "This is an OUTPUT file (mapping results)"
- Use the original taxonomy file instead

**File swap detected but files are correct:**
- Verify file contents: semantic should have URL + Keyword columns
- Taxonomy should have Product/Domain/Segment/Topic columns (NO URL)
- Check validation tooltips (hover over ✓✗⚠ icons) for detailed messages
- If validation is wrong, report as bug

**Validation stuck or not updating:**
- Validation happens on file selection in Browse dialog
- If indicator doesn't appear, try re-selecting the file
- Check Console tab for validation error messages

### Data Quality Issues

**Topics appearing that aren't expected:**
- Check your taxonomy file - ALL topics in output come from taxonomy Topic columns
- Example: "Products" appearing → Search taxonomy for "Products" in Topic columns
- The code does NOT create topics, only extracts them from taxonomy file
- Use: `grep -i "products" taxonomy.xlsx` or search in Excel

**Wrong Product values in output:**
- Product column from semantics file is **NOT used**
- Output Product comes from whichever taxonomy row's topic matched
- Example: If keyword "billing" matches topic "Invoicing" from taxonomy row with Product="CCH Central", output gets Product="CCH Central"
- To control Product assignment, use synonyms to guide which taxonomy topics match

**File swap error (0 matches, 0 topic columns detected):**
- V3.1 now detects this automatically with ⚠ yellow warning icon
- Shows "Files appear to be swapped!" banner with "Swap Files" button
- Click the button to automatically fix the swap
- Legacy fix: Manually swap the file paths in GUI inputs

**Consolidation produces empty Topic columns:**
- CAUSE: Topics that exactly match Segment names are filtered out during consolidation
- This is intentional - segments should not appear as topics
- If a topic legitimately has the same name as a segment, it will be filtered
- FIX: Rename the topic in taxonomy to be distinct from segment name

### GUI Issues

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
