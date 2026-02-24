"""
Strict Content Matcher
Generates topics purely from page content (Title, Summary, Description, URL path).
NO taxonomy file dependency — topics are what the page actually discusses.

If a user sees a topic, they should be able to find the related page directly.

Product is extracted from the URL path or semantic file — no taxonomy lookup.
Domain is classified from a fixed set based on content keywords.
Segment is extracted from URL path structure.

This is an ALTERNATIVE output alongside the main taxonomy_matcher.py, not a replacement.
"""

import pandas as pd
import re
import os
import json
from typing import List, Optional, Tuple, Dict
from country_config import CountryConfig
from generate_topic_recommendations import sanitize_dataframe
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

# Optional imports for URL crawling
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

try:
    import requests as requests_lib
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

CRAWLING_AVAILABLE = TRAFILATURA_AVAILABLE or REQUESTS_AVAILABLE


# Pre-compiled regex patterns
_CLAUSE_SPLIT = re.compile(r'[.,;:!?\n\r\t]+')
_CAMELCASE_PATTERN = re.compile(
    r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=\d)(?=[A-Za-z])|(?<=[A-Za-z])(?=\d)'
)
_LEADING_DIGITS = re.compile(r'^\d+')

# Brand names with internal CamelCase that must NOT be split by _CAMELCASE_PATTERN
# Maps lowercase -> correct form. These are replaced before CamelCase splitting.
_PROTECTED_BRANDS = {
    'ixbrl': 'iXBRL',
    'ifirm': 'iFirm',
}
_PROTECTED_BRANDS_RE = re.compile(
    '|'.join(re.escape(k) for k in _PROTECTED_BRANDS), re.IGNORECASE
)

# Title prefixes to strip (action words that describe the page, not the topic)
_TITLE_PREFIX = re.compile(
    r'^(creating\s+(?:a\s+)?|how\s+to\s+|working\s+with\s+|guide\s+to\s+|'
    r'overview\s+of\s+|introduction\s+to\s+|understanding\s+|'
    r'about\s+|setting\s+up\s+|using\s+|adding\s+(?:a\s+)?|'
    r'editing\s+(?:a\s+)?|configuring\s+|managing\s+|'
    r'deleting\s+(?:a\s+)?|removing\s+(?:a\s+)?|viewing\s+)',
    re.IGNORECASE
)

# URL path segments that are site navigation, NOT topics
_URL_NAV_SEGMENTS = {
    'product information', 'product help', 'product updates', 'product news',
    'product support', 'product documentation', 'product overview',
    'help centre', 'help center', 'knowledge base', 'knowledge centre',
    'support centre', 'support center', 'user guide', 'user guides',
    'release notes', 'release information', 'whats new', "what's new",
    'getting started', 'quick start', 'home', 'index', 'default',
    'main', 'help', 'docs', 'support', 'wiki', 'en', 'uk', 'content',
    'documentation', 'resources', 'articles', 'topics',
}

# Fixed domain set — classified by keyword matching
# Domain and segment keyword lists are loaded per-country from JSON files:
#   countries/{CODE}/domains.json  — maps domain names to keyword lists
#   countries/{CODE}/segments.json — maps segment names to keyword lists
# The _load_country_keywords() function handles loading with fallback to empty dicts.

def _load_country_keywords(config_root: str, country_code: str):
    """
    Load domain and segment keyword dicts from country-specific JSON files.

    Looks for:
        {config_root}/countries/{country_code}/domains.json
        {config_root}/countries/{country_code}/segments.json

    Returns:
        (domain_keywords: dict, segment_keywords: dict)
    """
    country_dir = os.path.join(config_root, 'countries', country_code)

    domain_keywords = {}
    domains_file = os.path.join(country_dir, 'domains.json')
    if os.path.exists(domains_file):
        try:
            with open(domains_file, 'r', encoding='utf-8') as f:
                domain_keywords = json.load(f)
            print(f"  Loaded {len(domain_keywords)} domains from {domains_file}")
        except Exception as e:
            print(f"  Warning: Failed to load {domains_file}: {e}")

    segment_keywords = {}
    segments_file = os.path.join(country_dir, 'segments.json')
    if os.path.exists(segments_file):
        try:
            with open(segments_file, 'r', encoding='utf-8') as f:
                segment_keywords = json.load(f)
            print(f"  Loaded {len(segment_keywords)} segments from {segments_file}")
        except Exception as e:
            print(f"  Warning: Failed to load {segments_file}: {e}")

    return domain_keywords, segment_keywords

