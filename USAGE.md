# Usage Guide - NL Taxonomy Mapper V2

## Quick Start

### 1. Installation

```bash
# Navigate to project folder
cd C:\Users\TonyGilpin\Desktop\Projects\nlmapV2

# Install dependencies
pip install -r requirements.txt
```

### 2. Prepare Input Files

Place these files in the project folder:
- `semantic_carriers_list.xlsx` (URL data with keywords)
- `NL Taxonomy V2.xlsx` (taxonomy structure)

### 3. Run the Script

```bash
python taxonomy_matcher.py
```

### 4. Output

The script creates `taxonomy_match.xlsx` with columns:
- URL
- Product
- Domain
- Segment
- Topic

---

## Detailed Usage

### Command Line Options (Future Enhancement)

Currently, settings are in the script. Future versions may support:

```bash
python taxonomy_matcher.py --threshold 85 --output custom_output.xlsx
```

### Adjusting Match Threshold

Edit `taxonomy_matcher.py` line 18:

```python
similarity_threshold: int = 80  # Change this value (0-100)
```

**Recommendations:**
- **80-85**: Balanced (recommended)
- **75-79**: More lenient (catches more matches, some may be loose)
- **86-90**: Stricter (fewer but higher quality matches)

### Adding Synonyms

Edit the `synonyms` dictionary in `taxonomy_matcher.py` (lines 27-37):

```python
self.synonyms = {
    'bankzaken': ['bank', 'banken', 'bankafschriften'],
    'your_term': ['synonym1', 'synonym2'],  # Add your own
}
```

---

## Expected Results

### Statistics
- **Input URLs:** 231
- **Expected output rows:** 350-450
- **Match rate:** ~92% of URLs
- **Processing time:** ~30-60 seconds

### Output Structure

**Example:**
| URL | Product | Domain | Segment | Topic |
|-----|---------|--------|---------|-------|
| https://...Bankboekingsinstructies | Twinfield | Boekhouding | Bankzaken | Bankboekingsinstructies |
| https://...Debiteuren | | General | Relatiebeheer | Klantenbeheer |

---

## Troubleshooting

### Issue: "File not found"
**Solution:** Ensure input files are in the same folder as the script, or provide full paths.

### Issue: Low match rate (<80%)
**Solutions:**
1. Lower the similarity threshold (try 75)
2. Add more synonyms to the dictionary
3. Check keyword quality in semantic_carriers_list.xlsx

### Issue: Too many matches per URL
**Solutions:**
1. Increase similarity threshold (try 85)
2. Review synonyms - may be too broad

### Issue: Script runs slowly
**Solution:** Install python-Levenshtein for faster fuzzy matching:
```bash
pip install python-Levenshtein
```

---

## Interpreting Results

### Match Quality

**High confidence (similarity 90-100):**
- Direct, exact matches
- Very reliable

**Medium confidence (similarity 80-89):**
- Good matches with slight variations
- Generally reliable

**Lower threshold (similarity 75-79):**
- May include some loose matches
- Review manually if possible

### Deduplication

The script automatically deduplicates:
- If 3 keywords from same URL match same topic → only 1 output row
- Same URL can appear multiple times for DIFFERENT topics

---

## Advanced Usage

### Programmatic Use

```python
from taxonomy_matcher import TaxonomyMatcher

# Create custom matcher
matcher = TaxonomyMatcher(
    semantic_file='path/to/semantic.xlsx',
    taxonomy_file='path/to/taxonomy.xlsx',
    output_file='custom_output.xlsx',
    similarity_threshold=85
)

# Run matching
matcher.run()
```

### Custom Synonym Loading

```python
# Load synonyms from external file (future enhancement)
matcher.load_synonyms('synonyms.json')
```

---

## Next Steps After Running

1. **Review output:** Open `taxonomy_match.xlsx`
2. **Check unmapped URLs:** Compare input count vs output unique URLs
3. **Validate matches:** Spot-check some matches for accuracy
4. **Adjust if needed:** Modify threshold or synonyms and re-run
5. **Use results:** Import into your content management system

---

## Support

For issues or questions:
1. Check CONFIG.md for settings
2. Review README.md for project overview
3. Examine the Python script comments for logic details
