# Salesforce Export Workflow

Standardized workflow for processing Salesforce Knowledge exports across BE, NL, SE (and future countries).

---

## Related Projects

| Project | Location | Running At | Purpose |
|---------|----------|------------|---------|
| **NLUrl v2.0** | `C:\url spreasheets\vs_projects\nlurlv2\` | localhost:5000 (dev) / localhost:8080 (prod) | Python/Flask web app. Crawls Salesforce community sites (NL, SE, BE) using aiohttp. Extracts frequency-based 2-3 word keywords via n-gram analysis (NOT AI semantic). Outputs Excel with `Keyword 1-15`. |
| **vmcrawl** | (separate project) | localhost:3000 | Node.js/Playwright crawler for GB/UK userdocs.wolterskluwer.co.uk. Outputs Excel with URL, HTML, TXT, Title columns. |
| **NLMap v3** | `C:\url spreasheets\vs_projects\nlmapV3\` | — (desktop) | This project. Fuzzy-matches keywords against taxonomy (rapidfuzz). Multi-country (NL, SE, BE, GB). |

**Data Pipeline:**
```
Salesforce sites (NL, SE, BE):
  Method A: NLUrl (localhost:5000) -> crawl_results_{lang}.xlsx -> NLMap taxonomy match
  Method B: CSV (482 cols) -> NLMap "Import SF CSV" -> Semantic_{CODE}.xlsx -> taxonomy_match_{CODE}.xlsx

GB/UK userdocs site:
  vmcrawl (localhost:3000) -> scraped_results.xlsx -> NLMap taxonomy match
```

**Future:** NLUrl and NLMap are planned to merge into a single application. Currently NLUrl imports `StrictContentMatcher` from NLMap for topic enrichment, and both share country config (`countries/{CODE}/domains.json`, `segments.json`, `synonyms.json`).

---

## Recommended Workflow: Belgium (BE)

**Best practice:** Use NLUrl crawler keywords — NOT Strict Content Matcher.

| Metric | NLUrl Crawler | Strict Content Matcher |
|--------|--------------|------------------------|
| HTML contamination | 0.0% | 57.5% |
| Generic noise | 0.0% | 100% |
| Product identification | ✅ Correct | ❌ Uses titles |
| Usable for taxonomy | ✅ Yes | ❌ No |

**Steps:**
1. Upload Salesforce Knowledge__kav CSV to NLUrl → `crawl_results_nl_BE.xlsx`
2. `python taxonomy_matcher.py -c BE --semantic-file crawl_results_nl_BE.xlsx`
3. Optional: `python post_processor.py -i taxonomy_match_BE.xlsx --max-rank 3`

---

## CSV Format Requirements

**Typical Salesforce Knowledge CSV export:**
- 482+ columns (only first ~6 useful, rest are HTML metadata)
- URLs in HTML anchor tags: `<a href="/lightning/articles/Knowledge/{slug}?language=nl_BE">...</a>`
- Essential columns: `Knowledge_Url__c`, `Title`, `Summary`, `Answer__c`/`Description`

**Auto-handled by both methods:**
- 476+ junk columns (ignored)
- HTML anchor tag URLs (extracted)
- Lightning URLs (converted to public community URLs)
- BOM in headers (stripped)
- Different column orders (detected)

---

## Taxonomy Structure Requirements

**Required structure:**

| Column | Required | Description |
|--------|----------|-------------|
| `Product` | ✅ Yes | Single column with product name |
| `Domain` | ✅ Yes | Domain name |
| `Segment` | ✅ Yes | Segment name |
| `Topic 1` ... `Topic N` | ✅ Yes | Topics (any number, auto-detected) |

**If taxonomy has `Product 1`, `Product 2`, etc. columns:**
```bash
python restructure_taxonomy.py -i "Taxonomy BE.xlsx" -o "countries/BE/taxonomy.xlsx"
```

Example conversion:
```
INPUT (1 row):
Productfamily | Product 1           | Product 2            | Domain | Topic 1
Adsolut       | Adsolut boekhouding | Adsolut Jaarrekening | Welkom | Login

