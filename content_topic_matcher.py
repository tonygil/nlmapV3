"""
Content-Based Topic Matcher
Analyzes URL, Title, Description, Summary to find relevant taxonomy topics
that actually appear in the content.
"""

import pandas as pd
from collections import Counter
from rapidfuzz import fuzz
import re
import os
from typing import List, Dict, Tuple, Set

# Stopwords to filter out
STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
    'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must',
    'shall', 'can', 'need', 'dare', 'ought', 'used', 'it', 'its', 'this', 'that',
    'these', 'those', 'i', 'you', 'he', 'she', 'we', 'they', 'what', 'which', 'who',
    'whom', 'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both', 'few',
    'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
    'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now', 'here', 'there',
    'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'between', 'under', 'again', 'further', 'then', 'once', 'any', 'our', 'your',
    'their', 'his', 'her', 'my', 'out', 'up', 'down', 'off', 'over', 'www', 'com',
    'http', 'https', 'html', 'php', 'asp', 'aspx', 'page', 'pages', 'uk', 'en',
    'title', 'information', 'product', 'help', 'using', 'use', 'user', 'users',
    'guide', 'overview', 'section', 'click', 'select', 'enter', 'view', 'see',
    'following', 'provides', 'allows', 'enables', 'including', 'within', 'based',
    'cch', 'wolterskluwer', 'userdocs', 'release', 'notes', 'version'
}


