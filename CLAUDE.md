# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**NL Taxonomy Mapper V3** is a Python application that maps URLs from semantic carriers to topics in a taxonomy structure using fuzzy string matching. It processes 231 URLs against 54 taxonomy topics with built-in Dutch language synonym support.

### Core Purpose
Maps keywords extracted from URLs (Keyword 1-10) to hierarchical taxonomy topics (Product → Domain → Segment → Topic) using configurable fuzzy matching with auto-deduplication.

## Development Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Required packages: pandas, openpyxl, fuzzywuzzy, python-Levenshtein
```

### Running the Application

**GUI Mode (Recommended):**
```bash
python taxonomy_matcher_gui.py

# Or use Windows launcher:
launch_gui.bat
```

**CLI Mode:**
```bash
python taxonomy_matcher.py
```

### Testing
No formal test suite currently exists. Manual testing workflow:
1. Place test files in project root: `semantic_carriers_list.xlsx` and `NL Taxonomy V2.xlsx`
2. Run matching with known threshold (e.g., 80%)
3. Verify output file `taxonomy_match.xlsx` is created
4. Check expected results: ~350-450 rows from 231 URLs, ~92% match rate

## Architecture

### Core Components

**taxonomy_matcher.py** - Core matching engine
- `TaxonomyMatcher` class: Main processing logic
- Fuzzy string matching using `fuzzywuzzy` library with Levenshtein distance
- Synonym expansion for Dutch language variations
- Deduplication logic prevents duplicate URL-Topic pairs
- Auto-adds Segment as Topic when any topic from that segment matches

**taxonomy_matcher_gui.py** - GUI application
- Tkinter-based interface with tabbed layout (Setup, Console, About)
- Threading for non-blocking UI during processing
- Real-time progress tracking and console logging
- File selection dialogs for input/output

### Key Architecture Patterns

**Flat Taxonomy Lookup Structure:**
- Taxonomy file has hierarchical rows (Product → Domain → Segment → Topic 1-6)
- Build phase flattens to list of dicts: `{'product', 'domain', 'segment', 'topic'}`
- Each topic becomes a separate searchable entry
- This enables efficient keyword-to-topic matching without nested loops

**Synonym Expansion:**
- Keywords expanded with synonyms BEFORE matching
- Each keyword generates multiple variations (e.g., 'bankzaken' → ['bankzaken', 'bank', 'banken', 'bankafschriften'])
- All variations compared against each topic; highest score wins
- Improves recall without sacrificing precision

**Auto-Segment Addition:**
- When ANY topic from a taxonomy row matches, also add that row's Segment as a separate topic
- Prevents loss of hierarchical information
- Example: If "Bankboekingsinstructies" matches → also add "Bankzaken" as topic

**Deduplication Strategy:**
- Use set of tuples: `(URL, Product, Domain, Segment, Topic)`
- Multiple keywords may match same topic → only one output row
- Same URL can appear multiple times for DIFFERENT topics
- Prevents combinatorial explosion of duplicate matches

### Data Flow
```
1. Load Excel files → pandas DataFrames
2. Flatten taxonomy → List[Dict] lookup structure
3. For each URL:
   - Extract keywords (Keyword 1-10)
   - For each keyword:
     - Expand with synonyms
     - Compare against all topics using fuzzy matching
     - Record matches above threshold
   - Auto-add segments for matched topics
   - Deduplicate URL-Topic combinations
4. Export to Excel
```

### Configurable Parameters

**Similarity Threshold (50-100):**
- Default: 80%
- GUI: Adjustable via slider
- CLI: Prompts user at runtime or hardcode in `TaxonomyMatcher.__init__`
- Affects precision/recall tradeoff

**Dutch Synonyms Dictionary:**
- Location: `taxonomy_matcher.py` lines 36-46
- Format: `{'main_term': ['synonym1', 'synonym2']}`
- Pre-configured for: bankzaken, facturatie, btw, relatiebeheer, grootboek, vaste activa, etc.

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

## File Structure

```
nlmapV3/
├── taxonomy_matcher.py         # Core matching engine (CLI)
├── taxonomy_matcher_gui.py     # Tkinter GUI wrapper
├── launch_gui.bat              # Windows launcher script
├── requirements.txt            # Python dependencies
├── CONFIG.md                   # Configuration documentation (not programmatically used)
└── [Input files]              # semantic_carriers_list.xlsx, NL Taxonomy V2.xlsx
```

## Common Modification Patterns

### Adjusting Match Threshold Programmatically
Edit `taxonomy_matcher.py` line 20:
```python
similarity_threshold: int = 80  # Change to desired value
```

### Adding New Synonyms
Edit `taxonomy_matcher.py` lines 36-46:
```python
self.synonyms = {
    'new_term': ['variant1', 'variant2'],
    # ... existing synonyms
}
```

### Changing Fuzzy Matching Algorithm
Currently uses `fuzz.partial_ratio()` (line 127). Alternatives:
- `fuzz.ratio()` - Strict full string comparison
- `fuzz.token_sort_ratio()` - Word order independent
- `fuzz.token_set_ratio()` - Handles subset matches

### Modifying Output Columns
Edit `taxonomy_matcher.py` lines 191-197 to add/remove columns in results dict.

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
- Columns: URL, Product, Domain, Segment, Topic
- One row per unique URL-Topic match
- Unmapped URLs have Domain='UNMAPPED'