OUTPUT (2 rows):
Product               | Domain | Topic 1
Adsolut boekhouding   | Welkom | Login
Adsolut Jaarrekening  | Welkom | Login
```

---

## Method A: NLUrl + NLMap (Production Quality)

**Recommended for:** Production use, best keyword quality, language-aware extraction.

**Steps:**
1. Upload to NLUrl (`http://localhost:5000`) — select Salesforce CSV, optionally enable "Auto-enrich", start crawl
2. Download `crawl_results_{lang}.xlsx` (URL + Title + Summary + Description + Keyword 1-15)
3. Match in NLMap:
   ```bash
   python taxonomy_matcher.py -c BE --semantic-file "crawl_results_nl_BE.xlsx"
   # GUI: Setup tab → select crawl_results as Semantic File → Run
   ```

**Quality:** 50.7% are 2-3 word phrases · 0% HTML contamination · 0% generic noise · language-aware stopwords.

---

## Method B: Direct Import in NLMap (Convenience)

**Recommended for:** Quick tests, no NLUrl access, single-tool workflow.

**Steps:**
1. Setup tab → Click "📥 Import SF CSV"
2. Select Salesforce CSV file, country code (BE/NL/SE), optional taxonomy for keyword ranking
3. Click "▶ Import CSV" — auto-detects columns, extracts URLs, converts Lightning URLs, generates Keyword 1-12, creates `Semantic_{country}_{datetime}.xlsx`
4. Semantic file auto-populated → Click "Run Taxonomy Match"

**Quality:** Good content-based extraction · 0% HTML contamination · Handles missing columns gracefully · Faster than NLUrl for small datasets.

---

## Method Comparison

| Feature | Method A (NLUrl) | Method B (Direct Import) | Strict Match (Deprecated) |
|---------|------------------|--------------------------|---------------------------|
| **Keyword source** | Frequency n-grams | Content extraction | Page crawl |
| **Language-aware** | ✅ Yes | Partial | No |
| **HTML handling** | ✅ Multi-algorithm | BeautifulSoup | Poor (57% contamination) |
| **Keyword count** | 15 | 12 | 6 |
| **Generic noise** | 0% | <5% | 90%+ |
| **Best for** | Production | Quick tests | ❌ Deprecated |

---

## Data_Categories__c Column Support (v3.13)

**Auto-detected from Salesforce exports:**
- Column: `Data_Categories__c` (semicolon-separated product/topic categories)
- Example: `"Adsolut_Account;ExpertM_Plus;Briljant_Account"`
- Mapped via: `countries/{CODE}/category_mapping.json`

**Multi-Product Row Expansion:**
```
Input (1 URL): Data_Categories__c = "Adsolut_Account;ExpertM_Plus"
Output (2 rows): Row 1: Product="Adsolut boekhouden"  Row 2: Product="ExpertM"
```

**Implementation:**
- Mapping file: `countries/BE/category_mapping.json` — 24 categories mapped, 8 special tags filtered
- Expansion happens in `salesforce_csv_processor.py` before keyword extraction
- ContentKeywordExtractor skips URL deduplication when Product column exists (v3.13 bug fix)
- Belgium stats: ~709 additional rows (1,809 unique URLs → 2,518 total rows)

**Critical bug fix (v3.13):** ContentKeywordExtractor always deduplicated by URL, destroying multi-product expansion.

Fix in `content_keyword_extractor.py` lines 701-714:
```python
if 'Product' in df.columns and df['Product'].notna().any():
    print("Product column detected - preserving multi-product rows")
    df_deduped = df  # NO deduplication
else:
    df_deduped = df.drop_duplicates(subset=['URL'], keep='first')
```

---

## Community Base URLs

| Country | Base URL |
|---------|----------|
| BE (Belgium) | `https://taasupport.wolterskluwer.be/customers/s/article` |
| NL (Netherlands) | `https://wktaaeu.my.site.com/nlcommunity/s/article` |
| SE (Sweden) | `https://wktaaeu.my.site.com/se/s/article` |

**To find base URL for a new country:** Open published article in Salesforce → "View as Customer" / "Public Link" → extract `https://{domain}/s/article` (everything before `/{slug}`).

---

## Quick Start: New Country Setup (~30 minutes)

1. **Add to `config.yaml`:**
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

2. **Create directory:**
   ```bash
   mkdir countries\XX
   # Add: taxonomy.xlsx, synonyms.json (start: {"synonyms": {}}), category_mapping.json ({})
   ```