class ContentTopicMatcher:
    """Match taxonomy topics based on content analysis."""

    def __init__(self, taxonomy_file: str, min_topic_length: int = 3):
        """
        Initialize with taxonomy file.

        Args:
            taxonomy_file: Path to taxonomy Excel file
            min_topic_length: Minimum topic word length to consider
        """
        self.taxonomy_file = taxonomy_file
        self.min_topic_length = min_topic_length
        self.topics = []
        self.topics_by_product = {}
        self.topic_to_info = {}  # topic -> {product, domain, segment}
        self._load_taxonomy()

    def _load_taxonomy(self):
        """Load topics from taxonomy file."""
        df = pd.read_excel(self.taxonomy_file)

        # Find topic columns (handle both "Topic 1" and "Topic_1" formats)
        topic_cols = [c for c in df.columns if c.startswith('Topic')]

        for _, row in df.iterrows():
            product = str(row.get('Product', '')).strip()
            domain = str(row.get('Domain', '')).strip()
            segment = str(row.get('Segment', '')).strip()

            for col in topic_cols:
                topic = row.get(col)
                if pd.notna(topic) and str(topic).strip():
                    topic_str = str(topic).strip()
                    if topic_str.lower() not in ['nan', '']:
                        self.topics.append(topic_str)

                        # Store by product
                        if product not in self.topics_by_product:
                            self.topics_by_product[product] = []
                        if topic_str not in self.topics_by_product[product]:
                            self.topics_by_product[product].append(topic_str)

                        # Store info
                        if topic_str not in self.topic_to_info:
                            self.topic_to_info[topic_str] = {
                                'product': product,
                                'domain': domain,
                                'segment': segment
                            }

        # Deduplicate
        self.topics = list(set(self.topics))
        print(f"Loaded {len(self.topics)} unique topics from taxonomy")
        print(f"Products: {list(self.topics_by_product.keys())}")

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text or pd.isna(text):
            return ''
        text = str(text).lower()
        # Replace separators with spaces
        for sep in ['-', '_', '/', '|', ':', ',', '.', '(', ')', '[', ']',
                    '&', ';', '?', '=', '"', "'", '\n', '\r', '\t']:
            text = text.replace(sep, ' ')
        # Remove extra spaces
        text = ' '.join(text.split())
        return text

    def _extract_content_words(self, text: str) -> Set[str]:
        """Extract meaningful words from text."""
        clean = self._clean_text(text)
        words = set()
        for word in clean.split():
            if len(word) >= self.min_topic_length and word not in STOPWORDS:
                words.add(word)
        return words

    def _extract_content_phrases(self, text: str, max_words: int = 4) -> List[str]:
        """Extract phrases from text."""
        clean = self._clean_text(text)
        words = [w for w in clean.split() if len(w) >= 2]

        phrases = []
        # Single words (filtered)
        for w in words:
            if len(w) >= self.min_topic_length and w not in STOPWORDS:
                phrases.append(w)

        # Multi-word phrases
        for n in range(2, max_words + 1):
            for i in range(len(words) - n + 1):
                phrase = ' '.join(words[i:i+n])
                # Only include if first and last words are not stopwords
                if words[i] not in STOPWORDS and words[i+n-1] not in STOPWORDS:
                    phrases.append(phrase)

        return phrases

    def _precompute_topic_data(self):
        """Pre-compute topic lookup data for faster matching."""
        self._topic_lower_map = {}  # topic_lower -> original topic
        self._single_word_topics = set()  # single word topics (lowercased)
        self._multi_word_topics = {}  # topic_lower -> list of significant words

        for topic in self.topics:
            topic_lower = topic.lower()
            self._topic_lower_map[topic_lower] = topic

            words = topic_lower.split()
            if len(words) == 1 and len(topic_lower) >= 4:
                self._single_word_topics.add(topic_lower)
            elif len(words) > 1:
                sig_words = tuple(w for w in words if len(w) >= 3 and w not in STOPWORDS)
                if sig_words:
                    self._multi_word_topics[topic_lower] = sig_words

    def find_topics_in_content(self, url: str, title: str, description: str,
                                summary: str, product: str = None,
                                prefer_product: bool = True) -> List[Dict]:
        """
        Find taxonomy topics based on keywords/phrases in Summary and Description.
        Extracts keywords, then fuzzy matches against taxonomy topics for relevance.
        """
        # Ensure precomputed data exists
        if not hasattr(self, '_topic_lower_map'):
            self._precompute_topic_data()

        # Clean content - focus on Summary and Description
        desc_clean = self._clean_text(description)
        summary_clean = self._clean_text(summary)
        title_clean = self._clean_text(title)

        # Primary content for keyword extraction (Summary + Description)
        primary_content = f"{summary_clean} {desc_clean}"
        # Secondary content (Title) for validation
        secondary_content = f"{title_clean}"
        all_content = f"{primary_content} {secondary_content}"

        # Extract keywords/phrases from Summary and Description
        keywords = self._extract_content_phrases(primary_content, max_words=3)
        title_keywords = self._extract_content_phrases(secondary_content, max_words=2)

        # Count keyword frequency
        keyword_counts = Counter(keywords)

        matches = []
        seen_topics = set()

        # For each taxonomy topic, check relevance to extracted keywords
        for topic in self.topics:
            if topic in seen_topics:
                continue

            topic_lower = topic.lower()
            topic_words = set(topic_lower.split())
            topic_info = self.topic_to_info.get(topic, {})

            best_score = 0
            match_type = None
            matched_keyword = None
            found_in = []

            # Check 1: Exact topic name in content
            if topic_lower in primary_content:
                best_score = 100
                match_type = 'exact'
                matched_keyword = topic_lower
                if topic_lower in summary_clean:
                    found_in.append('summary')
                if topic_lower in desc_clean:
                    found_in.append('description')

            # Check 2: Topic name in title
            elif topic_lower in title_clean:
                best_score = 98
                match_type = 'exact_title'
                matched_keyword = topic_lower
                found_in.append('title')

            # Check 3: Fuzzy match keywords against topic
            else:
                for kw, freq in keyword_counts.most_common(100):
                    if len(kw) < 3:
                        continue

                    # Fuzzy match
                    score = fuzz.ratio(kw, topic_lower)

                    # Boost score if keyword appears multiple times
                    if freq > 1 and score >= 75:
                        score = min(100, score + (freq * 2))

                    if score > best_score and score >= 80:
                        best_score = score
                        match_type = 'keyword_match'
                        matched_keyword = kw
                        # Determine where the keyword was found
                        if kw in summary_clean:
                            found_in = ['summary']
                        elif kw in desc_clean:
                            found_in = ['description']
                        else:
                            found_in = ['content']

            # Check 4: All topic words appear in content (for multi-word topics)
            if not match_type and len(topic_words) > 1:
                content_words = self._extract_content_words(primary_content)
                sig_words = [w for w in topic_words if len(w) >= 3 and w not in STOPWORDS]
                if sig_words and all(w in content_words for w in sig_words):
                    best_score = 90
                    match_type = 'all_words'
                    matched_keyword = ' '.join(sig_words)
                    found_in = ['keywords']

            if match_type and best_score >= 80:
                seen_topics.add(topic)
                matches.append({
                    'topic': topic,
                    'score': best_score,
                    'match_type': match_type,
                    'matched_keyword': matched_keyword,
                    'found_in': ', '.join(found_in) if found_in else match_type,
                    'topic_product': topic_info.get('product', ''),
                    'topic_domain': topic_info.get('domain', ''),
                    'topic_segment': topic_info.get('segment', ''),
                    'is_product_match': topic_info.get('product', '') == product
                })

        # Sort by: product match first, then score
        def sort_key(m):
            product_boost = 0 if m['is_product_match'] else 1
            type_order = {'exact': 0, 'exact_title': 1, 'keyword_match': 2, 'all_words': 3}
            return (product_boost, type_order.get(m['match_type'], 4), -m['score'])

        matches.sort(key=sort_key)
        return matches

    def find_segment_in_content(self, url: str, title: str, description: str,
                                  summary: str, product: str = None) -> List[Dict]:
        """Find segments that appear in content."""
        # Get segments from taxonomy for this product
        segments = set()
        segment_to_info = {}

        for topic, info in self.topic_to_info.items():
            seg = info.get('segment', '').strip()
            if seg and seg.lower() not in ['', 'nan']:
                if product and info.get('product', '') == product:
                    segments.add(seg)
                    segment_to_info[seg] = info
                elif not product:
                    segments.add(seg)
                    segment_to_info[seg] = info

        # Also add segments from all products as fallback
        for topic, info in self.topic_to_info.items():
            seg = info.get('segment', '').strip()
            if seg and seg.lower() not in ['', 'nan']:
                segments.add(seg)
                if seg not in segment_to_info:
                    segment_to_info[seg] = info

        # Clean content
        all_content = ' '.join([
            self._clean_text(url),
            self._clean_text(title),
            self._clean_text(description),
            self._clean_text(summary)
        ])
        content_words = self._extract_content_words(all_content)

        matches = []
        for segment in segments:
            seg_lower = segment.lower()
            seg_words = seg_lower.split()

            # Exact match
            if seg_lower in all_content:
                matches.append({
                    'segment': segment,
                    'score': 100,
                    'match_type': 'exact',
                    'domain': segment_to_info.get(segment, {}).get('domain', '')
                })
            # Word match for multi-word segments
            elif len(seg_words) > 1:
                sig_words = [w for w in seg_words if len(w) >= 3 and w not in STOPWORDS]
                if sig_words and all(w in content_words for w in sig_words):
                    matches.append({
                        'segment': segment,
                        'score': 95,
                        'match_type': 'word_match',
                        'domain': segment_to_info.get(segment, {}).get('domain', '')
                    })
            # Single word segment
            elif len(seg_lower) >= 4 and seg_lower in content_words:
                matches.append({
                    'segment': segment,
                    'score': 90,
                    'match_type': 'word_match',
                    'domain': segment_to_info.get(segment, {}).get('domain', '')
                })

        matches.sort(key=lambda x: -x['score'])
        return matches

    def process_file(self, input_file: str, output_file: str,
                     max_topics: int = 5, include_comparison: bool = True) -> pd.DataFrame:
        """
        Process input file and generate content-based topic matches.
        Creates one row per URL-Segment combination (both original and content-based).

        Args:
            input_file: Path to input Excel file (with URL, Title, Description, Summary, Product)
            output_file: Path to output Excel file
            max_topics: Maximum topics to assign per row
            include_comparison: Include comparison with original topics

        Returns:
            DataFrame with results
        """
        print(f"\nProcessing: {input_file}")
        df = pd.read_excel(input_file)
        print(f"Loaded {len(df)} rows")

        url_col = 'URL'
        if url_col not in df.columns:
            raise ValueError(f"Input file must have '{url_col}' column")

        # First, gather all original segments per URL
        url_data = {}  # url -> {title, desc, summary, product, original_segments: [{segment, domain, topics, score, relevance}]}

        print("  Gathering original data...")
        for idx, row in df.iterrows():
            url = row.get('URL', '')
            if not url:
                continue

            if url not in url_data:
                url_data[url] = {
                    'title': row.get('Title', ''),
                    'description': row.get('Description', ''),
                    'summary': row.get('Summary', ''),
                    'product': row.get('Product', ''),
                    'original_segments': []
                }

            # Collect original segment data
            segment = str(row.get('Segment', '')).strip() if pd.notna(row.get('Segment', '')) else ''
            domain = str(row.get('Domain', '')).strip() if pd.notna(row.get('Domain', '')) else ''
            topics = []
            for i in range(1, max_topics + 1):
                t = row.get(f'Topic_{i}', '')
                if pd.notna(t) and str(t).strip():
                    topics.append(str(t).strip())

            url_data[url]['original_segments'].append({
                'segment': segment,
                'domain': domain,
                'topics': topics,
                'score': row.get('Top_Score', ''),
                'relevance': row.get('Top_Relevance', '')
            })

        print(f"  Found {len(url_data)} unique URLs")

        # Process each URL and create expanded rows
        results = []
        total = len(url_data)

        for idx, (url, data) in enumerate(url_data.items()):
            if idx % 500 == 0:
                print(f"  Processing URL {idx}/{total}...")

            title = data['title']
            description = data['description']
            summary = data['summary']
            product = data['product']

            # Find content-based topics
            topic_matches = self.find_topics_in_content(
                url=url, title=title, description=description,
                summary=summary, product=product, prefer_product=True
            )

            # Find content-based segments
            segment_matches = self.find_segment_in_content(
                url=url, title=title, description=description,
                summary=summary, product=product
            )

            # Get sets for comparison
            original_segments_set = set(s['segment'].lower() for s in data['original_segments'] if s['segment'])
            content_segments_set = set(s['segment'].lower() for s in segment_matches if s['segment'])

            # Get content topics list for comparison
            content_topics_list = [tm['topic'] for tm in topic_matches]
            content_segments_list = [sm['segment'] for sm in segment_matches]

            # Create rows for ORIGINAL segments with content comparison
            for orig in data['original_segments']:
                row_data = {
                    'URL': url,
                    'Title': title,
                    'Product': product,
                    'Row_Type': 'Original',
                    'Domain': orig['domain'],
                    'Segment': orig['segment'],
                    'Segment_Source': 'Original',
                    'Segment_In_Content': 'Yes' if orig['segment'].lower() in content_segments_set else 'No',
                }
                # Add ORIGINAL topics
                for i in range(max_topics):
                    row_data[f'Original_Topic_{i+1}'] = orig['topics'][i] if i < len(orig['topics']) else ''

                # Add CONTENT topics for comparison
                for i in range(max_topics):
                    row_data[f'Content_Topic_{i+1}'] = content_topics_list[i] if i < len(content_topics_list) else ''

                # Add CONTENT segments for comparison
                for i in range(3):
                    row_data[f'Content_Segment_{i+1}'] = content_segments_list[i] if i < len(content_segments_list) else ''

                # Flag if topics match
                orig_topic1 = orig['topics'][0].lower() if orig['topics'] else ''
                content_topic1 = content_topics_list[0].lower() if content_topics_list else ''
                row_data['Topics_Match'] = 'Yes' if orig_topic1 and content_topic1 and orig_topic1 == content_topic1 else 'No'

                row_data['Original_Score'] = orig['score']
                row_data['Original_Relevance'] = orig['relevance']
                row_data['Description'] = description
                row_data['Summary'] = summary

                results.append(row_data)

            # Create rows for CONTENT-BASED segments (that are different from original)
            for seg_match in segment_matches:
                seg_name = seg_match['segment']
                # Skip if this segment was already in original
                if seg_name.lower() in original_segments_set:
                    continue

                # Find topics that belong to this segment
                segment_topics = []
                for tm in topic_matches:
                    if tm.get('topic_segment', '').lower() == seg_name.lower():
                        segment_topics.append(tm['topic'])
                # If no segment-specific topics, use top content topics
                if not segment_topics:
                    segment_topics = [tm['topic'] for tm in topic_matches[:max_topics]]

                row_data = {
                    'URL': url,
                    'Title': title,
                    'Product': product,
                    'Row_Type': 'Content-Based',
                    'Domain': seg_match.get('domain', ''),
                    'Segment': seg_name,
                    'Segment_Source': 'Content',
                    'Segment_In_Content': 'Yes',
                }
                # Original topics are empty for content-based rows
                for i in range(max_topics):
                    row_data[f'Original_Topic_{i+1}'] = ''

                # Add CONTENT topics
                for i in range(max_topics):
                    row_data[f'Content_Topic_{i+1}'] = segment_topics[i] if i < len(segment_topics) else ''

                # Add CONTENT segments
                for i in range(3):
                    row_data[f'Content_Segment_{i+1}'] = content_segments_list[i] if i < len(content_segments_list) else ''

                row_data['Topics_Match'] = 'N/A'  # No original to compare
                row_data['Original_Score'] = ''
                row_data['Original_Relevance'] = ''
                row_data['Description'] = description
                row_data['Summary'] = summary

                results.append(row_data)

        # Create DataFrame
        result_df = pd.DataFrame(results)

        # Sort by URL, then Row_Type (Original first), then Segment
        result_df = result_df.sort_values(['URL', 'Row_Type', 'Segment'])

        # Add Rank column - rank within each URL
        result_df['Rank'] = result_df.groupby('URL').cumcount() + 1

        # Define column order (Rank now exists)
        # Group: Identification | Segment info | Original Topics | Content Topics | Content Segments | Comparison | Details
        col_order = ['URL', 'Title', 'Product', 'Row_Type', 'Rank', 'Domain', 'Segment',
                     'Segment_Source', 'Segment_In_Content']
        # Original topics grouped together
        col_order += [f'Original_Topic_{i}' for i in range(1, max_topics + 1)]
        # Content topics grouped together for comparison
        col_order += [f'Content_Topic_{i}' for i in range(1, max_topics + 1)]
        # Content segments
        col_order += [f'Content_Segment_{i}' for i in range(1, 4)]
        # Comparison and details
        col_order += ['Topics_Match', 'Original_Score', 'Original_Relevance', 'Description', 'Summary']

        col_order = [c for c in col_order if c in result_df.columns]
        result_df = result_df[col_order]

        # Save to Excel
        print(f"\nSaving to: {output_file}")
        result_df.to_excel(output_file, index=False)

        # Print summary
        original_rows = len([r for r in results if r['Row_Type'] == 'Original'])
        content_rows = len([r for r in results if r['Row_Type'] == 'Content-Based'])
        segments_validated = len([r for r in results if r['Row_Type'] == 'Original' and r['Segment_In_Content'] == 'Yes'])

        print(f"\n=== SUMMARY ===")
        print(f"Total rows in output: {len(results)}")
        print(f"  - Original segment rows: {original_rows}")
        print(f"  - NEW content-based segment rows: {content_rows}")
        print(f"Original segments validated by content: {segments_validated} ({round(segments_validated/original_rows*100, 1)}%)")

        return result_df


def main():
    """Run content-based topic matching."""
    # Configuration - UPDATE THESE PATHS
    INPUT_FILE = r"C:\Users\Tony.Gilpin\Downloads\4thFeb\taxonomy_match_remappedV3_GB.xlsx"
    TAXONOMY_FILE = r"C:\Users\Tony.Gilpin\Downloads\4thFeb\Latest Taxonomy 03-02-26.xlsx"
    OUTPUT_FILE = r"C:\Users\Tony.Gilpin\Downloads\4thFeb\content_matched_topics.xlsx"

    # Run matching
    matcher = ContentTopicMatcher(TAXONOMY_FILE)
    result_df = matcher.process_file(
        input_file=INPUT_FILE,
        output_file=OUTPUT_FILE,
        max_topics=5,
        include_comparison=True
    )

    print(f"\nContent-based topic matching complete!")
    print(f"  Output: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