# Stopwords for topic extraction — aggressive filtering of non-topic words
_TOPIC_STOPWORDS = {
    # English function words
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
    'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must',
    'shall', 'can', 'need', 'it', 'its', 'this', 'that', 'these', 'those',
    'i', 'you', 'he', 'she', 'we', 'they', 'what', 'which', 'who', 'whom',
    'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both', 'few',
    'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
    'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now', 'here', 'there',
    'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'between', 'under', 'again', 'further', 'then', 'once', 'any', 'our', 'your',
    'their', 'his', 'her', 'my', 'out', 'up', 'down', 'off', 'over', 'if', 'while',
    # Documentation verbs — describe what the PAGE does, not the TOPIC
    'provides', 'allows', 'enables', 'enabling', 'allowing', 'including', 'within',
    'highlights', 'describes', 'explains', 'covers', 'outlines', 'discusses',
    'demonstrates', 'illustrates', 'presents', 'introduces', 'addresses',
    'references', 'contains', 'offers', 'involves', 'focuses', 'details',
    'summarizes', 'summarises', 'explores', 'reviews', 'examines',
    'creating', 'create', 'manage', 'managing', 'select', 'selecting',
    'update', 'updating', 'delete', 'deleting', 'add', 'adding',
    'remove', 'removing', 'edit', 'editing', 'configure', 'configuring',
    'ensure', 'ensuring', 'provide', 'providing', 'display', 'displaying',
    'show', 'showing', 'access', 'accessing', 'view', 'viewing',
    'finalize', 'finalise', 'finalizing', 'finalising',
    'using', 'used', 'use', 'based', 'following', 'found',
    # Action verbs that create garbage when paired with nouns
    'report', 'reporting', 'submit', 'submitting', 'submission',
    'automated', 'automate', 'streamline', 'streamlining',
    'facilitate', 'facilitates', 'facilitated',
    'matching', 'matched', 'match', 'process', 'processing',
    'program', 'programmes', 'programs', 'system', 'systems',
    'purposes', 'purpose', 'compliance', 'management',
    # Documentation nouns — too generic to be topics
    'webpage', 'page', 'pages', 'section', 'guide', 'step', 'steps',
    'overview', 'information', 'feature', 'features', 'option', 'options',
    'setting', 'settings', 'user', 'users', 'click', 'enter',
    'button', 'field', 'fields', 'form', 'forms', 'screen', 'screens',
    'dialog', 'list', 'item', 'items', 'value', 'values',
    # Adverbs/adjectives
    'efficiently', 'effectively', 'automatically', 'manually', 'directly',
    'correctly', 'properly', 'streamlined', 'comprehensive', 'detailed',
    'specific', 'particular', 'relevant', 'appropriate', 'necessary',
    'new', 'old', 'full', 'available', 'current', 'previous',
    # Web/tech & file formats
    'www', 'com', 'http', 'https', 'html', 'php', 'uk', 'en', 'co',
    'pdf', 'csv', 'xml', 'json', 'xlsx', 'doc', 'txt',
    # UI actions & page chrome (common in crawled content)
    'make', 'makes', 'making', 'made',
    'download', 'downloads', 'downloading', 'downloaded',
    'upload', 'uploads', 'uploading', 'uploaded',
    'print', 'printed', 'printing',
    'open', 'opening', 'opened', 'close', 'closing', 'closed',
    'save', 'saved', 'saving',
    'copy', 'copies', 'copied', 'copying',
    'correct', 'correcting', 'corrected',
    'either', 'neither', 'whether', 'however', 'therefore',
    'next', 'back', 'cancel', 'apply', 'confirm', 'continue',
    'yes', 'please', 'note', 'important', 'warning',
    'required', 'optional', 'default', 'selected', 'existing',
    'right', 'left', 'top', 'bottom', 'above', 'below',
    # CCH-specific generic
    'cch', 'wolterskluwer', 'userdocs',
    # Misc
    'etc', 'via', 'per', 'nbsp', 'amp',
    # UI elements & visual descriptions
    'mouse', 'cursor', 'arrow', 'scroll', 'hover', 'drag', 'checkbox',
    'dropdown', 'sidebar', 'toolbar', 'ribbon', 'breadcrumb', 'tooltip',
    'icon', 'icons', 'asterisk', 'dot', 'dots', 'triangle',
    # Colours
    'red', 'blue', 'green', 'yellow', 'orange', 'grey', 'gray',
    'white', 'black', 'purple', 'bold', 'italic', 'highlighted',
    # Vague quantifiers
    'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
    'nine', 'ten', 'single', 'another', 'several', 'various', 'multiple',
    'many', 'few', 'first', 'second', 'third', 'last', 'certain',
    # Generic action verbs (3rd-person / present)
    'shows', 'appears', 'displays', 'looks', 'wants', 'want',
    'needs', 'lets', 'gives', 'takes', 'runs', 'sets', 'gets',
    'requires', 'includes', 'contains', 'helps',
    # Page structure / chrome
    'content', 'menu', 'tab', 'tabs', 'bar', 'column', 'columns',
    'row', 'rows', 'panel', 'window', 'pane', 'header', 'footer',
    'updated', 'main',
    # Additional documentation noise
    'like', 'small', 'large', 'example', 'examples',
    'way', 'ways', 'type', 'types', 'record', 'records',
    'manual', 'manuals', 'chapter', 'chapters',
}

# Multi-word phrases that pass individual stopword checks but are still noise
_NOISE_PHRASES = {
    'last updated', 'main content', 'main menu', 'task bar',
    'ribbon bar', 'main toolbar', 'menu bar', 'sub menu',
    'data entry task bar', 'check box', 'check boxes', 'tick box',
    'tick boxes', 'scroll bar', 'double clicking', 'right clicking',
    'dropdown selector', 'navigation buttons', 'blue margin',
    'blue arrow', 'red triangle', 'blue menu', 'light blue',
    'grey area', 'grey menu', 'white space', 'hand cursor',
    'icon appears', 'window appears', 'dialog appears',
    'main tab', 'search criteria', 'hard drive',
    'temporary directory', 'pre requisites',
}