3. **Add community URL** in `convert_salesforce_urls.py`:
   ```python
   COMMUNITY_BASE_URLS = {'XX': 'https://your-community.example.com/s/article'}
   ```

4. **Test:** Use Method B (Direct Import) → verify URLs converted, keywords extracted, taxonomy matched. Match rate >50% is healthy (improves with synonyms).

Complete guide: `SALESFORCE_COUNTRY_SETUP.md`

---

## Salesforce Troubleshooting

**URLs not converted (still `/lightning/...`):**
```bash
python convert_salesforce_urls.py -i input.csv -c BE -o test.csv
# Check: "Converted: 0 URLs"? -> Wrong community URL, missing beautifulsoup4, or wrong column
pip install beautifulsoup4
```

**Match rate very low (<30%):** Check `Unmapped_Reason` column:
- "Product filter excluded" → fix category_mapping.json
- "No matches above threshold" → add synonyms (review Keyword Recommendations sheet)
- "No keywords extracted" → content columns empty

**Multi-product rows lost:**
```python
import pandas as pd
df = pd.read_excel("output.xlsx")
print(f"Multi-product URLs: {len(df['URL'].value_counts()[lambda x: x > 1])}")  # Should be >0 for BE
```
Fix: verify deduplication skip at `content_keyword_extractor.py` lines 701-714.

**Product column has garbage (HTML, font names):**
- If temp file (`_temp_semantic_*.xlsx`) Product is correct → ContentKeywordExtractor issue
- If temp file Product is corrupt → salesforce_csv_processor issue
- Fix: verify `content_keyword_extractor.py` lines 751-761 preserves Product unconditionally

---

## NLUrl v2.0 Reference

**CSV Column Auto-Detection:** Handles `Knowledge_Url__c`, `Title`, `Summary`, `Answer__c`/`Description` columns. Strips BOM from headers. Generates placeholder URLs if URL column missing.

**Keyword Extraction Method:** Frequency-based n-gram (NOT AI semantic). H1-H6 and bold text = high priority. Bigrams, trigrams, 4-grams. Stopword filtering + deduplication. Quality: 50.7% are 2-word phrases, 0% HTML contamination.

**To run NLUrl:**
```bash
cd "C:\url spreasheets\vs_projects\nlurlv2\webapp"
python app.py          # Dev server at localhost:5000
python run_webapp.py   # Production server at localhost:8080
```

**Required packages (NLUrl):** flask, waitress, pandas, rapidfuzz, PyYAML, aiohttp, beautifulsoup4, lxml, rich, openpyxl, nltk, stop-words

---

## NLUrl Topic Enrichment Integration

NLUrl imports `StrictContentMatcher` from NLMap to enrich crawl output with content-based topics. NLMap itself is not modified by this integration.

**Key files in NLUrl:**

| File | Purpose |
|------|---------|
| `backend/topic_enricher.py` | Bridge: imports StrictContentMatcher from NLMap, enriches crawl output Excel |
| `webapp/app.py` | Routes: `/upload_csv`, `/enrich`, `/enrich_stream`, `/download_enriched`; auto-enrich flag |
| `webapp/templates/results.html` | "Enrich with Topics" button, enrichment stats, download |
| `smart_crawler_multi.py` | `save_to_excel()` includes Summary + Description columns |
| `backend/crawler_wrapper.py` | `_run_csv_mode()` carries CSV Summary (row[3]) and Answer__c (row[4]) |

**CSV mode data flow:**
```
CSV File (Knowledge__kav)
  Column 2: Title      -> Excel "Title"
  Column 3: Summary    -> Excel "Summary"
  Column 4: Answer__c  -> Excel "Description" (first 5000 chars)
                       -> Keywords via n-gram -> Excel "Keyword 1-15"

TopicEnricher reads Excel output:
  Title/URL/Summary/Description -> StrictContentMatcher
  -> Enriched Excel: + Product_Auto, Domain, Segment, Topic_1..6, Source_1..6, Top_Relevance
```

**Two enrichment modes:**
1. **Manual:** Crawl → results page → "Enrich with Topics" button → download enriched Excel
2. **Auto:** Check "Auto-enrich" before crawling → enrichment runs automatically after crawl
