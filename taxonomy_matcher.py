"""
NL Taxonomy Mapper V3
Matches URLs from semantic carriers to taxonomy topics using fuzzy string matching.
NOW WITH MULTI-COUNTRY SUPPORT!
"""

import pandas as pd
from rapidfuzz import fuzz
from typing import List, Dict, Tuple, Optional
import os
import argparse
from functools import lru_cache
from country_config import CountryConfig


# Module-level cached synonym expansion function
@lru_cache(maxsize=10000)
def _expand_keyword_cached(keyword_lower: str, synonyms_tuple: tuple) -> tuple:
    """
    Cached synonym expansion. Returns tuple of variations for hashability.

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

        # Original behavior: if topic name is in keyword, add synonyms
        if key_lower in keyword_lower:
            variations.extend([s.lower() for s in synonyms])

        # NEW: if keyword exactly matches a synonym, add the topic name
        for syn in synonyms:
            syn_lower = syn.lower()
            if syn_lower == keyword_lower or syn_lower in keyword_lower:
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
                 config_file: str = 'config.yaml'):
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
        
    def load_data(self):
        """Load Excel files into pandas DataFrames."""
        print(f"Loading {self.semantic_file}...")
        self.semantic_df = pd.read_excel(self.semantic_file)
        print(f"  Loaded {len(self.semantic_df)} URLs")
        
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

    def find_topic_matches(self, keyword: str, semantic_product: str = None) -> List[Dict]:
        """
        Find matching topics for a given keyword.

        Args:
            keyword: Keyword to match
            semantic_product: Product from semantic file to filter taxonomy rows (optional)

        Returns:
            List of matching taxonomy entries with similarity scores
        """
        matches = []
        keyword_variations = self.expand_with_synonyms(keyword)

        for tax_entry in self.taxonomy_lookup:
            # Filter by Product if semantic_product is provided
            if semantic_product is not None:
                if not self.should_match_product(semantic_product, tax_entry['product']):
                    continue

            # Use pre-computed lowercase topic
            topic_lower = tax_entry['topic_lower']
            max_score = 0

            # Check similarity against all keyword variations
            for variation in keyword_variations:
                score = fuzz.ratio(variation, topic_lower)
                max_score = max(max_score, score)

            if max_score >= self.similarity_threshold:
                matches.append({
                    **tax_entry,
                    'similarity_score': max_score
                })

        # Sort by similarity score (highest first)
        matches.sort(key=lambda x: x['similarity_score'], reverse=True)
        return matches
    
    def extract_summary_terms(self, summary_text: str) -> List[str]:
        """
        Extract meaningful terms from Summary column.

        Args:
            summary_text: The summary text to extract terms from

        Returns:
            List of extracted terms (max 20)
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
                     'most', 'more', 'less', 'many', 'much', 'few', 'several'}

        terms = []
        words = str(summary_text).lower().split()

        for word in words:
            # Remove punctuation
            word = word.strip('.,!?;:()[]{}"\'-')
            # Filter by length, stopwords, and digits
            if len(word) >= 4 and word not in stopwords and not word.isdigit():
                terms.append(word)

        return terms[:20]  # Limit to 20 terms

    def extract_keywords(self, row) -> List[str]:
        """
        Extract all keywords from a semantic carriers row.

        Args:
            row: DataFrame row

        Returns:
            List of keywords
        """
        keywords = []

        # Extract from Keyword 1 through Keyword 12 (if present)
        for i in range(1, 13):
            col_name = f'Keyword {i}'
            if col_name in row.index and pd.notna(row[col_name]):
                keywords.append(str(row[col_name]).strip())

        # Optionally extract from Summary column
        if self.include_summary and 'Summary' in row.index:
            summary_terms = self.extract_summary_terms(row['Summary'])
            keywords.extend(summary_terms)

        return keywords
    
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
        product_matches_added = 0  # Track how many product-based matches were added

        for idx, row in self.semantic_df.iterrows():
            url = row.get('URL', '')
            keywords = self.extract_keywords(row)

            # Get Product from semantic file for filtering
            semantic_product = row.get('Product', None)

            # Capture additional columns to carry through to output
            title = row.get('Title', '') if pd.notna(row.get('Title', '')) else ''
            description = row.get('Description', '') if pd.notna(row.get('Description', '')) else ''
            summary = row.get('Summary', '') if pd.notna(row.get('Summary', '')) else ''

            url_has_match = False
            had_matches_before_product_filter = False
            has_product_domain_match = False  # Track if we got a match from product's own domain

            # Process each keyword
            for keyword in keywords:
                matches = self.find_topic_matches(keyword, semantic_product)

                # Check if there would be matches without product filter
                if not matches and semantic_product:
                    unfiltered_matches = self.find_topic_matches(keyword, None)
                    if unfiltered_matches:
                        had_matches_before_product_filter = True

                for match in matches:
                    # Track if this match is from the product's ORIGINAL taxonomy row
                    # (before any "Something Else" override)
                    original_product = match['product']
                    if semantic_product and original_product == semantic_product:
                        has_product_domain_match = True

                    # Override "Something Else" with product detected from URL
                    product = match['product']
                    domain = match['domain']
                    segment = match['segment']
                    if product == 'Something Else':
                        url_product = self.extract_product_from_url(url)
                        if url_product:
                            product = url_product
                            # Reassess Domain/Segment: find this topic under the new product
                            for entry in self.taxonomy_lookup:
                                if entry['product'] == url_product and entry['topic'] == match['topic']:
                                    domain = entry['domain']
                                    segment = entry['segment']
                                    break

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
                            'Unmapped_Reason': ''
                        })
                        url_has_match = True

            # ENSURE PRODUCT DOMAIN MATCH: If we have a known product but no matches
            # from that product's own taxonomy row, add the best product-based match
            if semantic_product and not has_product_domain_match and keywords:
                product_match = self.find_best_product_match(keywords, semantic_product)
                if product_match:
                    combo_key = (url, product_match['product'], product_match['domain'],
                                product_match['segment'], product_match['topic'])

                    if combo_key not in seen_combinations:
                        seen_combinations.add(combo_key)
                        results.append({
                            'URL': url,
                            'Title': title,
                            'Description': description,
                            'Summary': summary,
                            'Product': product_match['product'],
                            'Domain': product_match['domain'],
                            'Segment': product_match['segment'],
                            'Topic': product_match['topic'],
                            'Score': product_match['similarity_score'],
                            'Unmapped_Reason': ''
                        })
                        url_has_match = True
                        product_matches_added += 1

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
                    'Unmapped_Reason': unmapped_reason
                })
            
            # Progress indicator
            if (idx + 1) % 50 == 0:
                print(f"  Processed {idx + 1}/{total_urls} URLs...")

        print(f"\nMatching complete!")
        print(f"  URLs with matches: {urls_with_matches}/{total_urls} ({urls_with_matches/total_urls*100:.1f}%)")
        print(f"  Unmapped URLs: {len(unmapped_urls)}/{total_urls} ({len(unmapped_urls)/total_urls*100:.1f}%)")
        print(f"  Product domain matches added: {product_matches_added} (guaranteed product domain coverage)")
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

        Args:
            url: The URL to extract keywords from

        Returns:
            Set of lowercase keywords from the URL path
        """
        from urllib.parse import urlparse
        try:
            path = urlparse(url).path
        except Exception:
            path = url  # Fallback to using the URL as-is

        # Split by / and _ to get individual words
        words = []
        for segment in path.split('/'):
            # Split each segment by underscore
            words.extend(segment.split('_'))
            # Also split by hyphen
            words.extend(segment.split('-'))

        # Clean and lowercase, filter short words (<=2 chars) and numbers
        keywords = set()
        for w in words:
            w_clean = w.lower().strip()
            if len(w_clean) > 2 and not w_clean.isdigit():
                keywords.add(w_clean)

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

    def calculate_relevance(self, score: int, topic: str = None, url_keywords: set = None) -> str:
        """
        Calculate relevance category using score AND URL content analysis (hybrid approach).

        Args:
            score: Similarity score (0-100)
            topic: The matched topic name (optional, for URL content check)
            url_keywords: Set of keywords extracted from URL (optional)

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
        elif topic_in_url:
            return 'Relevant'
        elif score >= 90:
            return 'Somewhat Relevant'
        elif score >= 85:
            return 'Tangential'
        elif score >= 80:
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

            # Get Title, Description, Summary from first row of group (same for all rows with same URL)
            title = group['Title'].iloc[0] if 'Title' in group.columns else ''
            description = group['Description'].iloc[0] if 'Description' in group.columns else ''
            summary = group['Summary'].iloc[0] if 'Summary' in group.columns else ''

            # Filter out auto-added segment topics (segment name should not appear as topic)
            # Keep topics and scores paired during filtering
            filtered_pairs = [(t, s) for t, s in zip(topics, scores) if t != segment]

            # Skip rows with no actual topics (only had segment-as-topic)
            if not filtered_pairs:
                continue

            # Unzip the filtered pairs
            topics, scores = zip(*filtered_pairs)
            topics = list(topics)
            scores = list(scores)

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

            # Extract keywords from URL for hybrid relevance calculation
            url_keywords = self.extract_url_keywords(url)

            row['Top_Score'] = top_score
            row['Top_Relevance'] = self.calculate_relevance(top_score, top_topic, url_keywords)
            row['Unmapped_Reason'] = ''  # Matched rows have no unmapped reason

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

                # Priority levels (lower = better):
                # 0 = Product matches AND Domain is product-specific (not General) - BOOSTED
                # 1 = Product matches AND Domain is General
                # 2 = Product doesn't match
                if product_matches and not is_general_domain:
                    product_priority = 0  # Boost product-specific domain to top
                elif product_matches:
                    product_priority = 1  # Product matches but General domain
                else:
                    product_priority = 2  # Product doesn't match

                # Tiebreaker: count topic words found in URL
                url_kw = self.extract_url_keywords(row['URL'])
                relevance_count = 0
                for col in [c for c in row.index if c.startswith('Topic_')]:
                    if pd.notna(row[col]) and row[col] != '':
                        topic_words = set(str(row[col]).lower().split())
                        relevance_count += len(topic_words & url_kw)
                return pd.Series({
                    '_prod_priority': product_priority,
                    '_neg_score': -row.get('Top_Score', 0),
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
            consolidated_df = pd.concat([consolidated_df, unmapped], ignore_index=True)

        # Reorder columns: URL, Title, Description, Summary, Product, Domain, Segment, Topic_1...Topic_N, Top_Score, Top_Relevance, Unmapped_Reason, Rank
        base_cols = ['URL', 'Title', 'Description', 'Summary', 'Product', 'Domain', 'Segment']
        topic_cols = [f'Topic_{i}' for i in range(1, max_topics + 1)]
        score_cols = ['Top_Score', 'Top_Relevance', 'Unmapped_Reason', 'Rank']
        final_col_order = base_cols + topic_cols + score_cols
        # Only include columns that exist in the dataframe
        final_col_order = [c for c in final_col_order if c in consolidated_df.columns]
        consolidated_df = consolidated_df[final_col_order]

        print(f"  Consolidated to {len(consolidated_df)} rows (top {self.top_n} per URL) with up to {max_topics} topics per row")

        return consolidated_df

    def save_output(self, results_df: pd.DataFrame):
        """
        Save results to Excel file.
        
        Args:
            results_df: DataFrame with matched results
        """
        print(f"\nSaving results to {self.output_file}...")
        results_df.to_excel(self.output_file, index=False)
        print(f"Output saved successfully!")
        print(f"  File: {os.path.abspath(self.output_file)}")
        
        # Show unmapped count in output
        unmapped_count = len(results_df[results_df['Domain'] == 'UNMAPPED'])
        if unmapped_count > 0:
            print(f"[!] Note: {unmapped_count} unmapped URLs included in output")
            print(f"    Filter by Domain='UNMAPPED' to review these URLs")
    
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
            top_n=args.top_n
        )

        matcher.run()

    except Exception as e:
        print(f"\nâŒ Error: {e}")
        print("\nFor help, run: python taxonomy_matcher.py --help")
        exit(1)


if __name__ == "__main__":
    main()