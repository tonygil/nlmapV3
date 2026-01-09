"""
NL Taxonomy Mapper V3
Matches URLs from semantic carriers to taxonomy topics using fuzzy string matching.
NOW WITH MULTI-COUNTRY SUPPORT!
"""

import pandas as pd
from fuzzywuzzy import fuzz
from typing import List, Dict, Tuple, Optional
import os
import argparse
from country_config import CountryConfig


class TaxonomyMatcher:
    """Main class for matching URL keywords to taxonomy topics."""
    
    def __init__(self,
                 country_code: Optional[str] = None,
                 semantic_file: Optional[str] = None,
                 taxonomy_file: Optional[str] = None,
                 output_file: Optional[str] = None,
                 similarity_threshold: Optional[int] = None,
                 consolidate_topics: Optional[bool] = None,
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
        
        for idx, row in self.taxonomy_df.iterrows():
            product = row.get('Product', '')
            domain = row.get('Domain', '')
            segment = row.get('Segment', '')
            
            # Extract all topics from this row
            for topic_col in topic_columns:
                topic = row.get(topic_col, '')
                if pd.notna(topic) and topic.strip():
                    self.taxonomy_lookup.append({
                        'product': product if pd.notna(product) else '',
                        'domain': domain if pd.notna(domain) else '',
                        'segment': segment if pd.notna(segment) else '',
                        'topic': topic.strip()
                    })
        
        print(f"  Created {len(self.taxonomy_lookup)} searchable topic entries")
        print(f"  Note: Segments will be auto-added as topics when any topic from their row matches")
        
    def expand_with_synonyms(self, keyword: str) -> List[str]:
        """
        Expand a keyword with its synonyms.
        
        Args:
            keyword: Original keyword
            
        Returns:
            List of keyword variations including synonyms
        """
        variations = [keyword.lower().strip()]
        
        # Check if keyword matches any synonym key
        for key, synonyms in self.synonyms.items():
            if key in keyword.lower():
                variations.extend(synonyms)
        
        return list(set(variations))
    
    def find_topic_matches(self, keyword: str) -> List[Dict]:
        """
        Find matching topics for a given keyword.
        
        Args:
            keyword: Keyword to match
            
        Returns:
            List of matching taxonomy entries with similarity scores
        """
        matches = []
        keyword_variations = self.expand_with_synonyms(keyword)
        
        for tax_entry in self.taxonomy_lookup:
            topic = tax_entry['topic'].lower()
            max_score = 0
            
            # Check similarity against all keyword variations
            for variation in keyword_variations:
                score = fuzz.partial_ratio(variation, topic)
                max_score = max(max_score, score)
            
            if max_score >= self.similarity_threshold:
                matches.append({
                    **tax_entry,
                    'similarity_score': max_score
                })
        
        # Sort by similarity score (highest first)
        matches.sort(key=lambda x: x['similarity_score'], reverse=True)
        return matches
    
    def extract_keywords(self, row) -> List[str]:
        """
        Extract all keywords from a semantic carriers row.
        
        Args:
            row: DataFrame row
            
        Returns:
            List of keywords
        """
        keywords = []
        for i in range(1, 11):  # Keyword 1 through Keyword 10
            col_name = f'Keyword {i}'
            if col_name in row.index and pd.notna(row[col_name]):
                keywords.append(str(row[col_name]).strip())
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
        
        for idx, row in self.semantic_df.iterrows():
            url = row.get('URL', '')
            keywords = self.extract_keywords(row)
            
            url_has_match = False
            matched_segments = set()  # Track which (Product, Domain, Segment) combos matched
            
            # Process each keyword
            for keyword in keywords:
                matches = self.find_topic_matches(keyword)
                
                for match in matches:
                    # Create unique combination key for deduplication
                    combo_key = (url, match['product'], match['domain'], 
                                match['segment'], match['topic'])
                    
                    # Only add if not seen before (deduplication)
                    if combo_key not in seen_combinations:
                        seen_combinations.add(combo_key)
                        results.append({
                            'URL': url,
                            'Product': match['product'],
                            'Domain': match['domain'],
                            'Segment': match['segment'],
                            'Topic': match['topic']
                        })
                        url_has_match = True
                        
                        # Track this segment combination for auto-addition
                        if match['segment']:
                            segment_key = (url, match['product'], match['domain'], match['segment'])
                            matched_segments.add(segment_key)
            
            # AUTO-ADD: For each matched segment, add a row where Segment = Topic
            for segment_combo in matched_segments:
                url, product, domain, segment = segment_combo
                combo_key = (url, product, domain, segment, segment)
                
                # Only add if this exact combination doesn't already exist
                if combo_key not in seen_combinations:
                    seen_combinations.add(combo_key)
                    results.append({
                        'URL': url,
                        'Product': product,
                        'Domain': domain,
                        'Segment': segment,
                        'Topic': segment  # Segment becomes the Topic
                    })
            
            if url_has_match:
                urls_with_matches += 1
            else:
                # Add unmapped URL to results with empty taxonomy fields
                unmapped_urls.append(url)
                results.append({
                    'URL': url,
                    'Product': '',
                    'Domain': 'UNMAPPED',
                    'Segment': '',
                    'Topic': ''
                })
            
            # Progress indicator
            if (idx + 1) % 50 == 0:
                print(f"  Processed {idx + 1}/{total_urls} URLs...")
        
        print(f"\nMatching complete!")
        print(f"  URLs with matches: {urls_with_matches}/{total_urls} ({urls_with_matches/total_urls*100:.1f}%)")
        print(f"  Unmapped URLs: {len(unmapped_urls)}/{total_urls} ({len(unmapped_urls)/total_urls*100:.1f}%)")
        print(f"  Total output rows: {len(results)}")
        print(f"  Average matches per URL: {len(results)/total_urls:.2f}")
        
        results_df = pd.DataFrame(results)

        # Apply consolidation if enabled
        if self.consolidate_topics:
            print("\n  Applying topic consolidation...")
            results_df = self.consolidate_results(results_df)

        return results_df

    def consolidate_results(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """
        Consolidate multiple topic matches into single row per URL-Segment group.

        Args:
            results_df: DataFrame in one-row-per-topic format

        Returns:
            DataFrame with topics as columns (Topic_1, Topic_2, ...)
        """
        # Handle unmapped URLs separately
        unmapped = results_df[results_df['Domain'] == 'UNMAPPED'].copy()
        mapped = results_df[results_df['Domain'] != 'UNMAPPED'].copy()

        if len(mapped) == 0:
            return unmapped

        # Group by (URL, Product, Domain, Segment)
        grouped = mapped.groupby(['URL', 'Product', 'Domain', 'Segment'],
                                dropna=False, sort=False)

        consolidated_rows = []
        max_topics = 0

        for (url, product, domain, segment), group in grouped:
            topics = group['Topic'].tolist()  # Preserves discovery order

            # Filter out auto-added segment topics (segment name should not appear as topic)
            topics = [t for t in topics if t != segment]

            # Skip rows with no actual topics (only had segment-as-topic)
            if not topics:
                continue

            max_topics = max(max_topics, len(topics))

            row = {
                'URL': url,
                'Product': product,
                'Domain': domain,
                'Segment': segment
            }

            # Add topics as Topic_1, Topic_2, etc.
            for i, topic in enumerate(topics, start=1):
                row[f'Topic_{i}'] = topic

            consolidated_rows.append(row)

        consolidated_df = pd.DataFrame(consolidated_rows)

        # Ensure all topic columns exist (fill missing with empty string)
        for i in range(1, max_topics + 1):
            col_name = f'Topic_{i}'
            if col_name not in consolidated_df.columns:
                consolidated_df[col_name] = ''

        # Fill NaN with empty strings for cleaner Excel output
        consolidated_df = consolidated_df.fillna('')

        # Re-add unmapped URLs with empty topic columns
        if len(unmapped) > 0:
            for i in range(1, max_topics + 1):
                unmapped[f'Topic_{i}'] = ''
            unmapped = unmapped.drop('Topic', axis=1)
            consolidated_df = pd.concat([consolidated_df, unmapped], ignore_index=True)

        print(f"  Consolidated to {len(consolidated_df)} rows with up to {max_topics} topics per row")

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
            print(f"\nâš ï¸  Note: {unmapped_count} unmapped URLs included in output")
            print(f"  Filter by Domain='UNMAPPED' to review these URLs")
    
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
            consolidate_topics=args.consolidate_topics
        )

        matcher.run()

    except Exception as e:
        print(f"\nâŒ Error: {e}")
        print("\nFor help, run: python taxonomy_matcher.py --help")
        exit(1)


if __name__ == "__main__":
    main()