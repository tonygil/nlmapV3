"""
NL Taxonomy Mapper V3
Matches URLs from semantic carriers to taxonomy topics using fuzzy string matching.
NOW WITH MULTI-COUNTRY SUPPORT!
"""

import pandas as pd
import re
from rapidfuzz import fuzz
from typing import List, Dict, Tuple, Optional
import os
import argparse
from functools import lru_cache
from country_config import CountryConfig

# Pre-compiled regex for content keyword extraction (replaces 10-iteration loop)
_SEPARATOR_PATTERN = re.compile(r'[-_/|:,.()\[\]]')


# Module-level cached synonym expansion function
@lru_cache(maxsize=10000)
def _is_word_match(needle: str, haystack: str) -> bool:
    """Check if needle appears as a complete word/phrase in haystack.

    Rules:
    - Exact match always works: "security" == "security"
    - Single-word needle in multi-word haystack: needle must be a whole word
      "security" in "security mapping" -> True (complete word)
      "data" in "data validation" -> True (complete word)
    - Multi-word needle in single-word haystack: haystack must be a word in needle
      "security mapping" contains "security" -> True
    - Both multi-word: needle must appear as complete phrase in haystack
    """
    if needle == haystack:
        return True

    needle_words = needle.split()
    haystack_words = haystack.split()

    if len(needle_words) == 1 and len(haystack_words) == 1:
        # Both single words: must be exact
        return False  # Already checked equality above

    if len(needle_words) == 1 and len(haystack_words) > 1:
        # Single-word needle in multi-word haystack:
        # Allow if needle is a complete word in haystack
        # e.g., "security" in "security mapping" -> True
        return needle in haystack_words

    if len(needle_words) > 1 and len(haystack_words) == 1:
        # Multi-word needle, single-word haystack:
        # Check if haystack word appears in needle
        # e.g., keyword "security mapping" contains topic "security" -> expand
        return haystack in needle_words

    # Both multi-word: check if needle appears as complete phrase in haystack
    n = len(needle_words)
    for i in range(len(haystack_words) - n + 1):
        if haystack_words[i:i + n] == needle_words:
            return True
    return False


@lru_cache(maxsize=10000)
def _expand_keyword_cached(keyword_lower: str, synonyms_tuple: tuple) -> tuple:
    """
    Cached synonym expansion. Returns tuple of variations for hashability.

    Uses word boundary matching to prevent generic words like "data"
    from matching synonyms like "data validation" via substring.

    Args:
        keyword_lower: Lowercase, stripped keyword
        synonyms_tuple: Tuple of (topic, (syn1, syn2, ...)) pairs

    Returns:
        Tuple of keyword variations including synonyms
    """
    variations = [keyword_lower]

    for key, synonyms in synonyms_tuple:
        # Skip comment entries
        if key.startswith('_'):
            continue

        key_lower = key.lower()

        # Direction 1: If topic name appears as complete word(s) in keyword, add synonyms
        # e.g., keyword "security mapping" contains word "security" (topic) -> add synonyms
        # Rule: keyword must be >= topic length (keyword contains topic, not reverse)
        #   "security mapping" contains "security" -> YES (keyword longer)
        #   "data" contains "Data import" -> NO (keyword shorter than topic)
        key_words = key_lower.split()
        kw_words = keyword_lower.split()
        if len(kw_words) >= len(key_words) and _is_word_match(key_lower, keyword_lower):
            variations.extend([s.lower() for s in synonyms])

        # Direction 2: If keyword exactly matches a synonym, add the topic name
        # This is STRICT: keyword must fully match the synonym (not just be a word in it)
        # Prevents "data" from matching synonym "data validation" -> topic "Data validation"
        for syn in synonyms:
            syn_lower = syn.lower()
            if syn_lower == keyword_lower:
                # Exact match: keyword IS the synonym
                variations.append(key_lower)
                break
            # Multi-word keyword can match if synonym is a word in it
            # e.g., keyword "audit workflows" contains synonym "workflows" -> add topic
            elif len(keyword_lower.split()) > 1 and _is_word_match(syn_lower, keyword_lower):
                variations.append(key_lower)
                break

    return tuple(set(variations))


