"""
Convert Salesforce Lightning internal URLs to public community URLs.

Salesforce exports contain internal Lightning href tags like:
  <a href="/lightning/articles/Knowledge/{slug}?language=nl_BE">...</a>

This tool converts them to public community URLs like:
  https://taasupport.wolterskluwer.be/customers/s/article/{slug}?language=nl_BE

Usage:
  python convert_salesforce_urls.py -i input.csv -c BE
  python convert_salesforce_urls.py -i input.csv -c NL -o output.csv
  python convert_salesforce_urls.py -i input.csv -c SE --column URL

Supported countries: NL, SE, BE (auto-detected from filename if not specified)
"""

import argparse
import csv
import os
import re
import sys

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# Country -> public community article base URL
COMMUNITY_BASE_URLS = {
    'BE': 'https://taasupport.wolterskluwer.be/customers/s/article',
    'NL': 'https://wktaaeu.my.site.com/nlcommunity/s/article',
    'SE': 'https://wktaaeu.my.site.com/se/s/article',
}

# Regex to extract article slug and language from Lightning href
_LIGHTNING_PATTERN = re.compile(
    r'/lightning/articles/Knowledge/([^?"]+)\?language=([a-zA-Z_]+)'
)


def detect_country_from_filename(filename):
    """Try to detect country code from filename like crawl_results_nl_BE.csv."""
    basename = os.path.basename(filename).upper()
    for code in COMMUNITY_BASE_URLS:
        if f'_{code}.' in basename or f'_{code}_' in basename or basename.endswith(f'_{code}'):
            return code
    return None


def extract_url_from_cell(cell_value):
    """
    Extract URL from cell, handling:
    - HTML anchors: <a href="/lightning/...">text</a>
    - Plain Lightning URLs: /lightning/articles/Knowledge/{slug}
    - Already public URLs: https://...

    Returns the extracted URL string.
    """
    cell_str = str(cell_value)

    # Check for HTML anchor tag
    if '<a ' in cell_str.lower() and HAS_BS4:
        try:
            soup = BeautifulSoup(cell_str, 'html.parser')
            a_tag = soup.find('a', href=True)
            if a_tag:
                return a_tag['href']
        except Exception:
            # If parsing fails, fall through to return original
            pass

    # Return as-is if not HTML or parsing failed
    return cell_str


def convert_url(cell, base_url):
    """
    Convert a Lightning URL cell to a public URL.
    Handles both plain URLs and HTML anchor tags.
    Returns (converted_url, True) or (original_cell, False).
    """
    # First extract URL from HTML if needed
    url = extract_url_from_cell(cell)

    # Try to convert Lightning URL to public URL
    match = _LIGHTNING_PATTERN.search(url)
    if match:
        slug = match.group(1)
        lang = match.group(2)
        return f'{base_url}/{slug}?language={lang}', True

    # If we extracted a URL from HTML but it's not a Lightning URL,
    # return the extracted URL (not the original HTML)
    if url != cell and not url.startswith('http'):
        # Relative URL that's not Lightning pattern - might be useful
        return url, False

    return cell, False


def convert_file(input_file, output_file, country_code, url_column='URL'):
    """
    Convert all Lightning URLs in a CSV file to public URLs.

    Args:
        input_file: Path to input CSV
        output_file: Path to output CSV
        country_code: Country code (BE, NL, SE)
        url_column: Name of the URL column (default: 'URL')

    Returns:
        dict with 'converted', 'unchanged', 'total' counts
    """
    base_url = COMMUNITY_BASE_URLS.get(country_code.upper())
    if not base_url:
        raise ValueError(
            f"Unknown country code '{country_code}'. "
            f"Supported: {', '.join(sorted(COMMUNITY_BASE_URLS.keys()))}"
        )

    converted = 0
    unchanged = 0

    with open(input_file, 'r', encoding='utf-8-sig') as fin, \
         open(output_file, 'w', encoding='utf-8-sig', newline='') as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout)

        header = next(reader)
        writer.writerow(header)

        # Find URL column (case-insensitive)
        url_idx = None
        for i, col in enumerate(header):
            if col.strip().upper() == url_column.upper():
                url_idx = i
                break

        if url_idx is None:
            raise ValueError(
                f"Column '{url_column}' not found in CSV. "
                f"Available columns: {', '.join(header)}"
            )

        for row in reader:
            cell = row[url_idx]
            row[url_idx], was_converted = convert_url(cell, base_url)
            if was_converted:
                converted += 1
            else:
                unchanged += 1
            writer.writerow(row)

    return {'converted': converted, 'unchanged': unchanged, 'total': converted + unchanged}


def main():
    parser = argparse.ArgumentParser(
        description='Convert Salesforce Lightning URLs to public community URLs'
    )
    parser.add_argument('-i', '--input', required=True, help='Input CSV file')
    parser.add_argument('-o', '--output', help='Output CSV file (default: {input}_public_urls.csv)')
    parser.add_argument('-c', '--country', help='Country code: NL, SE, BE (auto-detected from filename if omitted)')
    parser.add_argument('--column', default='URL', help='URL column name (default: URL)')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    # Auto-detect country from filename if not specified
    country = args.country
    if not country:
        country = detect_country_from_filename(args.input)
        if not country:
            print(f"Error: Could not detect country from filename. Use -c to specify (NL, SE, BE)")
            sys.exit(1)
        print(f"Auto-detected country: {country}")

    country = country.upper()

    # Default output filename
    output = args.output
    if not output:
        base, ext = os.path.splitext(args.input)
        output = f'{base}_public_urls{ext}'

    print(f"Input:   {args.input}")
    print(f"Output:  {output}")
    print(f"Country: {country} -> {COMMUNITY_BASE_URLS[country]}")

    if not HAS_BS4:
        print("\nWARNING: beautifulsoup4 not installed. HTML anchor tag parsing disabled.")
        print("Install with: pip install beautifulsoup4")

    print()

    result = convert_file(args.input, output, country, args.column)

    print(f"Converted: {result['converted']:,} URLs")
    if result['unchanged'] > 0:
        print(f"Unchanged: {result['unchanged']:,} URLs (no Lightning pattern found)")
    print(f"Total:     {result['total']:,} rows")
    print(f"\nSaved to: {output}")


if __name__ == '__main__':
    main()
