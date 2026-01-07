# NL Taxonomy Mapper V2 🗂️

## Project Overview
Modern application for mapping URLs from semantic_carriers_list.xlsx to topics in NL Taxonomy V2.xlsx using fuzzy string matching.

## Features
✨ **Beautiful Modern GUI** - Intuitive interface with tabs and visual feedback
🎯 **Fuzzy String Matching** - 80% similarity threshold (adjustable)
🇳🇱 **Dutch Language Support** - Built-in synonym dictionary
🔄 **Auto Deduplication** - Prevents duplicate URL-Topic combinations
📊 **Real-time Progress** - Live console logging
⚡ **Fast Processing** - Handles 231 URLs in ~30 seconds

## Quick Start

### GUI Mode (Recommended)
```bash
python taxonomy_matcher_gui.py
```

### Command Line Mode
```bash
python taxonomy_matcher.py
```

## Installation

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Place input files in project folder:**
   - `semantic_carriers_list.xlsx`
   - `NL Taxonomy V2.xlsx`

3. **Run the application:**
   - GUI: `python taxonomy_matcher_gui.py`
   - CLI: `python taxonomy_matcher.py`

## GUI Interface

### Tabs

**📋 Setup Tab**
- Select input files (semantic carriers & taxonomy)
- Choose output file location
- Adjust similarity threshold (50-100%)
- Run matching process

**📊 Console Tab**
- Real-time processing logs
- Progress updates
- Copy/clear log functions

**ℹ️ About Tab**
- Application information
- Feature list
- Version details

### Using the GUI

1. **Click "Browse"** to select your input files
2. **Adjust threshold** slider (recommended: 75-85)
3. **Click "Run Matching"** to start processing
4. **Monitor progress** in Console tab
5. **Check output** when completed

## Input Files

### semantic_carriers_list.xlsx
- 231 URLs with extracted keywords (Keyword 1-10)
- Contains: URL, Title, Keywords, Word Count, Meta Description

### NL Taxonomy V2.xlsx
- Hierarchical taxonomy structure
- Contains: Product, Domain, Segment, Topic 1-6
- 33 taxonomy entries with 54 unique topics

## Output File

**taxonomy_match.xlsx**

Columns:
- **URL** - Source URL from semantic carriers
- **Product** - From taxonomy (may be empty)
- **Domain** - Main category (e.g., Boekhouding, General)
- **Segment** - Sub-category (e.g., Bankzaken, Facturatie)
- **Topic** - Matched topic

## Matching Logic

### Process
1. Extract all keywords from each URL (Keyword 1-10)
2. Compare each keyword against all taxonomy topics
3. Calculate similarity score using fuzzy matching
4. Record matches above threshold (default 80%)
5. Deduplicate: same URL+Topic appears only once

### Similarity Threshold Guide
- **75-80%** - More lenient, catches more matches
- **80-85%** - Balanced (recommended)
- **85-95%** - Stricter, higher quality matches

### Synonym Support
Dutch language variations handled automatically:
- `bankzaken` → bank, banken, bankafschriften, bankrekeningen
- `facturatie` → facturen, factuur, facturering
- `btw` → belasting, belastingaangifte
- And more...

## Expected Results

- **Processing time:** 30-60 seconds
- **Match rate:** ~92% of URLs
- **Output rows:** 350-450 (from 231 URLs)
- **Average matches per URL:** 1-2

## Project Structure

```
nlmapV2/
├── taxonomy_matcher.py         # Core matching logic (CLI)
├── taxonomy_matcher_gui.py     # Beautiful GUI application
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── USAGE.md                    # Detailed usage guide
├── CONFIG.md                   # Configuration options
└── PROJECT_SETUP.md           # Setup instructions
```

## Configuration

### Adjusting Threshold (CLI)
Edit line 18 in `taxonomy_matcher.py`:
```python
similarity_threshold: int = 80  # Change 0-100
```

### Adding Synonyms
Edit `taxonomy_matcher.py` lines 27-37:
```python
self.synonyms = {
    'your_term': ['synonym1', 'synonym2'],
}
```

## Dependencies

- **pandas** - Excel file operations
- **openpyxl** - Excel file format support
- **fuzzywuzzy** - Fuzzy string matching
- **python-Levenshtein** - Fast string comparison

## Troubleshooting

### "File not found"
- Ensure input files are in project folder
- Or use Browse button to select full paths

### Low match rate (<80%)
- Lower similarity threshold to 75
- Add more synonyms in code
- Check keyword quality in input file

### GUI doesn't start
- Install tkinter: `pip install tk`
- Check Python version (3.7+)

### Slow processing
- Install python-Levenshtein for speed boost
- Close other applications

## Screenshots

The GUI features:
- 🎨 Modern, clean design
- 📱 Responsive layout
- 🌓 Professional color scheme
- ⚡ Real-time feedback
- 📊 Live progress tracking

## Support & Documentation

- **README.md** - Overview (this file)
- **USAGE.md** - Detailed usage instructions
- **CONFIG.md** - Configuration settings
- **PROJECT_SETUP.md** - Initial setup guide

## Version History

**V2.0** (2025)
- Added beautiful GUI
- Improved matching algorithm
- Enhanced synonym support
- Better error handling
- Real-time progress tracking

## Author
Created: 2025
Version: 2.0.0

---

**Ready to use! Launch the GUI and start matching!** 🚀
