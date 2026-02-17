"""
Content Keyword Extractor
Extracts keywords/phrases from URL path, Title, Summary, and Description columns
to generate a clean keywords file for use with Remap URLs feature.

Key principle: Start with a CLEAN keyword list. Any existing Keyword columns
in the input file are completely ignored. The output contains ONLY freshly
extracted keywords from actual content (URL, Title, Summary, Description).

Optional: Crawl URLs to extract keywords from actual page content (much better
than relying on truncated Summary/Description columns).
"""

import pandas as pd
import re
from rapidfuzz import fuzz
from typing import List, Dict, Set, Optional, Tuple
from urllib.parse import urlparse, unquote
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Optional imports for URL crawling
# Prefer trafilatura for content extraction (much better boilerplate removal)
# Fall back to requests+BeautifulSoup if trafilatura not installed
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

CRAWLING_AVAILABLE = TRAFILATURA_AVAILABLE or REQUESTS_AVAILABLE

# Stopwords to filter out - expanded to remove generic/noise words
STOPWORDS = {
    # Common English stopwords
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
    'their', 'his', 'her', 'my', 'out', 'up', 'down', 'off', 'over', 'if', 'while',
    # Web/tech stopwords
    'www', 'com', 'http', 'https', 'html', 'php', 'asp', 'aspx', 'page', 'pages',
    'uk', 'en', 'org', 'net', 'co', 'gov',
    # Generic documentation words
    'title', 'information', 'product', 'help', 'using', 'use', 'user', 'users',
    'guide', 'overview', 'section', 'click', 'select', 'enter', 'view', 'see',
    'following', 'provides', 'allows', 'enables', 'enabling', 'including', 'within',
    'based', 'feature', 'features', 'option', 'options', 'setting', 'settings',
    'found', 'available', 'access', 'accessing', 'allow', 'allowing',
    # Action/process words that are too generic
    'manage', 'managing', 'create', 'creating', 'update', 'updating', 'delete',
    'deleting', 'add', 'adding', 'remove', 'removing', 'edit', 'editing',
    'process', 'processing', 'ensure', 'ensuring', 'provide', 'providing',
    'enable', 'display', 'displaying', 'show', 'showing', 'configure', 'configuring',
    # Generic nouns
    'data', 'file', 'files', 'system', 'systems', 'screen', 'screens', 'window',
    'windows', 'dialog', 'button', 'field', 'fields', 'form', 'forms', 'list',
    'item', 'items', 'record', 'records', 'entry', 'entries', 'value', 'values',
    'type', 'types', 'name', 'names', 'number', 'numbers', 'date', 'dates',
    'time', 'period', 'periods', 'year', 'years', 'month', 'months', 'day', 'days',
    # Generic adjectives/adverbs
    'new', 'old', 'full', 'empty', 'default', 'current', 'previous', 'next',
    'specific', 'particular', 'relevant', 'appropriate', 'necessary', 'required',
    'effectively', 'automatically', 'manually', 'directly', 'correctly', 'properly',
    'efficiently', 'streamlined', 'comprehensive', 'detailed', 'complete',
    'important', 'key', 'main', 'major', 'minor', 'basic', 'advanced',
    # Documentation verbs (describe what the page does, not what it's about)
    'highlights', 'describes', 'explains', 'covers', 'outlines', 'discusses',
    'demonstrates', 'illustrates', 'walks', 'guides', 'presents', 'introduces',
    'addresses', 'references', 'contains', 'offers', 'involves', 'focuses',
    'details', 'summarizes', 'summarises', 'explores', 'reviews', 'examines',
    'finalize', 'finalise', 'finalizing', 'finalising',
    # CCH/Wolters Kluwer specific
    'cch', 'wolterskluwer', 'userdocs', 'release', 'notes', 'version',
    # Numbers and misc
    'like', 'get', 'set', 'make', 'way', 'first', 'last', 'one', 'two', 'three',
    'four', 'five', 'etc', 'via', 'per', 'pre', 'post', 'non', 'sub', 'tab',
    'step', 'steps',
    # HTML entity fragments that leak from spreadsheet content
    'nbsp', 'amp', 'quot', 'apos', 'lt', 'gt',
    # More generic terms from user's output
    'client', 'clients', 'report', 'reports', 'reporting', 'convert', 'conversion',
    'found', 'maintenance', 'visit', 'starting', 'live', 'integrity', 'accuracy',
    'guidance', 'webpage', 'facilitates', 'creation', 'matching', 'codes', 'code'
}

