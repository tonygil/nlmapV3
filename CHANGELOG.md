# Changelog

Full version history for Taxonomy Mapper V3.
Current version and last 3 releases are in `CLAUDE.md`.

---

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
| 3.15 | 2026-02-XX | Source-aware matching: Title uses lower threshold `max(70, threshold-10)`; URL gets "Low Trust" at 80-84%; requires `Source N` columns. |
| 3.14 | 2026-02-XX | Exact Match Bypass removed — all topics through normal fuzzy threshold. |
| 3.13 | 2026-02-XX | ContentKeywordExtractor skips URL deduplication when Product column exists; Data_Categories__c multi-product row expansion. |
| 3.12 | 2026-02-XX | Strict Match hidden — 90% noise output, use crawler keywords instead. |