class StrictContentMatcher:
    """Generates topics purely from page content. No taxonomy dependency."""

    def __init__(self,
                 country_code: Optional[str] = None,
                 semantic_file: Optional[str] = None,
                 output_file: Optional[str] = None,
                 top_n: int = 6,
                 config_file: str = 'config.yaml',
                 debug: bool = False,
                 max_rows: int = 0,
                 url_filter: str = '',
                 sources: Optional[List[str]] = None,
                 max_workers: int = 20,
                 request_timeout: int = 15):
        self.country_config = CountryConfig(config_file)

        if country_code is None:
            country_code = self.country_config.get_default_country()
        self.country_code = country_code.upper()

        available = [c['code'] for c in self.country_config.get_available_countries()]
        if self.country_code not in available:
            raise ValueError(f"Country '{self.country_code}' not available. Available: {', '.join(available)}")

        if semantic_file is None:
            country_files = self.country_config.get_country_files(self.country_code)
            semantic_file = country_files['semantic_carriers']

        self.semantic_file = semantic_file

        if output_file is None:
            output_file = f'strict_match_{self.country_code}.xlsx'
        elif not output_file.replace('.xlsx', '').endswith(f'_{self.country_code}'):
            base, ext = os.path.splitext(output_file)
            output_file = f'{base}_{self.country_code}{ext}'
        self.output_file = output_file

        self.top_n = top_n
        self.debug = debug
        self.max_rows = max_rows
        self.url_filter = url_filter.strip() if url_filter else ''
        self.sources = sources if sources is not None else ['title', 'url', 'content']
        self.max_workers = max_workers
        self.request_timeout = request_timeout

        self.semantic_df = None
        self.crawl_stats = {'success': 0, 'failed': 0}
        self._crawled_content = {}  # URL -> crawled text

        # Load country-specific domain and segment keywords from JSON files
        config_root = os.path.dirname(os.path.abspath(config_file))
        self._domain_keywords, self._segment_keywords = _load_country_keywords(
            config_root, self.country_code
        )
        self._valid_segments = list(self._segment_keywords.keys())

    def load_data(self):
        """Load semantic file with optional filtering."""
        print(f"Loading {self.semantic_file}...")
        self.semantic_df = pd.read_excel(self.semantic_file)
        print(f"  Loaded {len(self.semantic_df)} URLs")

        if self.url_filter:
            before = len(self.semantic_df)
            mask = self.semantic_df['URL'].astype(str).str.contains(
                self.url_filter, case=False, regex=False
            )
            self.semantic_df = self.semantic_df[mask].copy()
            print(f"  URL filter '{self.url_filter}': {before} -> {len(self.semantic_df)} rows")
            if len(self.semantic_df) == 0:
                raise ValueError(f"URL filter '{self.url_filter}' matched 0 rows")

        if self.max_rows > 0 and len(self.semantic_df) > self.max_rows:
            before = len(self.semantic_df)
            self.semantic_df = self.semantic_df.head(self.max_rows).copy()
            print(f"  Max rows limit: {before} -> {len(self.semantic_df)} rows")

    # ==================== URL CRAWLING ====================

    def fetch_url_content(self, url: str) -> Optional[str]:
        """Fetch URL and extract main content text using trafilatura.
        Falls back to basic requests if trafilatura is not available."""
        if not CRAWLING_AVAILABLE:
            return None

        try:
            if TRAFILATURA_AVAILABLE:
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
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests_lib.get(url, headers=headers, timeout=self.request_timeout)
                response.raise_for_status()
                text = re.sub(r'<[^>]+>', ' ', response.text)
                text = re.sub(r'\s+', ' ', text).strip()
                return text[:50000] if text else None

        except Exception:
            return None

    def fetch_urls_concurrent(self, urls: List[str]) -> Dict[str, str]:
        """Fetch multiple URLs concurrently using ThreadPoolExecutor."""
        if not CRAWLING_AVAILABLE:
            print("  Warning: trafilatura (or requests) not installed. Crawling disabled.")
            print("  Install with: pip install trafilatura")
            return {url: '' for url in urls}

        results = {}
        total = len(urls)
        print(f"  Crawling {total} URLs with {self.max_workers} concurrent workers...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {executor.submit(self.fetch_url_content, url): url for url in urls}
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

                if completed % 10 == 0 or completed == total:
                    print(f"    Crawled {completed}/{total} URLs...")

        print(f"  Crawl complete: {self.crawl_stats['success']} success, {self.crawl_stats['failed']} failed")
        return results

    # ==================== PRODUCT EXTRACTION FROM URL ====================

    def _extract_product_from_url(self, url: str) -> str:
        """
        Extract product name from URL path heuristically.
        Uses underscore-cleaned segments (no CamelCase split) to preserve names like "iFirm".
        Skips navigation segments like "Product_Information", "Product_Help".
        """
        try:
            path = urlparse(unquote(unquote(url))).path
        except Exception:
            return ''

        segments = [s for s in path.split('/') if s.strip()]
        if not segments:
            return ''

        candidates = []
        for seg in segments[:5]:  # Check up to 5 segments (nav segments may come first)
            cleaned = seg.replace('_', ' ').replace('-', ' ').replace('+', ' ')
            cleaned = _LEADING_DIGITS.sub('', cleaned).strip()
            cleaned = ' '.join(cleaned.split())

            # Skip navigation segments
            if cleaned.lower() in _URL_NAV_SEGMENTS:
                continue

            words = cleaned.split()
            # Product segments: 2+ words, no action prefixes
            if len(words) >= 2 and not _TITLE_PREFIX.match(cleaned):
                candidates.append(cleaned)

        if not candidates:
            return ''

        # If multiple candidates share a prefix, pick the shortest one
        if len(candidates) >= 2:
            candidates.sort(key=len)
            for i, short in enumerate(candidates[:-1]):
                for longer in candidates[i+1:]:
                    if longer.lower().startswith(short.lower()):
                        return short
        return candidates[0]

    # ==================== DOMAIN CLASSIFICATION ====================

    def _classify_domain(self, product: str, title: str, summary: str,
                         description: str) -> str:
        """
        Classify content into a domain based on keyword matching.
        Uses country-specific domain keywords loaded from countries/{CODE}/domains.json.
        Checks product name + title + summary + description.
        Falls back to 'General' if no keywords match or no domains configured.
        """
        if not self._domain_keywords:
            return 'General'

        # Build search text from all content
        search_text = ' '.join(filter(None, [
            product.lower() if product else '',
            title.lower() if title and not pd.isna(title) else '',
            str(summary).lower() if summary and not pd.isna(summary) else '',
            str(description).lower() if description and not pd.isna(description) else ''
        ]))

        if not search_text.strip():
            return 'General'

        # Score each domain by counting keyword matches
        domain_scores = {}
        for domain, keywords in self._domain_keywords.items():
            score = 0
            for kw in keywords:
                if kw in search_text:
                    # Longer keywords get higher weight
                    score += len(kw.split())
            domain_scores[domain] = score

        # Return the highest scoring domain, or "General" if no matches
        best_domain = max(domain_scores, key=domain_scores.get)
        if domain_scores[best_domain] > 0:
            return best_domain
        return 'General'

    # ==================== SEGMENT CLASSIFICATION ====================

    def _classify_segments(self, product: str, title: str, summary: str,
                           description: str, url: str, max_segments: int = 3) -> List[str]:
        """
        Classify content into segments using country-specific keyword lists.
        Uses segment keywords loaded from countries/{CODE}/segments.json.
        Returns top N segments ranked by keyword match score.
        """
        if not self._segment_keywords:
            return ['']

        # Build search text
        try:
            path = urlparse(unquote(unquote(url))).path
            # Clean URL path for matching
            path_clean = path.replace('_', ' ').replace('-', ' ').replace('+', ' ')
            path_clean = _LEADING_DIGITS.sub('', path_clean)
        except Exception:
            path_clean = ''

        search_text = ' '.join(filter(None, [
            path_clean.lower(),
            title.lower() if title and not pd.isna(title) else '',
            str(summary).lower() if summary and not pd.isna(summary) else '',
            str(description).lower() if description and not pd.isna(description) else ''
        ]))

        if not search_text.strip():
            return ['']

        # Score each segment by keyword matches
        segment_scores = {}
        for segment, keywords in self._segment_keywords.items():
            score = 0
            for kw in keywords:
                if kw in search_text:
                    # Longer keywords get higher weight
                    score += len(kw.split()) * 2
            if score > 0:
                segment_scores[segment] = score

        if not segment_scores:
            return ['']

        # Return top N segments sorted by score
        sorted_segs = sorted(segment_scores.items(), key=lambda x: x[1], reverse=True)
        return [seg for seg, score in sorted_segs[:max_segments]]

    # ==================== CONTENT TOPIC EXTRACTION ====================

    def _clean_title_to_topic(self, title: str, product: str = '') -> Optional[str]:
        """Extract the main topic from a page title by stripping action prefixes and product name."""
        if not title or pd.isna(title):
            return None
        t = str(title).strip()
        # Strip common title prefixes
        t = _TITLE_PREFIX.sub('', t).strip()
        # Strip trailing noise like "- Help" or "| Guide"
        t = re.split(r'\s*[-|]\s*', t)[0].strip()
        # Remove product name if it appears at start of title
        if product:
            t_lower = t.lower()
            prod_lower = product.lower()
            if t_lower.startswith(prod_lower):
                remainder = t[len(product):].strip(' -:')
                if len(remainder) >= 3:
                    t = remainder
            # Also try without "CCH" prefix variations
            for prefix in ['cch ', 'cch_']:
                if prod_lower.startswith(prefix):
                    short_prod = prod_lower[len(prefix):]
                    if t_lower.startswith(short_prod):
                        remainder = t[len(short_prod):].strip(' -:')
                        if len(remainder) >= 3:
                            t = remainder
                        break
        return t if len(t) >= 3 else None

    def _extract_url_topics(self, url: str, product: str = '') -> List[str]:
        """Extract topic-like phrases from URL path segments.

        Skips navigation segments (Product Information, Product Help, etc.).
        Skips product segments. CamelCase split only on non-product segments.
        """
        try:
            path = urlparse(unquote(unquote(url))).path
        except Exception:
            return []

        segments = [s for s in path.split('/') if s.strip()]
        prod_lower = product.lower() if product else ''

        topics = []
        for seg in segments:
            # Step 1: Clean underscores ONLY (preserves CamelCase like "iFirm")
            raw_cleaned = seg.replace('_', ' ').replace('-', ' ').replace('+', ' ')
            raw_cleaned = _LEADING_DIGITS.sub('', raw_cleaned).strip()
            raw_cleaned = ' '.join(raw_cleaned.split())

            if not raw_cleaned or len(raw_cleaned) < 3:
                continue

            raw_lower = raw_cleaned.lower()

            # Step 2: Skip navigation segments
            if raw_lower in _URL_NAV_SEGMENTS:
                continue

            # Step 3: Product filtering on the raw-cleaned version
            if prod_lower and (raw_lower == prod_lower or prod_lower.startswith(raw_lower)):
                continue

            # If segment starts with product name, extract the suffix as topic
            if prod_lower and raw_lower.startswith(prod_lower):
                suffix = raw_cleaned[len(product):].strip()
                if len(suffix) >= 3:
                    suffix = _TITLE_PREFIX.sub('', suffix).strip()
                    if len(suffix) >= 3:
                        topics.append(self._title_case(suffix))
                continue

            # Step 4: Protect brand names, then apply CamelCase split
            # Placeholders must be all-lowercase, no digits (to avoid CamelCase splits)
            placeholders = {}
            def _brand_replace(m):
                key = f'xbrand{"abcdefgh"[len(placeholders)]}x'
                placeholders[key] = _PROTECTED_BRANDS[m.group().lower()]
                return key
            topic_text = _PROTECTED_BRANDS_RE.sub(_brand_replace, raw_cleaned)
            topic_text = _CAMELCASE_PATTERN.sub(' ', topic_text)
            for key, brand in placeholders.items():
                topic_text = topic_text.replace(key, brand)
            topic_text = ' '.join(topic_text.split())

            # Strip title prefixes
            topic_text = _TITLE_PREFIX.sub('', topic_text).strip()
            # Strip leading "About the", "About", "The" etc.
            topic_text = re.sub(r'^(?:about\s+the\s+|about\s+|the\s+)', '', topic_text, flags=re.IGNORECASE).strip()
            if len(topic_text) >= 3:
                topics.append(self._title_case(topic_text))

        return topics

    def _extract_topic_phrases(self, text: str) -> List[str]:
        """Extract meaningful noun phrases from text, clause-aware, stopword-filtered."""
        if not text or pd.isna(text):
            return []

        text_lower = str(text).lower()
        clauses = _CLAUSE_SPLIT.split(text_lower)

        phrases = []
        seen = set()

        for clause in clauses:
            clean = re.sub(r'[-_/|&()\[\]"\']+', ' ', clause)
            clean = clean.replace('&nbsp;', ' ').replace('&amp;', ' ')
            clean = ' '.join(clean.split())
            words = clean.split()

            # Extract 2-3 word phrases where all words are meaningful
            for n in range(2, 4):
                for i in range(len(words) - n + 1):
                    phrase_words = words[i:i+n]

                    # All words must pass stopword filter and be 3+ chars
                    if not all(w not in _TOPIC_STOPWORDS and len(w) >= 3 and not w.isdigit()
                               for w in phrase_words):
                        continue

                    phrase = ' '.join(phrase_words)

                    # Skip multi-word noise phrases
                    if phrase in _NOISE_PHRASES:
                        continue

                    # Skip phrases starting with special characters
                    if phrase[0] in '#\'+=*{.':
                        continue

                    if phrase not in seen:
                        seen.add(phrase)
                        phrases.append(phrase)

        return phrases

    def _title_case(self, text: str) -> str:
        """Convert to title case, handling small words and known acronyms."""
        small_words = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
                       'for', 'of', 'with', 'by', 'from', 'as', 'is', 'via'}
        # Known uppercase acronyms/brand names
        uppercase_words = {
            'cch': 'CCH', 'vat': 'VAT', 'mtd': 'MTD', 'cgt': 'CGT', 'hmrc': 'HMRC',
            'paye': 'PAYE', 'sa100': 'SA100', 'sa800': 'SA800', 'ct600': 'CT600',
            'ixbrl': 'iXBRL', 'ifirm': 'iFirm', 'ifrs': 'IFRS', 'frs': 'FRS',
            'p11d': 'P11D', 'api': 'API', 'uk': 'UK', 'crm': 'CRM',
            'sql': 'SQL', 'aml': 'AML', 'kyc': 'KYC', 'kyb': 'KYB',
            'gdpr': 'GDPR', 'bde': 'BDE', 'llp': 'LLP', 'gaap': 'GAAP',
            'xbrl': 'XBRL', 'wip': 'WIP', 'nic': 'NIC', 'nics': 'NICs',
            'isin': 'ISIN', 'isa': 'ISA', 'roi': 'ROI', 'mfa': 'MFA',
            'dpo': 'DPO', 'sug': 'SUG', 'eis': 'EIS', 'vct': 'VCT',
            'dta': 'DTA',
        }
        words = text.split()
        result = []
        for i, w in enumerate(words):
            w_lower = w.lower()
            if w_lower in uppercase_words:
                result.append(uppercase_words[w_lower])
            elif i == 0 or w_lower not in small_words:
                result.append(w.capitalize())
            else:
                result.append(w_lower)
        return ' '.join(result)

    def extract_content_topics(self, title: str, summary: str, description: str,
                               url: str, product: str = '',
                               crawled_text: str = '') -> List[Tuple[str, str]]:
        """
        Extract meaningful topics from page content. No taxonomy involved.
        Sources are gated by self.sources list.

        Returns:
            List of (topic, source) tuples where source is 'title', 'url', 'content', or 'crawl'
        """
        topics = []
        seen = set()
        prod_lower = product.lower() if product else ''

        def _add_phrases(phrases: List[str], source_tag: str, max_add: int = 12):
            """Helper to add topic phrases with dedup and product filtering."""
            added = 0
            for phrase in phrases:
                if added >= max_add:
                    break
                key = phrase.lower()
                if prod_lower and (key in prod_lower or prod_lower.startswith(key)):
                    continue
                already_covered = False
                for existing_key in seen:
                    if key in existing_key or existing_key in key:
                        already_covered = True
                        break
                if not already_covered:
                    topics.append((self._title_case(phrase), source_tag))
                    seen.add(key)
                    added += 1

        # 1. Title — primary topic source
        if 'title' in self.sources:
            title_topic = self._clean_title_to_topic(title, product)
            if title_topic:
                key = title_topic.lower()
                if key not in seen:
                    topics.append((self._title_case(title_topic), 'title'))
                    seen.add(key)

        # 2. URL path segments — structural topics
        if 'url' in self.sources:
            url_topics = self._extract_url_topics(url, product)
            for t in url_topics:
                key = t.lower()
                if key not in seen:
                    topics.append((t, 'url'))
                    seen.add(key)

        # 3. Summary + Description — supporting topic phrases
        if 'content' in self.sources:
            content = ' '.join(filter(None, [
                str(summary) if summary and not pd.isna(summary) else '',
                str(description) if description and not pd.isna(description) else ''
            ]))
            content_phrases = self._extract_topic_phrases(content)
            _add_phrases(content_phrases, 'content', max_add=12)

        # 4. Crawled page content — live fetched topics
        if 'crawl' in self.sources and crawled_text:
            crawl_phrases = self._extract_topic_phrases(crawled_text)
            _add_phrases(crawl_phrases, 'crawl', max_add=12)

        return topics

    # ==================== MAIN PROCESSING ====================

    def process_matching(self) -> pd.DataFrame:
        """Main processing: extract content topics for each URL."""
        print(f"\nProcessing strict content matching (sources: {', '.join(self.sources)})...")

        # Crawl URLs upfront if 'crawl' source is selected
        if 'crawl' in self.sources:
            urls = self.semantic_df['URL'].astype(str).tolist()
            # Strip anchors before crawling
            clean_urls = list(dict.fromkeys(u.split('#')[0] for u in urls if u))
            self._crawled_content = self.fetch_urls_concurrent(clean_urls)

        results = []

        total_urls = len(self.semantic_df)
        urls_with_topics = 0
        total_topics = 0
        domain_counts = {}
        self._url_segments = {}  # URL -> list of top segments (for ranked rows)

        for idx, row in self.semantic_df.iterrows():
            url = str(row.get('URL', ''))
            if '#' in url:
                url = url.split('#')[0]

            title = row.get('Title', '') if pd.notna(row.get('Title', '')) else ''
            summary = row.get('Summary', '') if pd.notna(row.get('Summary', '')) else ''
            description = row.get('Description', '') if pd.notna(row.get('Description', '')) else ''

            # Product: from semantic file first, then from URL
            semantic_product = row.get('Product', None)
            if semantic_product and not pd.isna(semantic_product):
                product = str(semantic_product).strip()
            else:
                product = self._extract_product_from_url(url)

            # Domain: classified from content keywords
            domain = self._classify_domain(product, title, summary, description)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

            # Segments: classified from content keywords (top 3 for ranked rows)
            segments = self._classify_segments(product, title, summary, description, url)
            self._url_segments[url] = segments
            segment = segments[0] if segments else ''

            if self.debug:
                print(f"\n[DEBUG] === URL: {url} ===")
                print(f"[DEBUG] Product: {product or '(none)'}")
                print(f"[DEBUG] Domain: {domain}")
                seg_display = ', '.join(s for s in segments if s)
                print(f"[DEBUG] Segments: {seg_display or '(none)'}")
                print(f"[DEBUG] Title: {title[:80]}{'...' if len(str(title)) > 80 else ''}")

            # Extract content-derived topics — NO taxonomy involved
            crawled_text = self._crawled_content.get(url, '')
            content_topics = self.extract_content_topics(title, summary, description, url, product,
                                                         crawled_text=crawled_text)

            if self.debug:
                if content_topics:
                    print(f"[DEBUG] Topics ({len(content_topics)}):")
                    for t, src in content_topics:
                        print(f"[DEBUG]   '{t}' (from {src})")
                else:
                    print(f"[DEBUG]   No topics extracted")

            if content_topics:
                urls_with_topics += 1
                for topic, source in content_topics:
                    total_topics += 1
                    results.append({
                        'URL': url,
                        'Title': title,
                        'Description': description,
                        'Summary': summary,
                        'Product': product,
                        'Domain': domain,
                        'Segment': segment,
                        'Topic': topic,
                        'Source': source,
                        'Unmapped_Reason': ''
                    })
            else:
                results.append({
                    'URL': url,
                    'Title': title,
                    'Description': description,
                    'Summary': summary,
                    'Product': product,
                    'Domain': domain,
                    'Segment': segment,
                    'Topic': '',
                    'Source': '',
                    'Unmapped_Reason': 'No content (Title/Summary/Description/URL empty)'
                })

            if (idx + 1) % 50 == 0:
                print(f"  Processed {idx + 1}/{total_urls} URLs...")

        print(f"\nStrict content matching complete!")
        print(f"  URLs with topics: {urls_with_topics}/{total_urls} ({urls_with_topics/max(total_urls,1)*100:.1f}%)")
        print(f"  Total topics extracted: {total_topics}")
        if urls_with_topics > 0:
            print(f"  Average topics per URL: {total_topics/urls_with_topics:.1f}")
        print(f"  Domain breakdown:")
        for d in list(self._domain_keywords.keys()) + ['General']:
            if d in domain_counts:
                print(f"    {d}: {domain_counts[d]}")

        results_df = pd.DataFrame(results)
        if len(results_df) > 0:
            results_df = self.consolidate_results(results_df)
        return results_df

    def consolidate_results(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """Consolidate to ranked rows per URL — up to 6 topics per row, up to 3 ranks.

        Rank 1: Primary segment, best topics (title/URL first)
        Rank 2: Secondary segment, next batch of topics
        Rank 3: Tertiary segment, remaining topics
        Each rank may have a different segment classification.
        """
        unmapped = results_df[results_df['Topic'] == ''].copy()
        mapped = results_df[results_df['Topic'] != ''].copy()

        if len(mapped) == 0:
            unmapped['Top_Relevance'] = 'Unmapped'
            for col in ['Topic', 'Source']:
                if col in unmapped.columns:
                    unmapped = unmapped.drop(col, axis=1)
            return unmapped

        max_per_row = 6  # Up to 6 topics per row
        max_ranks = 3    # Up to 3 ranked rows per URL

        grouped = mapped.groupby('URL', dropna=False, sort=False)

        consolidated_rows = []
        max_topics_in_row = 0

        for url, group in grouped:
            topics = group['Topic'].tolist()
            sources = group['Source'].tolist()

            title = group['Title'].iloc[0]
            description = group['Description'].iloc[0]
            summary = group['Summary'].iloc[0]
            product = group['Product'].iloc[0]
            domain = group['Domain'].iloc[0]
            segments = self._url_segments.get(url, [''])

            # Filter out segment-as-topic (check all segment names)
            seg_names_lower = {s.lower() for s in segments if s}
            filtered = [(t, s) for t, s in zip(topics, sources)
                        if t.lower() not in seg_names_lower]
            if filtered:
                topics, sources = zip(*filtered)
                topics = list(topics)
                sources = list(sources)

            # Split topics into chunks of max_per_row for different ranks
            for rank_idx in range(max_ranks):
                start = rank_idx * max_per_row
                chunk_topics = topics[start:start + max_per_row]
                chunk_sources = sources[start:start + max_per_row]

                if not chunk_topics:
                    break

                # Use different segment per rank if available
                seg = (segments[rank_idx] if rank_idx < len(segments)
                       else segments[-1] if segments else '')
                rank = rank_idx + 1

                max_topics_in_row = max(max_topics_in_row, len(chunk_topics))

                row_data = {
                    'URL': url,
                    'Title': title,
                    'Description': description,
                    'Summary': summary,
                    'Product': product,
                    'Domain': domain,
                    'Segment': seg,
                }

                for i, topic in enumerate(chunk_topics, start=1):
                    row_data[f'Topic_{i}'] = topic
                for i, src in enumerate(chunk_sources, start=1):
                    row_data[f'Source_{i}'] = src

                # Relevance based on primary source in this chunk
                primary_source = chunk_sources[0] if chunk_sources else ''
                if primary_source == 'title':
                    row_data['Top_Relevance'] = 'Best Match'
                elif primary_source == 'url':
                    row_data['Top_Relevance'] = 'Highly Relevant'
                elif primary_source == 'crawl':
                    row_data['Top_Relevance'] = 'Crawl-Derived'
                else:
                    row_data['Top_Relevance'] = 'Content-Derived'

                row_data['Unmapped_Reason'] = ''
                row_data['Rank'] = rank
                consolidated_rows.append(row_data)

        consolidated_df = pd.DataFrame(consolidated_rows)

        # Ensure all topic/source columns exist up to max_per_row
        col_count = min(max(max_topics_in_row, 1), max_per_row)
        for i in range(1, col_count + 1):
            if f'Topic_{i}' not in consolidated_df.columns:
                consolidated_df[f'Topic_{i}'] = ''
            if f'Source_{i}' not in consolidated_df.columns:
                consolidated_df[f'Source_{i}'] = ''

        consolidated_df = consolidated_df.fillna('')

        # Re-add unmapped
        if len(unmapped) > 0:
            for i in range(1, col_count + 1):
                unmapped[f'Topic_{i}'] = ''
                unmapped[f'Source_{i}'] = ''
            unmapped['Top_Relevance'] = 'Unmapped'
            unmapped['Rank'] = 1
            for col in ['Topic', 'Source']:
                if col in unmapped.columns:
                    unmapped = unmapped.drop(col, axis=1)
            consolidated_df = pd.concat([consolidated_df, unmapped], ignore_index=True)

        # Reorder columns
        base_cols = ['URL', 'Title', 'Description', 'Summary', 'Product', 'Domain', 'Segment']
        topic_cols = [f'Topic_{i}' for i in range(1, col_count + 1)]
        source_cols = [f'Source_{i}' for i in range(1, col_count + 1)]
        end_cols = ['Top_Relevance', 'Unmapped_Reason', 'Rank']
        final_order = base_cols + topic_cols + source_cols + end_cols
        final_order = [c for c in final_order if c in consolidated_df.columns]
        consolidated_df = consolidated_df[final_order]

        rank_counts = consolidated_df['Rank'].value_counts().sort_index()
        rank_summary = ', '.join(f'Rank {int(r)}: {c}' for r, c in rank_counts.items())
        print(f"  Consolidated to {len(consolidated_df)} rows ({rank_summary}), up to {col_count} topics per row")
        return consolidated_df

    def save_output(self, results_df: pd.DataFrame):
        """Save results to Excel with sanitization to prevent corruption."""
        print(f"\nSaving results to {self.output_file}...")
        sanitize_dataframe(results_df).to_excel(
            self.output_file, index=False, sheet_name='Strict Content Topics'
        )
        print(f"  Output saved: {self.output_file}")

    def run(self):
        """Execute the complete strict matching workflow."""
        print("=" * 60)
        print(f"Strict Content Matcher - Country: {self.country_code}")
        print("=" * 60)

        country_info = next(c for c in self.country_config.get_available_countries()
                           if c['code'] == self.country_code)
        print(f"Country: {country_info['name']} ({country_info['language']})")
        print(f"Mode: Content-derived topics (NO taxonomy dependency)")
        print(f"Sources: {', '.join(self.sources)}")
        print(f"Domains: {', '.join(list(self._domain_keywords.keys()) + ['General'])}")
        print(f"Input: Semantic file only")
        if 'crawl' in self.sources:
            if TRAFILATURA_AVAILABLE:
                print(f"Crawling: Enabled (trafilatura)")
            elif REQUESTS_AVAILABLE:
                print(f"Crawling: Enabled (requests fallback)")
            else:
                print(f"Crawling: WARNING - no crawling library available")
        if self.debug:
            print(f"Debug mode: ENABLED")
        if self.url_filter:
            print(f"URL filter: '{self.url_filter}'")
        if self.max_rows > 0:
            print(f"Max rows: {self.max_rows}")
        print("=" * 60)

        self.load_data()
        results_df = self.process_matching()
        self.save_output(results_df)

        print("\n" + "=" * 60)
        print("Strict content matching completed!")
        print(f"Output saved to: {self.output_file}")
        print("=" * 60)


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(
        description='Strict Content Matcher - generates topics from page content (no taxonomy needed)'
    )
    parser.add_argument('-c', '--country', type=str, default=None)
    parser.add_argument('--semantic-file', type=str, default=None)
    parser.add_argument('-o', '--output', type=str, default=None)
    parser.add_argument('--top-n', type=int, default=6)
    parser.add_argument('--debug', action='store_true', default=False)
    parser.add_argument('--max-rows', type=int, default=0)
    parser.add_argument('--url-filter', type=str, default='')
    parser.add_argument('--sources', type=str, nargs='+',
                        default=['title', 'url', 'content'],
                        choices=['title', 'url', 'content', 'crawl'],
                        help='Topic sources to use (default: title url content)')
    parser.add_argument('--max-workers', type=int, default=10,
                        help='Concurrent crawl threads (default: 10)')

    args = parser.parse_args()

    matcher = StrictContentMatcher(
        country_code=args.country,
        semantic_file=args.semantic_file,
        output_file=args.output,
        top_n=args.top_n,
        debug=args.debug,
        max_rows=args.max_rows,
        url_filter=args.url_filter,
        sources=args.sources,
        max_workers=args.max_workers
    )
    matcher.run()


if __name__ == "__main__":
    main()