# Noise phrase patterns - phrases starting with these are filtered out
NOISE_PHRASE_STARTS = {
    'enabling', 'allowing', 'providing', 'ensuring', 'facilitating',
    'managing', 'creating', 'updating', 'configuring', 'displaying',
    'showing', 'accessing', 'visiting', 'starting', 'guidance on',
    'effectively', 'automatically', 'properly', 'correctly'
}

# Pre-compiled regex for separator splitting
_SEPARATOR_PATTERN = re.compile(r'[-_/|:,.()\[\]&;?="\'\n\r\t]+')

# Regex to strip leading numeric prefixes from URL segments (e.g., "15Journals" -> "Journals", "010_Overview" -> "Overview")
_LEADING_DIGITS_PATTERN = re.compile(r'^\d+')

# Regex for CamelCase splitting (e.g., "ChartOfAccounts" -> "Chart Of Accounts")
# Splits on: lowercase->uppercase, letter->digit, digit->letter boundaries
_CAMELCASE_PATTERN = re.compile(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=\d)(?=[A-Za-z])|(?<=[A-Za-z])(?=\d)')


class ContentKeywordExtractor:
    """
    Extracts keywords from URL, Title, Summary, and Description content.
    Optionally ranks keywords by taxonomy match score.
    Optionally crawls URLs to extract keywords from actual page content.
    """

    def __init__(self, taxonomy_file: Optional[str] = None,
                 synonyms: Optional[Dict] = None,
                 threshold: int = 80,
                 min_word_length: int = 3,
                 crawl_urls: bool = False,
                 max_workers: int = 10,
                 request_timeout: int = 15,
                 progress_callback=None):
        """
        Initialize the keyword extractor.

        Args:
            taxonomy_file: Optional taxonomy file for ranking keywords by match score
            synonyms: Optional synonyms dict for expansion
            threshold: Minimum fuzzy match score for taxonomy matches
            min_word_length: Minimum word length to include
            crawl_urls: If True, fetch actual page content from URLs
            max_workers: Number of concurrent threads for URL fetching
            request_timeout: Timeout in seconds for each URL request
            progress_callback: Optional callback(current, total, message) for progress
        """
        self.taxonomy_file = taxonomy_file
        self.synonyms = synonyms or {}
        self.threshold = threshold
        self.min_word_length = min_word_length
        self.crawl_urls = crawl_urls
        self.max_workers = max_workers
        self.request_timeout = request_timeout
        self.progress_callback = progress_callback

        # Crawling stats
        self.crawl_stats = {'success': 0, 'failed': 0, 'skipped': 0}

        # Taxonomy data
        self.topics = []  # List of unique topic strings
        self.topics_lower = []  # Pre-computed lowercase topics
        self.topic_info = {}  # topic -> {product, domain, segment}

        if taxonomy_file:
            self._load_taxonomy()

    def fetch_url_content(self, url: str) -> Optional[str]:
        """
        Fetch URL and extract main content text using trafilatura.
        Trafilatura uses a multi-algorithm approach (own heuristic + readability + jusText)
        for superior boilerplate removal compared to manual BeautifulSoup exclusions.

        Falls back to basic requests if trafilatura is not available.

        Args:
            url: URL to fetch

        Returns:
            Extracted text content, or None if fetch failed
        """
        if not CRAWLING_AVAILABLE:
            return None

        try:
            if TRAFILATURA_AVAILABLE:
                # Use trafilatura: fetch + extract in one step
                downloaded = trafilatura.fetch_url(url)
                if downloaded:
                    text = trafilatura.extract(
                        downloaded,
                        favor_precision=True,
                        include_tables=True,
                        include_comments=False,
                        deduplicate=True,
                    )
                    if text:
                        return text[:50000]

                return None

            elif REQUESTS_AVAILABLE:
                # Fallback: basic requests fetch with minimal text extraction
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(url, headers=headers, timeout=self.request_timeout)
                response.raise_for_status()

                # Strip HTML tags with a simple regex fallback
                text = re.sub(r'<[^>]+>', ' ', response.text)
                text = re.sub(r'\s+', ' ', text).strip()
                return text[:50000] if text else None

        except Exception:
            # Silently fail - will fall back to Summary/Description
            return None

    def fetch_urls_concurrent(self, urls: List[str]) -> Dict[str, str]:
        """
        Fetch multiple URLs concurrently.

        Args:
            urls: List of URLs to fetch

        Returns:
            Dict mapping URL -> extracted content (or empty string if failed)
        """
        if not CRAWLING_AVAILABLE:
            print("  Warning: trafilatura (or requests) not installed. Crawling disabled.")
            print("  Install with: pip install trafilatura")
            return {url: '' for url in urls}

        results = {}
        total = len(urls)

        print(f"  Crawling {total} URLs with {self.max_workers} concurrent workers...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_url = {executor.submit(self.fetch_url_content, url): url for url in urls}

            # Process completed tasks
            completed = 0
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                completed += 1

                try:
                    content = future.result()
                    if content:
                        results[url] = content
                        self.crawl_stats['success'] += 1
                    else:
                        results[url] = ''
                        self.crawl_stats['failed'] += 1
                except Exception:
                    results[url] = ''
                    self.crawl_stats['failed'] += 1

                # Progress update every 10 URLs or at the end
                if completed % 10 == 0 or completed == total:
                    print(f"    Crawled {completed}/{total} URLs...")
                    if self.progress_callback:
                        self.progress_callback(completed, total, f"Crawling URL {completed}/{total}")

        print(f"  Crawl complete: {self.crawl_stats['success']} success, {self.crawl_stats['failed']} failed")
        return results

    def _load_taxonomy(self):
        """Load topics from taxonomy file for ranking."""
        if not self.taxonomy_file or not os.path.exists(self.taxonomy_file):
            return

        try:
            df = pd.read_excel(self.taxonomy_file)

            # Find topic columns
            topic_cols = [c for c in df.columns if c.startswith('Topic')]

            seen_topics = set()
            for _, row in df.iterrows():
                product = str(row.get('Product', '')).strip()
                domain = str(row.get('Domain', '')).strip()
                segment = str(row.get('Segment', '')).strip()

                for col in topic_cols:
                    topic = row.get(col)
                    if pd.notna(topic) and str(topic).strip():
                        topic_str = str(topic).strip()
                        if topic_str.lower() not in ['nan', ''] and topic_str not in seen_topics:
                            seen_topics.add(topic_str)
                            self.topics.append(topic_str)
                            self.topics_lower.append(topic_str.lower())
                            self.topic_info[topic_str] = {
                                'product': product,
                                'domain': domain,
                                'segment': segment
                            }

            print(f"Loaded {len(self.topics)} unique topics from taxonomy")
        except Exception as e:
            print(f"Warning: Could not load taxonomy: {e}")

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text or pd.isna(text):
            return ''
        text = str(text)
        # Decode common HTML entities that leak from spreadsheet columns
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<')
        text = text.replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
        # Also handle bare entity fragments (e.g., "nbsp" as standalone word)
        text = re.sub(r'\bnbsp\b', ' ', text, flags=re.IGNORECASE)
        text = text.lower()
        # Replace separators with spaces
        text = _SEPARATOR_PATTERN.sub(' ', text)
        # Remove extra spaces
        text = ' '.join(text.split())
        return text

    def extract_from_url(self, url: str) -> List[str]:
        """
        Extract keywords from URL path.

        Args:
            url: The URL to extract keywords from

        Returns:
            List of extracted terms (preserving multi-word terms where sensible)
        """
        if not url or pd.isna(url):
            return []

        try:
            # Decode URL encoding (handle double-encoding like %252B -> %2B -> +)
            url = unquote(unquote(url))
            parsed = urlparse(url)
            path = parsed.path
        except Exception:
            path = str(url)

        # Split path by / to get segments
        segments = [s for s in path.split('/') if s]

        keywords = []
        seen = set()

        for segment in segments:
            # Step 1: Replace underscores, hyphens, and plus signs with spaces
            segment_cleaned = segment.replace('_', ' ').replace('-', ' ').replace('+', ' ')

            # Step 2: Strip leading numeric prefixes from each word
            # Handles "15Journals" -> "Journals", "010 Chart" -> "Chart"
            words_after_num_strip = []
            for w in segment_cleaned.split():
                stripped = _LEADING_DIGITS_PATTERN.sub('', w)
                if stripped:
                    words_after_num_strip.append(stripped)

            # Step 3: Apply CamelCase splitting to each word
            # Handles "ChartOfAccounts" -> "Chart Of Accounts"
            words = []
            for w in words_after_num_strip:
                camel_parts = _CAMELCASE_PATTERN.split(w)
                if len(camel_parts) > 1:
                    # CamelCase detected - add split parts
                    for part in camel_parts:
                        if part:
                            words.append(part)
                else:
                    words.append(w)

            # Check if any split part is too short - if so, try joining
            # Only do this for segments that had NO separators (pure CamelCase like "ReSearch")
            # Segments with separators (e.g., "Chart_of_Accounts") already have proper word boundaries
            has_separators = '_' in segment or '-' in segment or '+' in segment
            has_short_part = any(len(w) < self.min_word_length for w in words)

            if has_short_part and not has_separators:
                # Add the joined version (no separators, no leading digits)
                joined_raw = segment.replace('_', '').replace('-', '').replace('+', '')
                joined = _LEADING_DIGITS_PATTERN.sub('', joined_raw).lower().strip()
                if (len(joined) >= self.min_word_length and
                    joined not in STOPWORDS and
                    not joined.isdigit() and
                    joined not in seen):
                    # Also try CamelCase splitting on the joined version
                    camel_parts = _CAMELCASE_PATTERN.split(joined_raw)
                    camel_parts = [_LEADING_DIGITS_PATTERN.sub('', p) for p in camel_parts if p]
                    if len(camel_parts) > 1:
                        # Use the CamelCase-split version instead of the blob
                        camel_words = [p.lower() for p in camel_parts
                                       if len(p) >= self.min_word_length
                                       and p.lower() not in STOPWORDS
                                       and not p.isdigit()]
                        if 2 <= len(camel_words) <= 5:
                            phrase = ' '.join(camel_words)
                            if phrase not in seen:
                                seen.add(phrase)
                                keywords.append(phrase)
                        # Also add individual CamelCase words
                        for cw in camel_words:
                            if cw not in seen:
                                seen.add(cw)
                                keywords.append(cw)
                    else:
                        seen.add(joined)
                        keywords.append(joined)

            # Filter meaningful words
            meaningful_words = []
            for word in words:
                word_clean = word.lower().strip()
                if (len(word_clean) >= self.min_word_length and
                    word_clean not in STOPWORDS and
                    not word_clean.isdigit()):
                    meaningful_words.append(word_clean)

            # Add the full multi-word term if it has 2-4 meaningful words
            if 2 <= len(meaningful_words) <= 4:
                phrase = ' '.join(meaningful_words)
                if phrase not in seen:
                    seen.add(phrase)
                    keywords.append(phrase)

            # Also add individual words (but they'll be filtered by substring check later)
            for word in meaningful_words:
                if word not in seen:
                    seen.add(word)
                    keywords.append(word)

        return keywords

    def _is_noise_phrase(self, phrase: str) -> bool:
        """Check if a phrase is a noise phrase that should be filtered out."""
        phrase_lower = phrase.lower()
        words = phrase_lower.split()

        # Check if phrase starts with a noise word
        for noise_start in NOISE_PHRASE_STARTS:
            if phrase_lower.startswith(noise_start):
                return True

        # Check if any word in the phrase is a noise start word (e.g., "enabling" in middle)
        for word in words:
            if word in NOISE_PHRASE_STARTS:
                return True

        # Check if phrase contains too many stopwords
        non_stop_count = sum(1 for w in words if w not in STOPWORDS)
        stop_count = len(words) - non_stop_count

        # If more than half are stopwords, it's noise
        if stop_count > non_stop_count:
            return True

        # Phrases with only 1 meaningful word are noise
        if non_stop_count <= 1:
            return True

        return False

    def extract_from_text(self, text: str, max_phrase_words: int = 4) -> List[str]:
        """
        Extract words and phrases from text content.

        Splits text into clauses (on punctuation) BEFORE extracting n-grams,
        so phrases never cross sentence/clause boundaries.

        Args:
            text: The text to extract keywords from
            max_phrase_words: Maximum words in extracted phrases

        Returns:
            List of extracted terms
        """
        if not text or pd.isna(text):
            return []

        # Split into clauses BEFORE cleaning away punctuation
        # This prevents n-grams from crossing clause boundaries
        # e.g., "...highlights integration with CCH..." won't merge across ","
        text_str = str(text).lower()
        clauses = re.split(r'[.,;:!?\n\r\t]+', text_str)

        keywords = []
        seen = set()

        for clause in clauses:
            # Clean each clause individually (removes remaining separators like - _ / etc.)
            clean = re.sub(r'[-_/|&()\[\]"\']+', ' ', clause)
            # Decode HTML entities
            clean = clean.replace('&nbsp;', ' ').replace('&amp;', '&')
            clean = re.sub(r'\bnbsp\b', ' ', clean, flags=re.IGNORECASE)
            clean = ' '.join(clean.split())

            words = clean.split()

            # Extract multi-word phrases (2-3 words only) within this clause
            for n in range(2, min(max_phrase_words + 1, 4)):  # Cap at 3 words
                for i in range(len(words) - n + 1):
                    phrase_words = words[i:i+n]

                    # ALL words must be non-stopwords and have 3+ chars
                    if not all(w not in STOPWORDS and len(w) >= 3 for w in phrase_words):
                        continue

                    phrase = ' '.join(phrase_words)

                    # Filter out noise phrases
                    if phrase not in seen and not self._is_noise_phrase(phrase):
                        seen.add(phrase)
                        keywords.append(phrase)

        return keywords

    def _score_keyword(self, keyword: str) -> Tuple[int, int, str]:
        """
        Score a keyword based on taxonomy match.

        Returns:
            Tuple of (priority_tier, score, matched_topic)
            - priority_tier: 1=exact match, 2=fuzzy match, 3=synonym match, 4=phrase, 5=word
            - score: fuzzy match score (0-100)
            - matched_topic: the taxonomy topic it matched (or empty string)
        """
        keyword_lower = keyword.lower()

        if not self.topics:
            # No taxonomy - score by length (longer = more specific = better)
            word_count = len(keyword.split())
            if word_count >= 2:
                return (4, 50 + word_count * 5, '')  # Phrases get priority 4
            else:
                return (5, 50, '')  # Single words get priority 5

        best_score = 0
        best_topic = ''

        # Check for exact match first
        for i, topic_lower in enumerate(self.topics_lower):
            if keyword_lower == topic_lower:
                return (1, 100, self.topics[i])  # Exact match

        # Check for fuzzy matches
        for i, topic_lower in enumerate(self.topics_lower):
            score = fuzz.ratio(keyword_lower, topic_lower)
            if score > best_score:
                best_score = score
                best_topic = self.topics[i]

        if best_score >= self.threshold:
            return (2, best_score, best_topic)  # Fuzzy match

        # Check synonym matches
        for topic_name, synonyms_list in self.synonyms.items():
            if topic_name.startswith('_'):
                continue
            topic_lower = topic_name.lower()
            for syn in synonyms_list:
                syn_lower = syn.lower()
                if keyword_lower == syn_lower:
                    # Keyword is a synonym - give it good priority
                    return (3, 85, topic_name)

        # No taxonomy match - score based on type
        word_count = len(keyword.split())
        if word_count >= 2:
            return (4, 50 + word_count * 5, '')  # Multi-word phrases
        else:
            return (5, 50, '')  # Single words

    def _filter_substring_keywords(self, keywords: List[str]) -> List[str]:
        """
        Remove keywords that are substrings of other keywords.
        E.g., if we have both "research" and "search", keep only "research".
        """
        if not keywords:
            return []

        keywords_lower = [kw.lower() for kw in keywords]
        to_remove = set()

        for i, kw1 in enumerate(keywords_lower):
            for j, kw2 in enumerate(keywords_lower):
                if i != j and len(kw1) < len(kw2):
                    # Check if kw1 is a substring of kw2 (not just contained, but a suffix/prefix)
                    # "search" in "research" -> remove "search"
                    # "tax" in "tax compliance" -> don't remove (it's a phrase)
                    if ' ' not in kw1 and ' ' not in kw2:
                        # Both are single words - check if one contains the other
                        if kw1 in kw2:
                            to_remove.add(i)

        return [kw for i, kw in enumerate(keywords) if i not in to_remove]

    def rank_keywords(self, keyword_source_pairs: List, max_keywords: int = 12) -> List:
        """
        Rank keyword-source pairs by taxonomy match score and return top N.

        Args:
            keyword_source_pairs: List of (keyword, source) tuples
            max_keywords: Maximum keywords to return

        Returns:
            Top N (keyword, source) tuples ranked by score
        """
        if not keyword_source_pairs:
            return []

        # Source priority for deduplication (lower = higher priority)
        SOURCE_PRIORITY = {'title': 0, 'summary': 1, 'description': 2, 'url': 3}

        # Deduplicate by keyword, keeping highest-priority source
        seen = {}  # keyword_lower -> (keyword, source)
        for kw, src in keyword_source_pairs:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen[kw_lower] = (kw, src)
            else:
                existing_src = seen[kw_lower][1]
                if SOURCE_PRIORITY.get(src, 99) < SOURCE_PRIORITY.get(existing_src, 99):
                    seen[kw_lower] = (kw, src)

        unique_pairs = list(seen.values())

        # Filter substring keywords (operate on strings only)
        keywords_only = [kw for kw, _ in unique_pairs]
        keywords_filtered = self._filter_substring_keywords(keywords_only)
        filtered_set = set(kw.lower() for kw in keywords_filtered)
        unique_pairs = [(kw, src) for kw, src in unique_pairs if kw.lower() in filtered_set]

        # Score each keyword
        scored = []
        for kw, src in unique_pairs:
            tier, score, matched_topic = self._score_keyword(kw)
            scored.append((tier, -score, kw, src, matched_topic))  # Negative score for descending

        # Sort by tier (ascending), then by score (descending via negative)
        scored.sort(key=lambda x: (x[0], x[1]))

        # Return top (keyword, source) pairs
        return [(item[2], item[3]) for item in scored[:max_keywords]]

    def process_row(self, url: str, title: str, summary: str,
                    description: str) -> Dict[str, str]:
        """
        Extract and rank keywords from a single row.

        Args:
            url: URL column value
            title: Title column value
            summary: Summary column value
            description: Description column value

        Returns:
            Dict with Keyword 1 through Keyword 12 and Source 1 through Source 12
        """
        all_keywords = []  # List of (keyword, source) tuples

        # Extract from each source (in priority order)
        url_keywords = self.extract_from_url(url)
        all_keywords.extend([(kw, 'url') for kw in url_keywords])

        # Title keywords
        title_keywords = self.extract_from_text(title, max_phrase_words=3)
        all_keywords.extend([(kw, 'title') for kw in title_keywords])

        # Summary keywords
        summary_keywords = self.extract_from_text(summary, max_phrase_words=4)
        all_keywords.extend([(kw, 'summary') for kw in summary_keywords])

        # Description keywords
        desc_keywords = self.extract_from_text(description, max_phrase_words=4)
        all_keywords.extend([(kw, 'description') for kw in desc_keywords])

        # Rank and get top 12 (keyword, source) pairs
        ranked = self.rank_keywords(all_keywords, max_keywords=12)

        # Build result dict with both Keyword and Source columns
        result = {}
        for i in range(1, 13):
            if i <= len(ranked):
                kw, src = ranked[i-1]
                result[f'Keyword {i}'] = kw
                result[f'Source {i}'] = src
            else:
                result[f'Keyword {i}'] = ''
                result[f'Source {i}'] = ''

        return result

    def process_file(self, input_file: str, output_file: str) -> pd.DataFrame:
        """
        Process input file and generate keywords file.

        Args:
            input_file: Path to input Excel file
            output_file: Path to output Excel file

        Returns:
            DataFrame with extracted keywords
        """
        print(f"\nLoading input file: {input_file}")
        df = pd.read_excel(input_file)
        original_count = len(df)
        print(f"  Loaded {original_count:,} rows")

        # Check required column
        if 'URL' not in df.columns:
            raise ValueError("Input file must have 'URL' column")

        # Deduplicate by URL ONLY if Product column doesn't exist
        # If Product column exists, we may have intentional multi-product rows
        if 'Product' in df.columns and df['Product'].notna().any():
            print(f"  Product column detected - preserving multi-product rows (no URL deduplication)")
            df_deduped = df
            duplicates_removed = 0
        else:
            # Deduplicate by URL (keep first occurrence)
            # This handles cases where input has multiple rows per URL (e.g., from consolidated output)
            df_deduped = df.drop_duplicates(subset=['URL'], keep='first')
            duplicates_removed = original_count - len(df_deduped)
            if duplicates_removed > 0:
                print(f"  Removed {duplicates_removed:,} duplicate URLs (keeping first occurrence)")

        print(f"  Processing {len(df_deduped):,} rows")

        # Crawl URLs if enabled
        crawled_content = {}
        if self.crawl_urls:
            print(f"\n[CRAWLING ENABLED] Fetching content from URLs...")
            urls = df_deduped['URL'].tolist()
            crawled_content = self.fetch_urls_concurrent(urls)

        # Process each row
        results = []
        total = len(df_deduped)
        processed = 0

        for idx, row in df_deduped.iterrows():
            url = row.get('URL', '')
            title = row.get('Title', '') if pd.notna(row.get('Title', '')) else ''
            summary = row.get('Summary', '') if pd.notna(row.get('Summary', '')) else ''
            description = row.get('Description', '') if pd.notna(row.get('Description', '')) else ''

            # If crawling enabled, use crawled content (or fall back to Summary/Description)
            if self.crawl_urls and url in crawled_content and crawled_content[url]:
                page_content = crawled_content[url]
                # Only use crawled content if it has enough text (> 100 chars)
                # Otherwise fall back to Summary/Description
                if len(page_content) > 100:
                    # Use crawled page content instead of Summary/Description
                    keywords = self.process_row(url, title, page_content, '')
                else:
                    # Crawled content too short (likely JS-loaded page), use columns
                    keywords = self.process_row(url, title, summary, description)
                    self.crawl_stats['skipped'] += 1
            else:
                # Extract keywords from columns (original behavior)
                keywords = self.process_row(url, title, summary, description)

            # Build output row
            output_row = {
                'URL': url,
                'Title': title,
                'Summary': summary,
                'Description': description,
            }

            # Preserve Product column if it exists (before keywords to ensure proper order)
            if 'Product' in df.columns:
                product_val = row.get('Product') if pd.notna(row.get('Product')) else ''
                output_row['Product'] = product_val

            # Add extracted keywords
            output_row.update(keywords)

            results.append(output_row)
            processed += 1

            # Progress indicator (only if not crawling - crawling has its own progress)
            if not self.crawl_urls and (processed % 100 == 0 or processed == total):
                print(f"  Processed {processed:,}/{total:,} rows...")
                if self.progress_callback:
                    self.progress_callback(processed, total, f"Processing row {processed:,}/{total:,}")

        # Create DataFrame with proper column order
        result_df = pd.DataFrame(results)

        # Define column order
        col_order = ['URL', 'Title', 'Summary', 'Description']
        if 'Product' in result_df.columns:
            col_order.append('Product')
        col_order.extend([f'Keyword {i}' for i in range(1, 13)])
        col_order.extend([f'Source {i}' for i in range(1, 13)])

        # Reorder columns
        col_order = [c for c in col_order if c in result_df.columns]
        result_df = result_df[col_order]

        # Save to Excel
        print(f"\nSaving to: {output_file}")
        result_df.to_excel(output_file, index=False)

        # Print summary
        keywords_extracted = sum(1 for _, row in result_df.iterrows()
                                  if row.get('Keyword 1', ''))
        print(f"\n=== SUMMARY ===")
        print(f"Input rows: {original_count:,}")
        if duplicates_removed > 0:
            print(f"Duplicates removed: {duplicates_removed:,}")
        print(f"Unique URLs processed: {total:,}")
        if self.crawl_urls:
            print(f"URLs crawled successfully: {self.crawl_stats['success']:,}")
            if self.crawl_stats['skipped'] > 0:
                print(f"URLs with thin content (used columns): {self.crawl_stats['skipped']:,}")
            print(f"URLs failed to crawl: {self.crawl_stats['failed']:,}")
        print(f"Rows with keywords extracted: {keywords_extracted:,}")
        print(f"Output file: {output_file}")

        return result_df


def main():
    """Run content keyword extraction (CLI mode)."""
    # Configuration - UPDATE THESE PATHS
    INPUT_FILE = r"path\to\input.xlsx"
    TAXONOMY_FILE = r"path\to\taxonomy.xlsx"  # Optional - set to None to skip ranking
    OUTPUT_FILE = r"path\to\output_keywords.xlsx"

    # Run extraction
    extractor = ContentKeywordExtractor(
        taxonomy_file=TAXONOMY_FILE,
        threshold=80
    )

    result_df = extractor.process_file(
        input_file=INPUT_FILE,
        output_file=OUTPUT_FILE
    )

    print(f"\nContent keyword extraction complete!")
    print(f"  Output: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