class TaxonomyMatcher:
    """Main class for matching URL keywords to taxonomy topics."""
    
    def __init__(self,
                 country_code: Optional[str] = None,
                 semantic_file: Optional[str] = None,
                 taxonomy_file: Optional[str] = None,
                 output_file: Optional[str] = None,
                 similarity_threshold: Optional[int] = None,
                 consolidate_topics: Optional[bool] = None,
                 include_summary: bool = False,
                 top_n: int = 3,
                 config_file: str = 'config.yaml',
                 debug: bool = False,
                 max_rows: int = 0,
                 url_filter: str = ''):
        """
        Initialize the TaxonomyMatcher.

        Args:
            country_code: Two-letter country code (NL, SE, BE) - if None, uses default
            semantic_file: Path to semantic carriers file (overrides config)
            taxonomy_file: Path to taxonomy file (overrides config)
            output_file: Path for output file (auto-generated if None)
            similarity_threshold: Minimum similarity score (overrides config)
            consolidate_topics: Consolidate topics into columns (overrides config)
            include_summary: Extract keywords from Summary column if present
            config_file: Path to YAML configuration file
            debug: Enable per-keyword trace output for debugging matches
            max_rows: Limit processing to first N rows (0 = all)
            url_filter: Only process URLs containing this text (empty = all)
        """
        # Load country configuration
        self.country_config = CountryConfig(config_file)

        # Determine country (fallback to default if not specified)
        if country_code is None:
            country_code = self.country_config.get_default_country()
        self.country_code = country_code.upper()

        # Validate country exists
        available = [c['code'] for c in self.country_config.get_available_countries()]
        if self.country_code not in available:
            raise ValueError(
                f"Country '{self.country_code}' not available. "
                f"Available countries: {', '.join(available)}"
            )

        # Get country-specific files (if not explicitly provided)
        if semantic_file is None or taxonomy_file is None:
            country_files = self.country_config.get_country_files(self.country_code)

            if semantic_file is None:
                semantic_file = country_files['semantic_carriers']
            if taxonomy_file is None:
                taxonomy_file = country_files['taxonomy']

        self.semantic_file = semantic_file
        self.taxonomy_file = taxonomy_file

        # Generate output filename with country code suffix
        if output_file is None:
            output_file = f'taxonomy_match_{self.country_code}.xlsx'
        # If user provided filename without country code, add it
        elif not output_file.replace('.xlsx', '').endswith(f'_{self.country_code}'):
            base, ext = os.path.splitext(output_file)
            output_file = f'{base}_{self.country_code}{ext}'

        self.output_file = output_file

        # Load country settings
        country_settings = self.country_config.get_country_settings(self.country_code)

        # Use provided threshold or country default
        if similarity_threshold is None:
            similarity_threshold = country_settings.get('similarity_threshold', 80)
        self.similarity_threshold = similarity_threshold

        # Use provided consolidate_topics or country default
        if consolidate_topics is None:
            consolidate_topics = country_settings.get('consolidate_topics', False)
        self.consolidate_topics = consolidate_topics

        # Load synonyms from JSON file instead of hardcoded dict
        self.synonyms = self.country_config.load_synonyms(self.country_code)

        # Create hashable tuple version of synonyms for caching
        self._synonyms_tuple = tuple(
            (k, tuple(v)) for k, v in self.synonyms.items()
        )

        # Store Summary column processing flag
        self.include_summary = include_summary

        # Top N results per URL
        self.top_n = top_n

        self.semantic_df = None
        self.taxonomy_df = None
        self.taxonomy_lookup = []

        # Cache for URL keyword extraction (avoid redundant parsing)
        self._url_keywords_cache = {}

        # Debug and testing parameters
        self.debug = debug
        self.max_rows = max_rows
        self.url_filter = url_filter.strip() if url_filter else ''
        
    def load_data(self):
        """Load Excel files into pandas DataFrames."""
        print(f"Loading {self.semantic_file}...")
        self.semantic_df = pd.read_excel(self.semantic_file)
        total_loaded = len(self.semantic_df)
        print(f"  Loaded {total_loaded} URLs")

        # Apply URL filter first (if set)
        if self.url_filter:
            before_count = len(self.semantic_df)
            mask = self.semantic_df['URL'].astype(str).str.contains(
                self.url_filter, case=False, regex=False
            )
            self.semantic_df = self.semantic_df[mask].copy()
            after_count = len(self.semantic_df)
            print(f"  URL filter '{self.url_filter}': {before_count} -> {after_count} rows")
            if after_count == 0:
                raise ValueError(
                    f"URL filter '{self.url_filter}' matched 0 rows out of {before_count}. "
                    f"Check the filter text and try again."
                )

        # Apply max rows limit second (within filtered set)
        if self.max_rows > 0 and len(self.semantic_df) > self.max_rows:
            before_count = len(self.semantic_df)
            self.semantic_df = self.semantic_df.head(self.max_rows).copy()
            print(f"  Max rows limit: {before_count} -> {len(self.semantic_df)} rows")

        print(f"\nLoading {self.taxonomy_file}...")
        self.taxonomy_df = pd.read_excel(self.taxonomy_file)
        print(f"  Loaded {len(self.taxonomy_df)} taxonomy entries")
        
    def build_taxonomy_lookup(self):
        """Build a flat lookup structure from taxonomy with all topics."""
        print("\nBuilding taxonomy lookup...")

        # Dynamically detect Topic columns
        topic_columns = [col for col in self.taxonomy_df.columns if col.startswith('Topic')]
        print(f"  Detected {len(topic_columns)} topic columns: {topic_columns}")

        # Pre-compute all topic entries with pre-lowercased topics for faster matching
        for idx, row in self.taxonomy_df.iterrows():
            product = row.get('Product', '')
            domain = row.get('Domain', '')
            segment = row.get('Segment', '')

            # Extract all topics from this row
            for topic_col in topic_columns:
                topic = row.get(topic_col, '')
                if pd.notna(topic) and topic.strip():
                    topic_str = topic.strip()
                    self.taxonomy_lookup.append({
                        'product': product if pd.notna(product) else '',
                        'domain': domain if pd.notna(domain) else '',
                        'segment': segment if pd.notna(segment) else '',
                        'topic': topic_str,
                        'topic_lower': topic_str.lower()  # Pre-computed lowercase
                    })

        print(f"  Created {len(self.taxonomy_lookup)} searchable topic entries")

        # Build sorted list of taxonomy product names for URL-based detection
        # Sorted longest-first so "CCH iFirm Accounts Production" matches before "CCH Accounts Production"
        self.taxonomy_products = sorted(
            [str(p) for p in self.taxonomy_df['Product'].dropna().unique() if str(p) != 'Something Else'],
            key=len, reverse=True
        )

        # Pre-compute product URL forms for faster lookup
        self._product_url_forms = [
            (product, product.replace(' ', '_').lower())
            for product in self.taxonomy_products
        ]

        # Build product-indexed lookup for faster product-specific queries
        self._product_lookup = {}
        for entry in self.taxonomy_lookup:
            product = entry['product']
            if product not in self._product_lookup:
                self._product_lookup[product] = []
            self._product_lookup[product].append(entry)

        # Build (product, topic) indexed lookup for O(1) domain/segment lookups
        # Used when reassigning "Something Else" topics to a specific product
        self._product_topic_lookup = {}
        for entry in self.taxonomy_lookup:
            key = (entry['product'], entry['topic'])
            if key not in self._product_topic_lookup:
                self._product_topic_lookup[key] = entry

        # Pre-compute list of all topics (lowercase) for batch matching
        self._all_topics_lower = [entry['topic_lower'] for entry in self.taxonomy_lookup]

    def expand_with_synonyms(self, keyword: str) -> List[str]:
        """
        Expand a keyword with its synonyms and map synonyms back to topics.
        Uses module-level LRU cache for performance.

        Args:
            keyword: Original keyword

        Returns:
            List of keyword variations including synonyms and mapped topics
        """
        keyword_lower = keyword.lower().strip()
        # Use cached function - returns tuple, convert to list
        return list(_expand_keyword_cached(keyword_lower, self._synonyms_tuple))
    
    def should_match_product(self, semantic_product: str, taxonomy_product: str) -> bool:
        """
        Check if a semantic file Product should match a taxonomy Product.

        Args:
            semantic_product: Product value from semantic carriers file
            taxonomy_product: Product value from taxonomy row

        Returns:
            True if the products should match
        """
        # Normalize empty/NaN values
        sem_prod = '' if pd.isna(semantic_product) else str(semantic_product).strip()
        tax_prod = '' if pd.isna(taxonomy_product) else str(taxonomy_product).strip()

        # If taxonomy product is empty/General/"Something Else", match with ANY semantic product
        # These are generic/shared topics that apply to all products
        if tax_prod == '' or tax_prod.lower() == 'something else':
            return True

        # Exact product match
        if sem_prod == tax_prod:
            return True

        # Allow "Other" semantic product to match any taxonomy product
        if sem_prod == 'Other':
            return True

        return False

    def find_topic_matches(self, keyword: str, semantic_product: str = None,
                           track_near_misses: bool = False, source: str = 'unknown'):
        """
        Find matching topics for a given keyword.

        Source-aware thresholds: Title keywords use a lower threshold (threshold - 10,
        min 70) to catch near-matches that are still meaningful. URL keywords use the
        normal threshold but get a "Low Trust" relevance label at borderline scores.

        Args:
            keyword: Keyword to match
            semantic_product: Product from semantic file to filter taxonomy rows (optional)
            track_near_misses: If True, also return near-miss entries (score >= 50 but below threshold)
            source: Keyword source — 'title', 'summary', 'description', 'url', or 'unknown'

        Returns:
            List of matching taxonomy entries with similarity scores.
            If track_near_misses=True, returns (matches, near_misses) tuple.
        """
        # Source-specific thresholds
        if source == 'title':
            effective_threshold = max(70, self.similarity_threshold - 10)
        else:
            effective_threshold = self.similarity_threshold

        matches = []
        near_misses = [] if track_near_misses else None
        seen_topics = set()  # Track added topics to avoid duplicates
        keyword_variations = self.expand_with_synonyms(keyword)

        # Fuzzy matching — all matches go through the threshold check
        # OPTIMIZATION: Filter to relevant entries BEFORE the loop
        # This reduces fuzzy comparisons by 50-80% when product is known
        if semantic_product is not None:
            # Get entries for the specific product
            product_entries = self._product_lookup.get(semantic_product, [])
            # Also include entries with empty product (matches any semantic product)
            empty_product_entries = self._product_lookup.get('', [])
            # Also include "Something Else" entries (matches any semantic product)
            something_else_entries = self._product_lookup.get('Something Else', [])
            # Combine all relevant entries
            entries_to_check = product_entries + empty_product_entries + something_else_entries
        else:
            # No product filter - check all entries
            entries_to_check = self.taxonomy_lookup

        for tax_entry in entries_to_check:
            # Skip duplicates
            topic_key = (tax_entry['product'], tax_entry['topic'])
            if topic_key in seen_topics:
                continue

            # Use pre-computed lowercase topic
            topic_lower = tax_entry['topic_lower']
            max_score = 0

            # Check similarity against all keyword variations
            for variation in keyword_variations:
                score = fuzz.ratio(variation, topic_lower)
                max_score = max(max_score, score)

            if max_score >= effective_threshold:
                seen_topics.add(topic_key)
                matches.append({
                    **tax_entry,
                    'similarity_score': max_score,
                })
            elif track_near_misses and max_score >= 50:
                near_misses.append({
                    **tax_entry,
                    'similarity_score': max_score,
                    'rejection_reason': f'Below threshold ({max_score}% < {effective_threshold}%)'
                })

        # Sort by similarity score (highest first)
        matches.sort(key=lambda x: x['similarity_score'], reverse=True)
        if track_near_misses:
            near_misses.sort(key=lambda x: x['similarity_score'], reverse=True)
            return matches, near_misses
        return matches
    
    def extract_summary_terms(self, summary_text: str) -> List[str]:
        """
        Extract meaningful multi-word phrases from Summary column.

        Only extracts 2-3 word phrases (not single words) to avoid generic
        terms like "data", "security", "guide" that trigger false matches
        via synonym substring expansion.

        Args:
            summary_text: The summary text to extract terms from

        Returns:
            List of extracted phrases (max 15)
        """
        if pd.isna(summary_text) or not summary_text:
            return []

        # Stopwords to filter out
        stopwords = {'the', 'and', 'or', 'a', 'an', 'is', 'are', 'in', 'on', 'of',
                     'to', 'for', 'with', 'by', 'this', 'that', 'from', 'as', 'at',
                     'be', 'can', 'their', 'they', 'you', 'your', 'it', 'its',
                     'has', 'have', 'been', 'being', 'will', 'would', 'could',
                     'should', 'may', 'might', 'must', 'shall', 'into', 'also',
                     'such', 'than', 'then', 'when', 'where', 'which', 'while',
                     'about', 'after', 'before', 'between', 'through', 'during',
                     'under', 'over', 'above', 'below', 'each', 'every', 'both',
                     'either', 'neither', 'other', 'another', 'some', 'any', 'all',
                     'most', 'more', 'less', 'many', 'much', 'few', 'several',
                     'not', 'but', 'if', 'so', 'no', 'nor', 'too', 'very',
                     'just', 'only', 'own', 'same', 'how', 'what', 'why',
                     'does', 'did', 'do', 'was', 'were', 'had', 'need',
                     'provides', 'including', 'ensure', 'using', 'based',
                     'within', 'without', 'along', 'among', 'upon'}

        # Clean words
        words = str(summary_text).lower().split()
        clean_words = []
        for w in words:
            w = w.strip('.,!?;:()[]{}"\'-')
            if w and not w.isdigit():
                clean_words.append(w)

        # Extract 2-3 word phrases where all words are meaningful
        phrases = []
        seen = set()
        for n in [2, 3]:
            for i in range(len(clean_words) - n + 1):
                ngram = clean_words[i:i + n]
                # All words must be non-stopwords and >= 3 chars
                if all(w not in stopwords and len(w) >= 3 for w in ngram):
                    phrase = ' '.join(ngram)
                    if phrase not in seen:
                        seen.add(phrase)
                        phrases.append(phrase)

        return phrases[:15]  # Limit to 15 phrases

    def extract_keywords(self, row):
        """
        Extract all keywords from a semantic carriers row.

        Args:
            row: DataFrame row

        Returns:
            Tuple of (keywords, sources) — parallel lists.
            source is 'title'/'summary'/'description'/'url'/'unknown' (from Source N column if present).
            Backward compatible: files without Source columns return 'unknown' for all sources.
        """
        keywords = []
        sources = []

        # Extract from Keyword 1 through Keyword 12 (if present)
        for i in range(1, 13):
            col_name = f'Keyword {i}'
            src_col = f'Source {i}'
            if col_name in row.index and pd.notna(row[col_name]):
                kw = str(row[col_name]).strip()
                if kw:
                    keywords.append(kw)
                    # Read source if available, otherwise default to 'unknown'
                    if src_col in row.index and pd.notna(row[src_col]):
                        src = str(row[src_col]).strip().lower()
                        sources.append(src if src else 'unknown')
                    else:
                        sources.append('unknown')

        # Optionally extract from Summary column (treated as 'summary' source)
        if self.include_summary and 'Summary' in row.index:
            summary_terms = self.extract_summary_terms(row['Summary'])
            keywords.extend(summary_terms)
            sources.extend(['summary'] * len(summary_terms))

        return keywords, sources

    def clean_url(self, url: str) -> str:
        """
        Clean URL by stripping anchor fragments (#...).

        This is done BEFORE matching to ensure clean URLs are used for
        keyword extraction, relevance calculation, and deduplication.

        Args:
            url: Original URL

        Returns:
            URL with anchor fragment removed
        """
        if not url or pd.isna(url):
            return ''
        url = str(url)
        # Strip anchor fragment (everything after #)
        if '#' in url:
            url = url.split('#')[0]
        return url

    def process_matching(self) -> pd.DataFrame:
        """
        Main processing: match all URLs to taxonomy topics.

        Returns:
            DataFrame with matched results (includes unmapped URLs)
        """
        print("\nProcessing URL-to-taxonomy matching...")
        results = []
        seen_combinations = set()  # For deduplication

        total_urls = len(self.semantic_df)
        urls_with_matches = 0
        unmapped_urls = []
        urls_cleaned = 0  # Track how many URLs had anchors stripped

        # Near-miss tracking for keyword recommendations
        self._keyword_near_misses = {}

        for idx, row in self.semantic_df.iterrows():
            original_url = row.get('URL', '')
            # Clean URL by stripping anchor fragments BEFORE any processing
            url = self.clean_url(original_url)
            if url != original_url:
                urls_cleaned += 1
            keywords, sources = self.extract_keywords(row)

            # Get Product from semantic file for filtering
            semantic_product = row.get('Product', None)

            # Capture additional columns to carry through to output
            title = row.get('Title', '') if pd.notna(row.get('Title', '')) else ''
            description = row.get('Description', '') if pd.notna(row.get('Description', '')) else ''
            summary = row.get('Summary', '') if pd.notna(row.get('Summary', '')) else ''

            if self.debug:
                print(f"\n[DEBUG] === URL: {url} ===")
                sem_prod_str = semantic_product if semantic_product and not pd.isna(semantic_product) else '(none)'
                print(f"[DEBUG] Product: {sem_prod_str}")
                kw_src_pairs = list(zip(keywords, sources))
                print(f"[DEBUG] Keywords ({len(keywords)}): {kw_src_pairs}")

            url_has_match = False
            had_matches_before_product_filter = False

            # Track which keywords produced matches for Unmatched_Keywords column
            matched_keywords = set()
            url_result_start_idx = len(results)

            # Process each keyword with its source
            for keyword, source in zip(keywords, sources):
                if self.debug:
                    # Show synonym expansion
                    expanded = self.expand_with_synonyms(keyword)
                    added_syns = [v for v in expanded if v.lower() != keyword.lower().strip()]
                    if source != 'unknown':
                        src_tag = f'[{source}]'
                    else:
                        src_tag = ''
                    if added_syns:
                        print(f"[DEBUG]   KW '{keyword}'{src_tag} -> expanded with: {added_syns}")
                    else:
                        print(f"[DEBUG]   KW '{keyword}'{src_tag} -> no synonym expansion")

                matches = self.find_topic_matches(keyword, semantic_product, source=source)

                if self.debug:
                    if matches:
                        for m in matches:
                            print(f"[DEBUG]     MATCH: '{m['topic']}' score={m['similarity_score']} ({m['product']}/{m['segment']})")
                    else:
                        # Show nearest miss for unmatched keywords
                        _, debug_near_misses = self.find_topic_matches(keyword, semantic_product, track_near_misses=True, source=source)
                        eff_thresh = max(70, self.similarity_threshold - 10) if source == 'title' else self.similarity_threshold
                        print(f"[DEBUG]     NO MATCH (below {eff_thresh}% threshold, source={source})")
                        if debug_near_misses:
                            best_miss = max(debug_near_misses, key=lambda x: x['similarity_score'])
                            print(f"[DEBUG]     Nearest miss: '{best_miss['topic']}' score={best_miss['similarity_score']}")

                # Check if there would be matches without product filter
                if not matches and semantic_product:
                    unfiltered_matches = self.find_topic_matches(keyword, None, source=source)
                    if unfiltered_matches:
                        had_matches_before_product_filter = True

                for match in matches:
                    # Override "Something Else" with product detected from URL
                    product = match['product']
                    domain = match['domain']
                    segment = match['segment']
                    if product == 'Something Else':
                        url_product = self.extract_product_from_url(url)
                        if url_product:
                            product = url_product
                            # Reassess Domain/Segment: use O(1) lookup instead of linear scan
                            lookup_key = (url_product, match['topic'])
                            if lookup_key in self._product_topic_lookup:
                                entry = self._product_topic_lookup[lookup_key]
                                domain = entry['domain']
                                segment = entry['segment']

                    # Create unique combination key for deduplication
                    combo_key = (url, product, domain,
                                segment, match['topic'])

                    # Only add if not seen before (deduplication)
                    if combo_key not in seen_combinations:
                        seen_combinations.add(combo_key)
                        results.append({
                            'URL': url,
                            'Title': title,
                            'Description': description,
                            'Summary': summary,
                            'Product': product,
                            'Domain': domain,
                            'Segment': segment,
                            'Topic': match['topic'],
                            'Score': match['similarity_score'],
                            'Source': source,
                            'Unmapped_Reason': ''
                        })
                        url_has_match = True
                        matched_keywords.add(keyword)

            # Compute unmatched keywords and backfill all result rows for this URL
            unmatched_pairs = [(kw, src) for kw, src in zip(keywords, sources) if kw not in matched_keywords]
            unmatched = [kw for kw, _ in unmatched_pairs]
            if self.debug and unmatched:
                print(f"[DEBUG]   Unmatched keywords: {unmatched}")
            unmatched_str = ', '.join(unmatched)
            for i in range(url_result_start_idx, len(results)):
                results[i]['Unmatched_Keywords'] = unmatched_str

            # Track near-misses for unmatched keywords (for Keyword Recommendations)
            for kw, src in unmatched_pairs:
                _, near_miss_list = self.find_topic_matches(kw, semantic_product, track_near_misses=True, source=src)

                # Check if product filter excluded matches
                if semantic_product:
                    unfiltered = self.find_topic_matches(kw, None, source=src)
                    filtered = self.find_topic_matches(kw, semantic_product, source=src)
                    if unfiltered and not filtered:
                        for m in unfiltered[:1]:
                            near_miss_list.append({
                                **m,
                                'rejection_reason': f'Product filtered (exists in {m["product"]})'
                            })

                key = kw.lower().strip()
                if key not in self._keyword_near_misses:
                    self._keyword_near_misses[key] = {
                        'keyword': kw,
                        'nearest_topic': None,
                        'nearest_score': 0,
                        'nearest_product': '',
                        'nearest_domain': '',
                        'nearest_segment': '',
                        'rejection_reason': 'No close match (<50%)',
                        'urls': [],
                        'frequency': 0
                    }
                entry = self._keyword_near_misses[key]
                entry['frequency'] += 1
                if len(entry['urls']) < 5:
                    entry['urls'].append(url)

                if near_miss_list:
                    best = max(near_miss_list, key=lambda x: x['similarity_score'])
                    if best['similarity_score'] > entry['nearest_score']:
                        entry['nearest_topic'] = best['topic']
                        entry['nearest_score'] = best['similarity_score']
                        entry['nearest_product'] = best['product']
                        entry['nearest_domain'] = best['domain']
                        entry['nearest_segment'] = best['segment']
                        entry['rejection_reason'] = best.get('rejection_reason', 'Below threshold')

            if url_has_match:
                urls_with_matches += 1
            else:
                # Determine unmapped reason
                if not keywords:
                    unmapped_reason = 'No keywords extracted from row'
                elif had_matches_before_product_filter:
                    unmapped_reason = f'Product filter excluded matches (semantic Product: {semantic_product})'
                else:
                    unmapped_reason = f'No matches above {self.similarity_threshold}% threshold'

                # Add unmapped URL to results with empty taxonomy fields
                unmapped_urls.append(url)
                results.append({
                    'URL': url,
                    'Title': title,
                    'Description': description,
                    'Summary': summary,
                    'Product': '',
                    'Domain': 'UNMAPPED',
                    'Segment': '',
                    'Topic': '',
                    'Score': 0,
                    'Exact_Match': False,
                    'Unmapped_Reason': unmapped_reason,
                    'Unmatched_Keywords': unmatched_str
                })
            
            # Progress indicator
            if (idx + 1) % 50 == 0:
                print(f"  Processed {idx + 1}/{total_urls} URLs...")

        print(f"\nMatching complete!")
        print(f"  URLs with matches: {urls_with_matches}/{total_urls} ({urls_with_matches/total_urls*100:.1f}%)")
        print(f"  Unmapped URLs: {len(unmapped_urls)}/{total_urls} ({len(unmapped_urls)/total_urls*100:.1f}%)")
        if urls_cleaned > 0:
            print(f"  URLs cleaned (anchors stripped): {urls_cleaned}")
        print(f"  Total output rows: {len(results)}")
        print(f"  Average matches per URL: {len(results)/total_urls:.2f}")
        
        results_df = pd.DataFrame(results)

        # Apply consolidation if enabled
        if self.consolidate_topics:
            print("\n  Applying topic consolidation...")
            results_df = self.consolidate_results(results_df)

        return results_df

    def extract_url_keywords(self, url: str) -> set:
        """
        Extract meaningful words from URL path for relevance checking.
        Uses caching to avoid redundant URL parsing.

        Args:
            url: The URL to extract keywords from

        Returns:
            Set of lowercase keywords from the URL path
        """
        # Check cache first
        if url in self._url_keywords_cache:
            return self._url_keywords_cache[url]

        import re
        from urllib.parse import urlparse, unquote
        try:
            path = urlparse(unquote(unquote(url))).path
        except Exception:
            path = url  # Fallback to using the URL as-is

        # Split by / and _ to get individual words
        words = []
        for segment in path.split('/'):
            # Replace separators with spaces
            segment_cleaned = segment.replace('_', ' ').replace('-', ' ').replace('+', ' ')
            for w in segment_cleaned.split():
                # Strip leading numeric prefixes (e.g., "15Journals" -> "Journals")
                w = re.sub(r'^\d+', '', w)
                if not w:
                    continue
                # CamelCase split (e.g., "ChartOfAccounts" -> ["Chart", "Of", "Accounts"])
                camel_parts = re.split(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', w)
                words.extend(camel_parts)

        # Clean and lowercase, filter short words (<=2 chars) and numbers
        keywords = set()
        for w in words:
            w_clean = w.lower().strip()
            if len(w_clean) > 2 and not w_clean.isdigit():
                keywords.add(w_clean)

        # Cache the result
        self._url_keywords_cache[url] = keywords
        return keywords

    def extract_product_from_url(self, url: str) -> str:
        """Extract a known taxonomy product name from URL path.

        Converts each taxonomy product name to URL form (spaces to underscores)
        and checks if it appears in the URL. Products are checked longest-first
        to avoid partial matches.

        Args:
            url: The URL to check

        Returns:
            Matching taxonomy product name, or None if no match found
        """
        url_lower = url.lower()
        # Use pre-computed product URL forms
        for product, url_form in self._product_url_forms:
            if url_form in url_lower:
                return product
        return None

    def get_product_taxonomy_entries(self, product: str) -> List[Dict]:
        """Get all taxonomy entries for a specific product.

        Args:
            product: Product name to filter by

        Returns:
            List of taxonomy entries for this product
        """
        # Use pre-computed product lookup
        return self._product_lookup.get(product, [])

    def find_best_product_match(self, keywords: List[str], product: str) -> Optional[Dict]:
        """Find the best matching topic from a product's taxonomy entries.

        This is used to ensure at least one match from the product's own domain,
        even if the fuzzy score is below the normal threshold.

        Args:
            keywords: List of keywords to match against
            product: Product name to get taxonomy entries for

        Returns:
            Best matching taxonomy entry with score, or None if no keywords
        """
        if not keywords:
            return None

        product_entries = self.get_product_taxonomy_entries(product)
        if not product_entries:
            return None

        best_match = None
        best_score = 0

        for keyword in keywords:
            keyword_variations = self.expand_with_synonyms(keyword)

            for entry in product_entries:
                # Use pre-computed lowercase topic
                topic_lower = entry['topic_lower']

                for variation in keyword_variations:
                    score = fuzz.ratio(variation, topic_lower)
                    if score > best_score:
                        best_score = score
                        best_match = {
                            **entry,
                            'similarity_score': score,
                            'is_product_match': True  # Flag to indicate this is a guaranteed product match
                        }

        # Return best match if it has any reasonable similarity (>= 50)
        # This ensures we get the product's domain even with weak keyword matches
        if best_match and best_score >= 50:
            return best_match

        # If no good keyword match, return the first topic from product's taxonomy
        # with a base score indicating it's a product-based match
        if product_entries:
            return {
                **product_entries[0],
                'similarity_score': 50,  # Base score for product match
                'is_product_match': True
            }

        return None

    def calculate_relevance(self, score: int, topic: str = None, url_keywords: set = None,
                            source: str = 'unknown') -> str:
        """
        Calculate relevance category using score, URL content analysis, and keyword source.

        Source-aware rules:
        - 'title' keywords: lower threshold (70+) and one-tier relevance boost when not in URL
        - 'url' keywords: score 80-84 not in URL → 'Low Trust' instead of 'Low Relevance'
        - Other sources: standard hybrid relevance

        Args:
            score: Similarity score (0-100)
            topic: The matched topic name (optional, for URL content check)
            url_keywords: Set of keywords extracted from URL (optional)
            source: Keyword source — 'title', 'summary', 'description', 'url', or 'unknown'

        Returns:
            Relevance category string
        """
        # If no URL analysis requested, fall back to score-only
        if topic is None or url_keywords is None:
            if score >= 95:
                return 'Highly Relevant'
            elif score >= 90:
                return 'Relevant'
            elif score >= 85:
                return 'Somewhat Relevant'
            elif score >= 80:
                return 'Moderate'
            elif score > 0:
                return 'Weak'
            else:
                return 'Unmapped'

        # Hybrid approach: check if topic words appear in URL
        topic_words = set(topic.lower().split())
        topic_in_url = bool(topic_words & url_keywords)  # Any word overlap?

        if score >= 90 and topic_in_url:
            return 'Best Match'
        elif score >= 85 and topic_in_url:
            return 'Highly Relevant'
        elif score >= 70 and topic_in_url and source == 'title':
            return 'Highly Relevant'  # Boosted: title keyword with topic in URL
        elif topic_in_url:
            return 'Relevant'
        elif score >= 90:
            return 'Somewhat Relevant'
        elif score >= 85:
            return 'Tangential'
        elif score >= 70 and source == 'title':
            return 'Tangential'  # Boosted: title keyword, not in URL but meaningful match
        elif score >= 80:
            if source == 'url':
                return 'Low Trust'  # URL path keywords at borderline scores are less reliable
            return 'Low Relevance'
        elif score > 0:
            return 'Weak'
        else:
            return 'Unmapped'

    def consolidate_results(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """
        Consolidate multiple topic matches into single row per URL-Segment group.

        Args:
            results_df: DataFrame in one-row-per-topic format

        Returns:
            DataFrame with topics as columns (Topic_1, Topic_2, ..., Top_Score, Top_Relevance)
        """
        # Handle unmapped URLs separately
        unmapped = results_df[results_df['Domain'] == 'UNMAPPED'].copy()
        mapped = results_df[results_df['Domain'] != 'UNMAPPED'].copy()

        if len(mapped) == 0:
            # Add score columns to unmapped
            unmapped['Top_Score'] = 0
            unmapped['Top_Relevance'] = 'Unmapped'
            if 'Topic' in unmapped.columns:
                unmapped = unmapped.drop('Topic', axis=1)
            if 'Score' in unmapped.columns:
                unmapped = unmapped.drop('Score', axis=1)
            return unmapped

        # Group by (URL, Product, Domain, Segment)
        grouped = mapped.groupby(['URL', 'Product', 'Domain', 'Segment'],
                                dropna=False, sort=False)

        consolidated_rows = []
        max_topics = 0

        for (url, product, domain, segment), group in grouped:
            topics = group['Topic'].tolist()  # Preserves discovery order
            scores = group['Score'].tolist()  # Get corresponding scores
            group_sources = group['Source'].tolist() if 'Source' in group.columns else ['unknown'] * len(topics)

            # Get Title, Description, Summary from first row of group (same for all rows with same URL)
            title = group['Title'].iloc[0] if 'Title' in group.columns else ''
            description = group['Description'].iloc[0] if 'Description' in group.columns else ''
            summary = group['Summary'].iloc[0] if 'Summary' in group.columns else ''

            # Filter out auto-added segment topics (segment name should not appear as topic)
            filtered_triples = [(t, s, src) for t, s, src in zip(topics, scores, group_sources) if t != segment]

            # Skip rows with no actual topics (only had segment-as-topic)
            if not filtered_triples:
                continue

            # Unzip the filtered triples
            topics, scores, group_sources = zip(*filtered_triples)
            topics = list(topics)
            scores = list(scores)
            group_sources = list(group_sources)

            max_topics = max(max_topics, len(topics))

            row = {
                'URL': url,
                'Title': title,
                'Description': description,
                'Summary': summary,
                'Product': product,
                'Domain': domain,
                'Segment': segment
            }

            # Add topics as Topic_1, Topic_2, etc.
            for i, topic in enumerate(topics, start=1):
                row[f'Topic_{i}'] = topic

            # Add summary score columns with hybrid relevance (score + URL content check)
            # Find the top scoring topic for relevance calculation
            top_idx = scores.index(max(scores))
            top_score = scores[top_idx]
            top_topic = topics[top_idx]
            top_source = group_sources[top_idx]

            # Extract keywords from URL for hybrid relevance calculation
            url_keywords = self.extract_url_keywords(url)

            row['Top_Score'] = top_score
            row['Top_Relevance'] = self.calculate_relevance(top_score, top_topic, url_keywords, source=top_source)
            row['Unmapped_Reason'] = ''  # Matched rows have no unmapped reason
            row['Unmatched_Keywords'] = group['Unmatched_Keywords'].iloc[0] if 'Unmatched_Keywords' in group.columns else ''

            consolidated_rows.append(row)

        consolidated_df = pd.DataFrame(consolidated_rows)

        # Rank and limit to top N per URL
        if len(consolidated_df) > 0 and self.top_n > 0:
            # Compute ranking columns
            def rank_row(row):
                url_product = self.extract_product_from_url(row['URL'])
                domain = str(row.get('Domain', '')).strip()
                is_general_domain = domain.lower() in ['general', 'general ']
                product_matches = url_product and row['Product'] == url_product
                score = row.get('Top_Score', 0)

                # Check if topic appears in content (URL, Title, Summary, Description)
                # This validates relevance beyond just fuzzy matching
                url_kw = self.extract_url_keywords(row['URL'])

                # Also extract keywords from Title, Summary, Description
                content_keywords = set(url_kw)
                for field in ['Title', 'Summary', 'Description']:
                    field_val = row.get(field, '')
                    if pd.notna(field_val) and str(field_val).strip():
                        # Extract words from field using pre-compiled regex (single pass)
                        field_text = _SEPARATOR_PATTERN.sub(' ', str(field_val).lower())
                        content_keywords.update(w for w in field_text.split() if len(w) >= 3)

                # Count topic words found in content
                relevance_count = 0
                topic_found_in_content = False
                for col in [c for c in row.index if c.startswith('Topic_')]:
                    if pd.notna(row[col]) and row[col] != '':
                        topic_words = set(str(row[col]).lower().split())
                        matches_found = len(topic_words & content_keywords)
                        relevance_count += matches_found
                        if matches_found > 0:
                            topic_found_in_content = True

                # Priority levels (lower = better):
                # 0 = Product matches AND Domain is product-specific AND (topic in content OR score >= 80%)
                # 1 = Product matches AND Domain is General AND topic in content
                # 2 = Product matches but topic NOT in content (weak relevance)
                # 3 = Product doesn't match
                # 4 = Weak score AND topic NOT in content (demoted - likely irrelevant)

                if product_matches and not is_general_domain:
                    if topic_found_in_content or score >= 80:
                        product_priority = 0  # Boost: product-specific + validated relevance
                    else:
                        product_priority = 2  # Demote: product-specific but unvalidated weak match
                elif product_matches:
                    if topic_found_in_content:
                        product_priority = 1  # General domain but topic confirmed in content
                    else:
                        product_priority = 2  # General domain, topic not in content
                else:
                    product_priority = 3  # Product doesn't match

                # Further demote weak scores with no content validation
                if score < 75 and not topic_found_in_content:
                    product_priority = 4  # Likely irrelevant match

                return pd.Series({
                    '_prod_priority': product_priority,
                    '_neg_score': -score,
                    '_neg_url_rel': -relevance_count
                })

            rank_cols = consolidated_df.apply(rank_row, axis=1)
            consolidated_df = pd.concat([consolidated_df, rank_cols], axis=1)
            consolidated_df = consolidated_df.sort_values(
                ['URL', '_prod_priority', '_neg_score', '_neg_url_rel']
            )

            # Assign rank per URL and limit to top N
            consolidated_df['Rank'] = consolidated_df.groupby('URL').cumcount() + 1
            consolidated_df = consolidated_df[consolidated_df['Rank'] <= self.top_n]
            consolidated_df = consolidated_df.drop(
                ['_prod_priority', '_neg_score', '_neg_url_rel'], axis=1
            )

        # Ensure all topic columns exist (fill missing with empty string)
        for i in range(1, max_topics + 1):
            col_name = f'Topic_{i}'
            if col_name not in consolidated_df.columns:
                consolidated_df[col_name] = ''

        # Fill NaN with empty strings for cleaner Excel output
        consolidated_df = consolidated_df.fillna('')

        # Re-add unmapped URLs with empty topic columns and score columns
        if len(unmapped) > 0:
            for i in range(1, max_topics + 1):
                unmapped[f'Topic_{i}'] = ''
            unmapped['Top_Score'] = 0
            unmapped['Top_Relevance'] = 'Unmapped'
            unmapped['Rank'] = 1
            if 'Topic' in unmapped.columns:
                unmapped = unmapped.drop('Topic', axis=1)
            if 'Score' in unmapped.columns:
                unmapped = unmapped.drop('Score', axis=1)
            if 'Exact_Match' in unmapped.columns:
                unmapped = unmapped.drop('Exact_Match', axis=1)  # safety cleanup if present
            consolidated_df = pd.concat([consolidated_df, unmapped], ignore_index=True)

        # Reorder columns: URL, Title, Description, Summary, Product, Domain, Segment, Topic_1...Topic_N, Top_Score, Top_Relevance, Unmapped_Reason, Unmatched_Keywords, Rank
        base_cols = ['URL', 'Title', 'Description', 'Summary', 'Product', 'Domain', 'Segment']
        topic_cols = [f'Topic_{i}' for i in range(1, max_topics + 1)]
        score_cols = ['Top_Score', 'Top_Relevance', 'Unmapped_Reason', 'Unmatched_Keywords', 'Rank']
        final_col_order = base_cols + topic_cols + score_cols
        # Only include columns that exist in the dataframe
        final_col_order = [c for c in final_col_order if c in consolidated_df.columns]
        consolidated_df = consolidated_df[final_col_order]

        print(f"  Consolidated to {len(consolidated_df)} rows (top {self.top_n} per URL) with up to {max_topics} topics per row")

        return consolidated_df

    def save_output(self, results_df: pd.DataFrame):
        """
        Save results to Excel file with keyword recommendations.

        Args:
            results_df: DataFrame with matched results
        """
        from generate_topic_recommendations import sanitize_dataframe

        print(f"\nSaving results to {self.output_file}...")

        # Generate keyword recommendations
        self._recommendations_df = self.generate_keyword_recommendations()

        # Write with ExcelWriter for multi-sheet support
        with pd.ExcelWriter(self.output_file, engine='openpyxl') as writer:
            sanitize_dataframe(results_df).to_excel(writer, sheet_name='Results', index=False)
            if self._recommendations_df is not None and len(self._recommendations_df) > 0:
                sanitize_dataframe(self._recommendations_df).to_excel(
                    writer, sheet_name='Keyword Recommendations', index=False
                )

        # Print keyword recommendations summary
        if self._recommendations_df is not None and len(self._recommendations_df) > 0:
            rec_df = self._recommendations_df
            total_near_misses = len(getattr(self, '_keyword_near_misses', {}))
            high_count = len(rec_df[rec_df['Priority'] == 'HIGH'])
            medium_count = len(rec_df[rec_df['Priority'] == 'MEDIUM'])
            new_topic_count = len(rec_df[rec_df['Recommendation'] == 'Consider new topic'])
            noise_filtered = total_near_misses - len(rec_df)
            print(f"\nKeyword Recommendations: {total_near_misses} unmatched keywords analyzed")
            print(f"  HIGH priority (add as synonym): {high_count}")
            print(f"  MEDIUM priority (review): {medium_count}")
            print(f"  New topic candidates: {new_topic_count}")
            print(f"  Noise filtered: {noise_filtered}")

        print(f"Output saved successfully!")
        print(f"  File: {os.path.abspath(self.output_file)}")

        # Show unmapped count in output
        unmapped_count = len(results_df[results_df['Domain'] == 'UNMAPPED'])
        if unmapped_count > 0:
            print(f"[!] Note: {unmapped_count} unmapped URLs included in output")
            print(f"    Filter by Domain='UNMAPPED' to review these URLs")
    
    def generate_keyword_recommendations(self) -> Optional[pd.DataFrame]:
        """
        Generate keyword recommendations from near-miss data collected during matching.

        Processes self._keyword_near_misses into a DataFrame with actionable recommendations
        for each unmatched keyword (add as synonym, consider new topic, or noise).

        Returns:
            DataFrame with keyword recommendations, or None if no data
        """
        if not hasattr(self, '_keyword_near_misses') or not self._keyword_near_misses:
            return None

        rows = []
        threshold = self.similarity_threshold

        for key, entry in self._keyword_near_misses.items():
            keyword = entry['keyword']
            frequency = entry['frequency']
            nearest_topic = entry['nearest_topic'] or ''
            nearest_score = entry['nearest_score']
            rejection_reason = entry['rejection_reason']
            nearest_product = entry['nearest_product']
            nearest_domain = entry['nearest_domain']
            nearest_segment = entry['nearest_segment']

            # Check if keyword is already a synonym for the nearest topic
            already_in_synonyms = 'No'
            if nearest_topic:
                topic_synonyms = self.synonyms.get(nearest_topic, [])
                if keyword.lower() in [s.lower() for s in topic_synonyms]:
                    already_in_synonyms = 'Yes'

            # Classification logic
            if 'Product filtered' in rejection_reason:
                recommendation = f'Exists in other product ({nearest_product}) - check taxonomy structure'
                priority = 'MEDIUM'
            elif nearest_score >= (threshold - 5) and frequency >= 3:
                recommendation = f'Add as synonym to [{nearest_topic}]'
                priority = 'HIGH'
            elif nearest_score >= (threshold - 15) and frequency >= 2:
                recommendation = f'Add as synonym to [{nearest_topic}]'
                priority = 'MEDIUM'
            elif nearest_score >= 50:
                recommendation = f'Review - possible synonym for [{nearest_topic}]'
                priority = 'LOW'
            elif frequency >= 5 and nearest_score < 50:
                recommendation = 'Consider new topic'
                priority = 'MEDIUM'
            else:
                recommendation = 'Noise - ignore'
                priority = 'NOISE'

            row = {
                'Keyword': keyword,
                'Frequency': frequency,
                'Nearest_Topic': nearest_topic,
                'Nearest_Score': nearest_score,
                'Rejection_Reason': rejection_reason,
                'Recommendation': recommendation,
                'Target_Product': nearest_product,
                'Target_Domain': nearest_domain,
                'Target_Segment': nearest_segment,
                'Priority': priority,
                'Already_In_Synonyms': already_in_synonyms,
            }

            # Add up to 3 sample URLs
            for i in range(3):
                url = entry['urls'][i] if i < len(entry['urls']) else ''
                row[f'Sample_URL_{i+1}'] = url

            rows.append(row)

        if not rows:
            return None

        df = pd.DataFrame(rows)

        # Filter out NOISE
        df = df[df['Priority'] != 'NOISE'].copy()

        if len(df) == 0:
            return None

        # Sort: Priority (HIGH first) → Frequency (desc) → Score (desc)
        priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        df['_priority_sort'] = df['Priority'].map(priority_order)
        df = df.sort_values(['_priority_sort', 'Frequency', 'Nearest_Score'],
                           ascending=[True, False, False])
        df = df.drop('_priority_sort', axis=1)
        df = df.reset_index(drop=True)

        return df

    def run(self):
        """Execute the complete matching workflow."""
        print("=" * 60)
        print(f"NL Taxonomy Mapper V3 - Country: {self.country_code}")
        print("=" * 60)

        # Print configuration details
        country_info = next(c for c in self.country_config.get_available_countries()
                           if c['code'] == self.country_code)
        print(f"Country: {country_info['name']} ({country_info['language']})")
        print(f"Threshold: {self.similarity_threshold}%")
        print(f"Synonyms loaded: {len(self.synonyms)} terms")
        if self.include_summary:
            print(f"Summary column: ENABLED (extracting additional keywords)")
        if self.debug:
            print(f"Debug mode: ENABLED")
        if self.url_filter:
            print(f"URL filter: '{self.url_filter}'")
        if self.max_rows > 0:
            print(f"Max rows: {self.max_rows}")
        print("=" * 60)

        self.load_data()
        self.build_taxonomy_lookup()
        results_df = self.process_matching()
        self.save_output(results_df)

        print("\n" + "=" * 60)
        print("Process completed successfully!")
        print(f"Output saved to: {self.output_file}")
        print("=" * 60)


def get_threshold_from_user() -> int:
    """
    Prompt user for similarity threshold.
    
    Returns:
        int: Threshold value between 50-100
    """
    print("\n" + "=" * 60)
    print("SIMILARITY THRESHOLD SETTING")
    print("=" * 60)
    print("\nThe similarity threshold determines how closely keywords must")
    print("match taxonomy topics to be considered a match.")
    print("\nRecommendations:")
    print("  â€¢ 75-79: More lenient (more matches, some may be loose)")
    print("  â€¢ 80-85: Balanced (recommended for most cases)")
    print("  â€¢ 86-95: Stricter (fewer but higher quality matches)")
    print("\n" + "=" * 60)
    
    while True:
        try:
            user_input = input("\nEnter similarity threshold (50-100) [default: 80]: ").strip()
            
            # Use default if empty
            if not user_input:
                threshold = 80
                print(f"Using default threshold: {threshold}%")
                return threshold
            
            # Convert to integer
            threshold = int(user_input)
            
            # Validate range
            if 50 <= threshold <= 100:
                print(f"âœ“ Threshold set to: {threshold}%")
                return threshold
            else:
                print("âŒ Error: Please enter a value between 50 and 100")
                
        except ValueError:
            print("âŒ Error: Please enter a valid number")
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            exit(0)


def main():
    """Main entry point with CLI argument support."""
    parser = argparse.ArgumentParser(
        description='NL Taxonomy Mapper V3 - Multi-Country Support'
    )
    parser.add_argument(
        '-c', '--country',
        type=str,
        help='Country code (NL, SE, BE, etc.)',
        default=None
    )
    parser.add_argument(
        '-t', '--threshold',
        type=int,
        help='Similarity threshold (50-100)',
        default=None
    )
    parser.add_argument(
        '--semantic-file',
        type=str,
        help='Path to semantic carriers file (overrides config)',
        default=None
    )
    parser.add_argument(
        '--taxonomy-file',
        type=str,
        help='Path to taxonomy file (overrides config)',
        default=None
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output filename (country code auto-appended)',
        default=None
    )
    parser.add_argument(
        '-ct', '--consolidate-topics',
        action='store_true',
        help='Consolidate multiple topics into columns (Topic_1, Topic_2, ...)',
        default=None
    )
    parser.add_argument(
        '--use-summary',
        action='store_true',
        help='Extract keywords from Summary column if present (for crawler output)',
        default=False
    )
    parser.add_argument(
        '--top-n',
        type=int,
        help='Maximum results per URL (1-10, default 3)',
        default=3
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable per-keyword debug trace output',
        default=False
    )
    parser.add_argument(
        '--max-rows',
        type=int,
        help='Limit processing to first N rows (0 = all)',
        default=0
    )
    parser.add_argument(
        '--url-filter',
        type=str,
        help='Only process URLs containing this text',
        default=''
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("           NL TAXONOMY MAPPER V3 - SETUP")
    print("=" * 60)

    # Get threshold (CLI arg takes precedence, otherwise prompt)
    threshold = args.threshold
    if threshold is None:
        threshold = get_threshold_from_user()

    # Initialize and run the matcher
    try:
        matcher = TaxonomyMatcher(
            country_code=args.country,
            semantic_file=args.semantic_file,
            taxonomy_file=args.taxonomy_file,
            output_file=args.output,
            similarity_threshold=threshold,
            consolidate_topics=args.consolidate_topics,
            include_summary=args.use_summary,
            top_n=args.top_n,
            debug=args.debug,
            max_rows=args.max_rows,
            url_filter=args.url_filter
        )

        matcher.run()

    except Exception as e:
        print(f"\nâŒ Error: {e}")
        print("\nFor help, run: python taxonomy_matcher.py --help")
        exit(1)


if __name__ == "__main__":
    main()