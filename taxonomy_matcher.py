"""
NL Taxonomy Mapper V2
Matches URLs from semantic carriers to NL Taxonomy topics using fuzzy string matching.
Now includes Segment matching!
"""

import pandas as pd
from fuzzywuzzy import fuzz
from typing import List, Dict, Tuple
import os


class TaxonomyMatcher:
    """Main class for matching URL keywords to taxonomy topics."""
    
    def __init__(self, 
                 semantic_file: str = 'semantic_carriers_list.xlsx',
                 taxonomy_file: str = 'NL Taxonomy V2.xlsx',
                 output_file: str = 'taxonomy_match.xlsx',
                 similarity_threshold: int = 80):
        """
        Initialize the TaxonomyMatcher.
        
        Args:
            semantic_file: Path to semantic carriers Excel file
            taxonomy_file: Path to taxonomy Excel file
            output_file: Path for output Excel file
            similarity_threshold: Minimum similarity score (0-100) for matches
        """
        self.semantic_file = semantic_file
        self.taxonomy_file = taxonomy_file
        self.output_file = output_file
        self.similarity_threshold = similarity_threshold
        
        # Synonym dictionary for Dutch terms
        self.synonyms = {
            'bankzaken': ['bank', 'banken', 'bankafschriften', 'bankrekeningen', 'bankenmodule'],
            'betalen': ['betaling', 'betalingen'],
            'incasseren': ['incasso'],
            'facturatie': ['facturen', 'factuur', 'facturering'],
            'jaarafsluiting': ['jaarrekening', 'jaarafsluiten'],
            'btw': ['belasting', 'belastingaangifte'],
            'relatiebeheer': ['klanten', 'leveranciers', 'debiteuren', 'crediteuren'],
            'grootboek': ['grootboekrekeningen'],
            'vaste activa': ['activa', 'activum'],
        }
        
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
        
        print(f"\n✅ Matching complete!")
        print(f"  URLs with matches: {urls_with_matches}/{total_urls} ({urls_with_matches/total_urls*100:.1f}%)")
        print(f"  Unmapped URLs: {len(unmapped_urls)}/{total_urls} ({len(unmapped_urls)/total_urls*100:.1f}%)")
        print(f"  Total output rows: {len(results)}")
        print(f"  Average matches per URL: {len(results)/total_urls:.2f}")
        
        return pd.DataFrame(results)
    
    def save_output(self, results_df: pd.DataFrame):
        """
        Save results to Excel file.
        
        Args:
            results_df: DataFrame with matched results
        """
        print(f"\nSaving results to {self.output_file}...")
        results_df.to_excel(self.output_file, index=False)
        print(f"âœ… Output saved successfully!")
        print(f"  File: {os.path.abspath(self.output_file)}")
        
        # Show unmapped count in output
        unmapped_count = len(results_df[results_df['Domain'] == 'UNMAPPED'])
        if unmapped_count > 0:
            print(f"\nâš ï¸  Note: {unmapped_count} unmapped URLs included in output")
            print(f"  Filter by Domain='UNMAPPED' to review these URLs")
    
    def run(self):
        """Execute the complete matching workflow."""
        print("=" * 60)
        print("NL Taxonomy Mapper V2")
        print("=" * 60)
        
        self.load_data()
        self.build_taxonomy_lookup()
        results_df = self.process_matching()
        self.save_output(results_df)
        
        print("\n" + "=" * 60)
        print("Process completed successfully!")
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
    """Main entry point."""
    print("\n" + "=" * 60)
    print("           NL TAXONOMY MAPPER V2 - SETUP")
    print("=" * 60)
    
    # Get threshold from user
    threshold = get_threshold_from_user()
    
    # Initialize and run the matcher
    matcher = TaxonomyMatcher(
        semantic_file='semantic_carriers_list.xlsx',
        taxonomy_file='NL Taxonomy V2.xlsx',
        output_file='taxonomy_match.xlsx',
        similarity_threshold=threshold
    )
    
    matcher.run()


if __name__ == "__main__":
    main()