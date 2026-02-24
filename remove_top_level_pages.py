"""
Remove Top Level Pages
Filters out URLs from a spreadsheet where the page contains "Topic Hierarchy" text.
These are considered top-level/landing pages rather than content pages.

Usage:
    python remove_top_level_pages.py -i input.xlsx -o output.xlsx
    python remove_top_level_pages.py -i input.xlsx  # auto-names output
"""

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Configuration ---
TAG_TEXT = "Topic Hierarchy"
MAX_WORKERS = 10
REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def create_session():
    """Create a requests session with retry logic."""
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry, pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def check_url_for_tag(session, url, tag_text=TAG_TEXT):
    """
    Fetch a URL and check if it contains the tag text.
    Returns (url, has_tag, error_msg).
    """
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        has_tag = tag_text.lower() in response.text.lower()
        return (url, has_tag, None)
    except requests.RequestException as e:
        return (url, False, str(e))


def process_spreadsheet(input_file, output_file=None, tag_text=TAG_TEXT, max_workers=MAX_WORKERS):
    """
    Read spreadsheet, check each URL for tag text, remove matching rows.
    Returns (kept_count, removed_count, error_count).
    """
    # Read input
    df = pd.read_excel(input_file)
    total_rows = len(df)
    print(f"Loaded {total_rows} rows from: {os.path.basename(input_file)}")
    print(f"Columns: {list(df.columns)}")

    if "URL" not in df.columns:
        print("ERROR: No 'URL' column found in spreadsheet.")
        sys.exit(1)

    # Get unique URLs to avoid duplicate fetches
    unique_urls = df["URL"].dropna().unique()
    print(f"Unique URLs to check: {len(unique_urls)}")
    print(f"Searching for pages containing: '{tag_text}'")
    print(f"Using {max_workers} concurrent threads...\n")

    # Check URLs concurrently
    session = create_session()
    url_results = {}  # url -> (has_tag, error)
    checked = 0
    tagged_count = 0
    error_count = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(check_url_for_tag, session, url, tag_text): url
            for url in unique_urls
        }

        for future in as_completed(futures):
            url, has_tag, error = future.result()
            url_results[url] = (has_tag, error)
            checked += 1

            if has_tag:
                tagged_count += 1
            if error:
                error_count += 1

            # Progress update every 100 URLs
            if checked % 100 == 0 or checked == len(unique_urls):
                elapsed = time.time() - start_time
                rate = checked / elapsed if elapsed > 0 else 0
                print(f"  Checked {checked}/{len(unique_urls)} URLs "
                      f"({tagged_count} top-level found, {error_count} errors) "
                      f"[{rate:.0f} URLs/sec]")

    elapsed = time.time() - start_time
    print(f"\nScan complete in {elapsed:.1f}s")
    print(f"  Top-level pages found: {tagged_count}")
    print(f"  Content pages: {len(unique_urls) - tagged_count - error_count}")
    print(f"  Errors (kept): {error_count}")

    # Filter out rows where URL has the tag
    top_level_urls = {url for url, (has_tag, _) in url_results.items() if has_tag}
    mask_keep = ~df["URL"].isin(top_level_urls)
    df_kept = df[mask_keep].copy()
    df_removed = df[~mask_keep].copy()

    kept_count = len(df_kept)
    removed_count = len(df_removed)

    print(f"\nRows kept: {kept_count}")
    print(f"Rows removed: {removed_count}")

    # Generate output filename if not provided
    if output_file is None:
        stem = os.path.splitext(input_file)[0]
        output_file = f"{stem}_no_top_level.xlsx"

    # Save output with two sheets
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df_kept.to_excel(writer, sheet_name="Content Pages", index=False)
        df_removed.to_excel(writer, sheet_name="Removed Top Level", index=False)

    print(f"\nSaved to: {output_file}")
    print(f"  Sheet 'Content Pages': {kept_count} rows")
    print(f"  Sheet 'Removed Top Level': {removed_count} rows")

    return kept_count, removed_count, error_count


def main():
    parser = argparse.ArgumentParser(description="Remove top-level pages (containing 'Topic Hierarchy') from spreadsheet")
    parser.add_argument("-i", "--input", required=True, help="Input Excel file")
    parser.add_argument("-o", "--output", help="Output Excel file (default: input_no_top_level.xlsx)")
    parser.add_argument("--tag", default=TAG_TEXT, help=f"Text to search for (default: '{TAG_TEXT}')")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help=f"Concurrent threads (default: {MAX_WORKERS})")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: File not found: {args.input}")
        sys.exit(1)

    process_spreadsheet(args.input, args.output, args.tag, args.workers)


if __name__ == "__main__":
    main()
