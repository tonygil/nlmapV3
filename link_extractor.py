"""
Link Extractor - Crawls URLs and extracts all embedded hyperlinks
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# Configuration
INPUT_FILE = r"C:\Users\Tony.Gilpin\Downloads\2ndFeb\taxonomy_match_GB_2ndFeb_GB_cleaned_filtered_filtered_filtered.xlsx"
OUTPUT_FILE = r"C:\Users\Tony.Gilpin\Downloads\2ndFeb\embedded_links_report.xlsx"
MAX_WORKERS = 10
TIMEOUT = 15


def extract_links(url):
    """Crawl a URL and extract all hyperlinks."""
    result = {
        'Source_URL': url,
        'Status': 'Unknown',
        'Total_Links': 0,
        'Internal_Links': 0,
        'External_Links': 0,
        'Error': '',
        'Links': []  # List of (link_text, href, link_type)
    }

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }

        response = requests.get(url, headers=headers, timeout=TIMEOUT, verify=False, allow_redirects=True)
        result['Status'] = f'{response.status_code}'

        if response.status_code != 200:
            result['Error'] = f'HTTP {response.status_code}'
            return result

        soup = BeautifulSoup(response.text, 'html.parser')

        # Parse source URL for comparison
        source_parsed = urlparse(url)
        source_domain = source_parsed.netloc.lower()

        links = []
        internal_count = 0
        external_count = 0

        # Find all <a> tags with href
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()

            # Skip empty, anchor-only, or javascript links
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue

            # Get link text
            link_text = a_tag.get_text(strip=True)[:100] or '[No Text]'

            # Resolve relative URLs
            full_url = urljoin(url, href)

            # Determine if internal or external
            try:
                link_parsed = urlparse(full_url)
                link_domain = link_parsed.netloc.lower()

                if link_domain == source_domain or not link_domain:
                    link_type = 'Internal'
                    internal_count += 1
                else:
                    link_type = 'External'
                    external_count += 1

                links.append({
                    'Link_Text': link_text,
                    'Link_URL': full_url[:500],
                    'Link_Type': link_type,
                    'Link_Domain': link_domain or source_domain
                })
            except:
                continue

        result['Total_Links'] = len(links)
        result['Internal_Links'] = internal_count
        result['External_Links'] = external_count
        result['Links'] = links

    except requests.Timeout:
        result['Status'] = 'Timeout'
        result['Error'] = 'Request timed out'
    except requests.ConnectionError as e:
        result['Status'] = 'Connection Error'
        result['Error'] = str(e)[:100]
    except Exception as e:
        result['Status'] = 'Error'
        result['Error'] = str(e)[:100]

    return result


def main():
    print(f"Link Extractor Report Generator")
    print(f"=" * 50)
    print(f"Input: {INPUT_FILE}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    # Load the Excel file
    print("Loading Excel file...")
    try:
        df = pd.read_excel(INPUT_FILE)
        print(f"Loaded {len(df)} rows")
    except Exception as e:
        print(f"Error loading file: {e}")
        return

    # Find URL column
    url_col = None
    for col in df.columns:
        if col.upper() == 'URL':
            url_col = col
            break

    if not url_col:
        print("ERROR: No 'URL' column found")
        return

    # Get unique URLs
    urls = df[url_col].dropna().unique().tolist()
    print(f"Found {len(urls)} unique URLs to crawl")
    print()

    # Crawl URLs
    results = []
    all_links = []
    start_time = time.time()

    print(f"Crawling URLs with {MAX_WORKERS} workers...")
    print("-" * 50)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(extract_links, url): url for url in urls}

        completed = 0
        total_links = 0

        for future in as_completed(future_to_url):
            completed += 1
            result = future.result()

            # Store summary
            results.append({
                'Source_URL': result['Source_URL'],
                'Status': result['Status'],
                'Total_Links': result['Total_Links'],
                'Internal_Links': result['Internal_Links'],
                'External_Links': result['External_Links'],
                'Error': result['Error']
            })

            # Store individual links
            for link in result['Links']:
                all_links.append({
                    'Source_URL': result['Source_URL'],
                    'Link_Text': link['Link_Text'],
                    'Link_URL': link['Link_URL'],
                    'Link_Type': link['Link_Type'],
                    'Link_Domain': link['Link_Domain']
                })

            total_links += result['Total_Links']

            if completed % 100 == 0:
                print(f"[{completed}/{len(urls)}] Processed... ({total_links} links found)")

    elapsed = time.time() - start_time
    print()
    print(f"Crawling complete in {elapsed:.1f} seconds")
    print(f"Total links extracted: {len(all_links)}")
    print()

    # Create DataFrames
    summary_df = pd.DataFrame(results)
    links_df = pd.DataFrame(all_links)

    # Create external links only view
    external_links_df = links_df[links_df['Link_Type'] == 'External'].copy()

    # Domain summary
    domain_counts = links_df.groupby('Link_Domain').size().reset_index(name='Count')
    domain_counts = domain_counts.sort_values('Count', ascending=False)

    # External domain summary
    external_domain_counts = external_links_df.groupby('Link_Domain').size().reset_index(name='Count')
    external_domain_counts = external_domain_counts.sort_values('Count', ascending=False)

    # Summary statistics
    stats = {
        'Metric': [
            'Total URLs Crawled',
            'Successful Requests',
            'Failed Requests',
            'Total Links Found',
            'Internal Links',
            'External Links',
            'Unique Link Domains',
            'Unique External Domains',
            'Avg Links Per Page',
            'Crawl Duration (seconds)'
        ],
        'Value': [
            len(results),
            len([r for r in results if r['Status'] == '200']),
            len([r for r in results if r['Status'] != '200']),
            len(all_links),
            len(links_df[links_df['Link_Type'] == 'Internal']),
            len(external_links_df),
            links_df['Link_Domain'].nunique() if len(links_df) > 0 else 0,
            external_links_df['Link_Domain'].nunique() if len(external_links_df) > 0 else 0,
            round(len(all_links) / len(results), 1) if results else 0,
            round(elapsed, 1)
        ]
    }
    stats_df = pd.DataFrame(stats)

    # Write to Excel
    print(f"Writing report to {OUTPUT_FILE}...")
    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
        stats_df.to_excel(writer, sheet_name='Summary', index=False)
        links_df.to_excel(writer, sheet_name='All Links', index=False)
        external_links_df.to_excel(writer, sheet_name='External Links Only', index=False)
        domain_counts.to_excel(writer, sheet_name='Links by Domain', index=False)
        external_domain_counts.to_excel(writer, sheet_name='External Domains', index=False)
        summary_df.to_excel(writer, sheet_name='Page Summary', index=False)

    print()
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    for i, row in stats_df.iterrows():
        print(f"{row['Metric']}: {row['Value']}")
    print()
    print(f"Report saved to: {OUTPUT_FILE}")

    # Show top external domains
    if len(external_domain_counts) > 0:
        print()
        print("Top 10 External Domains:")
        print("-" * 30)
        for i, row in external_domain_counts.head(10).iterrows():
            print(f"  {row['Link_Domain']}: {row['Count']} links")


if __name__ == '__main__':
    main()
