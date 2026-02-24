"""
Salesforce CSV Processor - Bridge between raw Salesforce exports and NLMap semantic format

Handles the "482-column mess" from Salesforce Knowledge exports:
- Auto-detects useful columns (URL, Title, Summary, Answer__c/Description)
- Extracts URLs from HTML anchor tags
- Converts Lightning URLs to public community URLs
- Generates keywords using ContentKeywordExtractor
- Outputs clean semantic file ready for taxonomy matching

Usage:
    from salesforce_csv_processor import process_salesforce_csv

    result = process_salesforce_csv(
        input_csv="Belgium, articles.csv",
        output_file="semantic_BE.xlsx",
        country_code="BE",
        taxonomy_file="taxonomy.xlsx",  # Optional
        progress_callback=lambda pct, msg: print(f"{pct}% - {msg}")
    )

    print(f"Processed {result['total_rows']} rows")
    print(f"URLs extracted: {result['urls_extracted']}")
    print(f"Keywords generated: {result['keywords_generated']}")
"""

import pandas as pd
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, Dict

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# Import from existing modules
from convert_salesforce_urls import COMMUNITY_BASE_URLS, extract_url_from_cell, _LIGHTNING_PATTERN
from content_keyword_extractor import ContentKeywordExtractor


def detect_csv_structure(csv_path):
    """
    Auto-detect column structure in Salesforce CSV export.

    Handles:
    - BOM (byte order mark) in headers
    - 482+ column exports (476 junk columns)
    - Various column name formats

    Returns:
        dict with keys: url_col, title_col, summary_col, content_col, data_categories_col (column indices)
    """
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader)

    # Strip BOM and whitespace from headers
    header = [col.strip().lstrip('\ufeff') for col in header]

    result = {
        'url_col': None,
        'title_col': None,
        'summary_col': None,
        'content_col': None,
        'data_categories_col': None
    }

    # Case-insensitive column detection
    for i, col in enumerate(header):
        col_lower = col.lower()

        # URL column
        if col == 'Knowledge_Url__c' or 'url' in col_lower:
            if result['url_col'] is None:  # Take first match
                result['url_col'] = i

        # Title column
        elif col == 'Title' or col_lower == 'title':
            result['title_col'] = i

        # Summary column
        elif col == 'Summary' or col_lower == 'summary':
            result['summary_col'] = i

        # Content column (Answer__c, Body, Description)
        elif col in ('Answer__c', 'Body', 'Description') or \
             col_lower in ('answer', 'body', 'description', 'content'):
            if result['content_col'] is None:  # Take first match
                result['content_col'] = i

        # Data Categories column
        elif col == 'Data_Categories__c' or col_lower == 'data_categories__c':
            result['data_categories_col'] = i

    # Warn about missing columns (data_categories is optional)
    missing = [k for k, v in result.items() if v is None and k != 'data_categories_col']
    if missing:
        print(f"WARNING: Could not detect columns: {missing}")
        print(f"Available columns ({len(header)}): {header[:10]}...")

    # Info about data categories
    if result['data_categories_col'] is not None:
        print(f"INFO: Data_Categories__c column found at index {result['data_categories_col']}")

    return result


def extract_and_convert_url(cell_value, base_url):
    """
    Extract URL from cell (handling HTML anchors) and convert to public URL.

    Args:
        cell_value: Cell content (may be HTML anchor tag or plain URL)
        base_url: Community base URL for conversion

    Returns:
        tuple: (public_url, was_converted)
    """
    # Extract URL from HTML anchor if present
    url = extract_url_from_cell(cell_value)

    # Try to convert Lightning URL
    match = _LIGHTNING_PATTERN.search(url)
    if match:
        slug = match.group(1)
        lang = match.group(2)
        public_url = f'{base_url}/{slug}?language={lang}'
        return public_url, True

    # Return extracted URL (may differ from cell_value if HTML was parsed)
    return url, False


def clean_text_content(text, max_length=5000):
    """
    Clean text content (Summary, Description) for keyword extraction.

    Args:
        text: Raw text (may contain HTML)
        max_length: Maximum length to return

    Returns:
        Cleaned text string
    """
    if pd.isna(text):
        return ''

    text_str = str(text)

    # Remove HTML tags if present
    if '<' in text_str and '>' in text_str:
        if HAS_BS4:
            try:
                soup = BeautifulSoup(text_str, 'html.parser')
                text_str = soup.get_text(separator=' ', strip=True)
            except Exception as e:
                # If BS4 fails, try regex fallback
                import re
                text_str = re.sub(r'<[^>]+>', ' ', text_str)
                text_str = re.sub(r'\s+', ' ', text_str)
        else:
            # Fallback: simple regex HTML removal
            import re
            text_str = re.sub(r'<[^>]+>', ' ', text_str)
            text_str = re.sub(r'\s+', ' ', text_str)

        # Decode HTML entities
        import html
        text_str = html.unescape(text_str)

    # Truncate if too long
    if len(text_str) > max_length:
        text_str = text_str[:max_length]

    return text_str.strip()


def load_category_mapping(country_code):
    """
    Load category mapping file for a country.

    Args:
        country_code: Country code (BE, NL, SE)

    Returns:
        dict: Category name -> Product name mapping (or None if file not found)
    """
    import json
    from pathlib import Path

    mapping_file = Path(__file__).parent / 'countries' / country_code / 'category_mapping.json'

    if not mapping_file.exists():
        print(f"INFO: No category mapping file found at {mapping_file}")
        return None

    try:
        with open(mapping_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('mappings', {})
    except Exception as e:
        print(f"WARNING: Could not load category mapping: {e}")
        return None


def map_categories_to_products(categories_str, mapping):
    """
    Map Data_Categories__c string to product names.

    Args:
        categories_str: Semicolon-separated category string (e.g., "Adsolut_Account;ExpertM_Plus")
        mapping: Category -> Product mapping dict (or None)

    Returns:
        list: Mapped product names (duplicates removed, nulls filtered)
    """
    if pd.isna(categories_str) or not str(categories_str).strip():
        return []

    # Split on semicolon
    categories = [c.strip() for c in str(categories_str).split(';')]

    # Map to products
    products = []
    for cat in categories:
        if not cat:
            continue

        if mapping and cat in mapping:
            # Use mapping
            product = mapping[cat]
            if product:  # Skip None (filtered categories)
                products.append(product)
        else:
            # No mapping - use original category name (might match taxonomy directly)
            products.append(cat)

    # Remove duplicates while preserving order
    seen = set()
    unique_products = []
    for p in products:
        if p not in seen:
            seen.add(p)
            unique_products.append(p)

    return unique_products


def process_salesforce_csv(
    input_csv: str,
    output_file: str,
    country_code: str,
    taxonomy_file: Optional[str] = None,
    threshold: int = 80,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> Dict:
    """
    Process Salesforce Knowledge CSV export to NLMap semantic format.

    Args:
        input_csv: Path to Salesforce CSV export
        output_file: Path to output Excel file
        country_code: Country code (BE, NL, SE) for URL conversion
        taxonomy_file: Optional taxonomy file for keyword ranking
        threshold: Similarity threshold for keyword extraction (default: 80)
        progress_callback: Optional callback(percent, message) for progress updates

    Returns:
        dict with statistics: total_rows, urls_extracted, keywords_generated, etc.
    """
    def update_progress(pct, msg):
        if progress_callback:
            progress_callback(pct, msg)

    # Validate country code
    country_code = country_code.upper()
    base_url = COMMUNITY_BASE_URLS.get(country_code)
    if not base_url:
        raise ValueError(
            f"Unknown country code '{country_code}'. "
            f"Supported: {', '.join(sorted(COMMUNITY_BASE_URLS.keys()))}"
        )

    update_progress(0, "Detecting CSV structure...")

    # Auto-detect column structure
    structure = detect_csv_structure(input_csv)

    # Load category mapping (if available)
    category_mapping = load_category_mapping(country_code)
    if category_mapping:
        update_progress(3, f"Loaded category mapping ({len(category_mapping)} categories)")

    # Read CSV
    update_progress(5, "Loading CSV file...")
    df = pd.read_csv(input_csv, encoding='utf-8-sig')

    total_rows = len(df)
    update_progress(10, f"Processing {total_rows:,} rows...")

    # Extract useful columns
    rows_data = []
    urls_extracted = 0
    urls_converted = 0
    products_extracted = 0
    category_stats = {}  # Track category usage

    for idx, row in df.iterrows():
        # Progress update every 100 rows
        if idx % 100 == 0:
            pct = 10 + int((idx / total_rows) * 30)  # 10-40%
            update_progress(pct, f"Extracting URLs: {idx}/{total_rows}")

        row_data = {}

        # Extract and convert URL
        if structure['url_col'] is not None:
            url_cell = row.iloc[structure['url_col']]
            url, was_converted = extract_and_convert_url(url_cell, base_url)
            row_data['URL'] = url
            if url and str(url).strip():
                urls_extracted += 1
                if was_converted:
                    urls_converted += 1
        else:
            # Generate placeholder URL if column missing
            row_data['URL'] = f"placeholder_{idx}"

        # Extract Title
        if structure['title_col'] is not None:
            row_data['Title'] = str(row.iloc[structure['title_col']]) if pd.notna(row.iloc[structure['title_col']]) else ''
        else:
            row_data['Title'] = ''

        # Extract Summary
        if structure['summary_col'] is not None:
            row_data['Summary'] = clean_text_content(row.iloc[structure['summary_col']])
        else:
            row_data['Summary'] = ''

        # Extract Description (from Answer__c or similar)
        if structure['content_col'] is not None:
            row_data['Description'] = clean_text_content(row.iloc[structure['content_col']])
        else:
            row_data['Description'] = ''

        # Extract and map Product from Data_Categories__c
        if structure['data_categories_col'] is not None:
            categories_str = row.iloc[structure['data_categories_col']]
            products = map_categories_to_products(categories_str, category_mapping)

            if products:
                # Join multiple products with semicolon
                row_data['Product'] = ';'.join(products)
                products_extracted += 1

                # Track category usage for stats
                for cat in str(categories_str).split(';'):
                    cat = cat.strip()
                    if cat:
                        category_stats[cat] = category_stats.get(cat, 0) + 1
            else:
                row_data['Product'] = ''
        else:
            row_data['Product'] = ''

        rows_data.append(row_data)

    # Create DataFrame
    update_progress(40, "Creating semantic file...")
    semantic_df = pd.DataFrame(rows_data)

    # Deduplicate URLs (keep first occurrence)
    before_dedup = len(semantic_df)
    semantic_df = semantic_df.drop_duplicates(subset=['URL'], keep='first')
    after_dedup = len(semantic_df)

    if before_dedup > after_dedup:
        update_progress(45, f"Removed {before_dedup - after_dedup} duplicate URLs")

    # Expand rows where Product contains multiple products (semicolon-separated)
    update_progress(47, "Expanding multi-product rows...")
    expanded_rows = []
    for _, row in semantic_df.iterrows():
        product = row.get('Product', '')
        if product and ';' in product:
            # Multiple products - create one row per product
            products = [p.strip() for p in product.split(';') if p.strip()]
            for prod in products:
                new_row = row.copy()
                new_row['Product'] = prod
                expanded_rows.append(new_row)
        else:
            # Single product or no product - keep as is
            expanded_rows.append(row)

    semantic_df = pd.DataFrame(expanded_rows)
    rows_after_expansion = len(semantic_df)

    if rows_after_expansion > after_dedup:
        update_progress(48, f"Expanded to {rows_after_expansion} rows ({rows_after_expansion - after_dedup} multi-product)")

    # Save intermediate file for keyword extraction
    update_progress(50, "Generating keywords...")
    temp_file = Path(output_file).parent / f"_temp_semantic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    try:
        semantic_df.to_excel(temp_file, index=False)

        # Extract keywords using ContentKeywordExtractor
        extractor = ContentKeywordExtractor(
            taxonomy_file=taxonomy_file,
            threshold=threshold,
            crawl_urls=False  # Don't crawl - use columns
        )

        update_progress(60, "Extracting keywords from content...")

        # Process with keyword extraction
        extractor.process_file(
            input_file=str(temp_file),
            output_file=output_file
        )

        # Clean up temp file (keep for debugging if needed)
        # temp_file.unlink()  # Commented out for debugging
        print(f"\nDEBUG: Temp file saved at: {temp_file}")
        print("       Check this file to see if Product column is correct BEFORE keyword extraction")

        update_progress(95, "Finalizing output...")

        # Read final output to get keyword stats
        final_df = pd.read_excel(output_file)
        keyword_cols = [col for col in final_df.columns if col.startswith('Keyword ')]
        keywords_generated = final_df[keyword_cols].notna().sum().sum()

    except Exception as e:
        # Clean up temp file on error
        if temp_file.exists():
            temp_file.unlink()
        raise e

    update_progress(100, "Complete!")

    # Get top products for stats
    top_products = []
    if category_stats:
        from collections import Counter
        top_categories = Counter(category_stats).most_common(5)
        top_products = [f"{cat} ({count})" for cat, count in top_categories]

    # Return statistics
    return {
        'total_rows': total_rows,
        'output_rows': rows_after_expansion,
        'unique_urls': after_dedup,
        'duplicates_removed': before_dedup - after_dedup,
        'multi_product_expansion': rows_after_expansion - after_dedup,
        'urls_extracted': urls_extracted,
        'urls_converted': urls_converted,
        'products_extracted': products_extracted,
        'top_products': top_products,
        'keywords_generated': int(keywords_generated),
        'output_file': output_file,
        'country_code': country_code,
        'base_url': base_url
    }


def main():
    """CLI interface for testing."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description='Process Salesforce CSV export to NLMap semantic format'
    )
    parser.add_argument('-i', '--input', required=True,
                        help='Input Salesforce CSV file')
    parser.add_argument('-o', '--output', required=True,
                        help='Output semantic Excel file')
    parser.add_argument('-c', '--country', required=True,
                        help='Country code (BE, NL, SE)')
    parser.add_argument('-t', '--taxonomy', default=None,
                        help='Taxonomy file for keyword ranking (optional)')
    parser.add_argument('--threshold', type=int, default=80,
                        help='Similarity threshold (default: 80)')

    args = parser.parse_args()

    # Check input exists
    if not Path(args.input).exists():
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)

    # Progress callback
    def show_progress(pct, msg):
        print(f"[{pct:3d}%] {msg}")

    print(f"Processing Salesforce CSV: {args.input}")
    print(f"Country: {args.country}")
    print(f"Output: {args.output}")
    if args.taxonomy:
        print(f"Taxonomy: {args.taxonomy}")
    print()

    try:
        result = process_salesforce_csv(
            input_csv=args.input,
            output_file=args.output,
            country_code=args.country,
            taxonomy_file=args.taxonomy,
            threshold=args.threshold,
            progress_callback=show_progress
        )

        print("\n" + "="*60)
        print("SUCCESS!")
        print(f"  Input rows: {result['total_rows']:,}")
        print(f"  Unique URLs: {result['unique_urls']:,}")
        print(f"  Output rows: {result['output_rows']:,}")
        if result.get('duplicates_removed', 0) > 0:
            print(f"  Duplicates removed: {result['duplicates_removed']:,}")
        if result.get('multi_product_expansion', 0) > 0:
            print(f"  Multi-product expansion: +{result['multi_product_expansion']:,} rows")
        print(f"  URLs extracted: {result['urls_extracted']:,}")
        print(f"  URLs converted: {result['urls_converted']:,} (Lightning → public)")
        if result.get('products_extracted', 0) > 0:
            print(f"  Products assigned: {result['products_extracted']:,} unique URLs")
            if result.get('top_products'):
                print(f"  Top categories: {', '.join(result['top_products'][:3])}")
        print(f"  Keywords generated: {result['keywords_generated']:,}")
        print(f"  Output file: {result['output_file']}")
        print("="*60)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
