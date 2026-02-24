"""
Media Detector - Crawls URLs and identifies media content (videos, audio, etc.)
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Configuration
INPUT_FILE = r"C:\Users\Tony.Gilpin\Downloads\2ndFeb\taxonomy_match_GB_2ndFeb_GB_cleaned_filtered_filtered_filtered.xlsx"
OUTPUT_FILE = r"C:\Users\Tony.Gilpin\Downloads\2ndFeb\media_detection_report.xlsx"
MAX_WORKERS = 10  # Concurrent requests
TIMEOUT = 15  # Request timeout in seconds

# Media detection patterns
VIDEO_PATTERNS = {
    'tags': ['video', 'iframe'],
    'src_patterns': [
        r'youtube\.com', r'youtu\.be', r'vimeo\.com', r'wistia\.com',
        r'dailymotion\.com', r'brightcove', r'vidyard', r'loom\.com',
        r'\.mp4', r'\.webm', r'\.ogg', r'\.mov', r'\.avi', r'\.wmv',
        r'player\.', r'embed', r'video'
    ],
    'class_patterns': [
        r'video', r'player', r'media-player', r'embed', r'youtube', r'vimeo'
    ]
}

AUDIO_PATTERNS = {
    'tags': ['audio'],
    'src_patterns': [
        r'\.mp3', r'\.wav', r'\.ogg', r'\.m4a', r'\.flac',
        r'soundcloud\.com', r'spotify\.com', r'podcast'
    ]
}

INTERACTIVE_PATTERNS = {
    'tags': ['canvas', 'object', 'embed'],
    'src_patterns': [
        r'\.swf', r'flash', r'interactive', r'calculator', r'tool'
    ]
}


def detect_media(url):
    """Crawl a URL and detect media content (strict mode - actual videos only)."""
    result = {
        'URL': url,
        'Status': 'Unknown',
        'Has_Video': False,
        'Has_Audio': False,
        'Has_Interactive': False,
        'Video_Sources': '',
        'Audio_Sources': '',
        'Interactive_Elements': '',
        'Video_Count': 0,
        'Audio_Count': 0,
        'Iframe_Count': 0,
        'Media_Types_Found': '',
        'Error': ''
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

        # Detect Videos (STRICT - only actual video elements)
        video_sources = []
        video_count = 0

        # Check <video> tags - this is a definite video
        for video in soup.find_all('video'):
            video_count += 1
            src = video.get('src', '')
            if src:
                video_sources.append(f'<video>:{src[:100]}')
            for source in video.find_all('source'):
                src = source.get('src', '')
                if src:
                    video_sources.append(f'<video><source>:{src[:100]}')

        # Check iframes ONLY for known video hosting platforms
        iframe_count = 0
        video_iframe_patterns = [
            r'youtube\.com/embed',
            r'youtu\.be',
            r'player\.vimeo\.com',
            r'wistia\.com/embed',
            r'fast\.wistia\.net',
            r'dailymotion\.com/embed',
            r'brightcove.*player',
            r'vidyard\.com/embed',
            r'loom\.com/embed',
            r'embed.*\.mp4',
            r'\.mp4\?',
        ]
        for iframe in soup.find_all('iframe'):
            iframe_count += 1
            src = iframe.get('src', '') or iframe.get('data-src', '')
            if src:
                for pattern in video_iframe_patterns:
                    if re.search(pattern, src, re.IGNORECASE):
                        video_count += 1
                        video_sources.append(f'<iframe>:{src[:100]}')
                        break

        # Check for data attributes that indicate actual embedded videos
        for el in soup.find_all(attrs={'data-video-id': True}):
            video_id = el.get("data-video-id", "")
            if video_id:  # Must have an actual video ID
                video_count += 1
                video_sources.append(f'data-video-id:{video_id[:50]}')

        for el in soup.find_all(attrs={'data-video-url': True}):
            video_url = el.get("data-video-url", "")
            if video_url:  # Must have an actual video URL
                video_count += 1
                video_sources.append(f'data-video-url:{video_url[:50]}')

        # Detect Audio
        audio_sources = []
        audio_count = 0

        for audio in soup.find_all('audio'):
            audio_count += 1
            src = audio.get('src', '')
            if src:
                audio_sources.append(f'audio:{src[:100]}')
            for source in audio.find_all('source'):
                src = source.get('src', '')
                if src:
                    audio_sources.append(f'source:{src[:100]}')

        # Check for podcast/audio embeds in iframes
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '') or iframe.get('data-src', '')
            if src:
                for pattern in AUDIO_PATTERNS['src_patterns']:
                    if re.search(pattern, src, re.IGNORECASE):
                        audio_count += 1
                        audio_sources.append(f'iframe:{src[:100]}')
                        break

        # Detect Interactive Elements
        interactive_elements = []

        for tag in INTERACTIVE_PATTERNS['tags']:
            elements = soup.find_all(tag)
            for el in elements:
                src = el.get('src', '') or el.get('data', '')
                interactive_elements.append(f'{tag}:{src[:50] if src else "no-src"}')

        # Compile results
        result['Has_Video'] = video_count > 0
        result['Has_Audio'] = audio_count > 0
        result['Has_Interactive'] = len(interactive_elements) > 0
        result['Video_Sources'] = ' | '.join(list(set(video_sources))[:5])
        result['Audio_Sources'] = ' | '.join(list(set(audio_sources))[:5])
        result['Interactive_Elements'] = ' | '.join(list(set(interactive_elements))[:5])
        result['Video_Count'] = video_count
        result['Audio_Count'] = audio_count
        result['Iframe_Count'] = iframe_count

        # Media types summary
        media_types = []
        if result['Has_Video']:
            media_types.append('Video')
        if result['Has_Audio']:
            media_types.append('Audio')
        if result['Has_Interactive']:
            media_types.append('Interactive')
        result['Media_Types_Found'] = ', '.join(media_types) if media_types else 'None'

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
    print(f"Media Detection Report Generator")
    print(f"=" * 50)
    print(f"Input: {INPUT_FILE}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    # Load the Excel file
    print("Loading Excel file...")
    try:
        df = pd.read_excel(INPUT_FILE)
        print(f"Loaded {len(df)} rows")
        print(f"Columns: {list(df.columns)}")
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
        print("ERROR: No 'URL' column found in the file")
        print(f"Available columns: {list(df.columns)}")
        return

    # Get unique URLs
    urls = df[url_col].dropna().unique().tolist()
    print(f"Found {len(urls)} unique URLs to crawl")
    print()

    # Crawl URLs
    results = []
    start_time = time.time()

    print(f"Crawling URLs with {MAX_WORKERS} workers...")
    print("-" * 50)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(detect_media, url): url for url in urls}

        completed = 0
        media_found = 0

        for future in as_completed(future_to_url):
            completed += 1
            result = future.result()
            results.append(result)

            if result['Has_Video'] or result['Has_Audio'] or result['Has_Interactive']:
                media_found += 1
                print(f"[{completed}/{len(urls)}] MEDIA FOUND: {result['URL'][:60]}... ({result['Media_Types_Found']})")
            elif completed % 50 == 0:
                print(f"[{completed}/{len(urls)}] Processed... ({media_found} with media)")

    elapsed = time.time() - start_time
    print()
    print(f"Crawling complete in {elapsed:.1f} seconds")
    print()

    # Create results DataFrame
    results_df = pd.DataFrame(results)

    # Create summary statistics
    summary = {
        'Metric': [
            'Total URLs Crawled',
            'Successful Requests (200)',
            'Failed Requests',
            'URLs with Video',
            'URLs with Audio',
            'URLs with Interactive Content',
            'URLs with Any Media',
            'Total Videos Detected',
            'Total Audio Files Detected',
            'Total Iframes Found',
            'Crawl Duration (seconds)'
        ],
        'Value': [
            len(results),
            len([r for r in results if r['Status'] == '200']),
            len([r for r in results if r['Status'] != '200']),
            len([r for r in results if r['Has_Video']]),
            len([r for r in results if r['Has_Audio']]),
            len([r for r in results if r['Has_Interactive']]),
            len([r for r in results if r['Has_Video'] or r['Has_Audio'] or r['Has_Interactive']]),
            sum(r['Video_Count'] for r in results),
            sum(r['Audio_Count'] for r in results),
            sum(r['Iframe_Count'] for r in results),
            round(elapsed, 1)
        ]
    }
    summary_df = pd.DataFrame(summary)

    # URLs with media only
    media_df = results_df[
        results_df['Has_Video'] | results_df['Has_Audio'] | results_df['Has_Interactive']
    ].copy()

    # Videos only
    video_df = results_df[results_df['Has_Video']].copy()

    # Failed URLs
    failed_df = results_df[results_df['Status'] != '200'].copy()

    # Write to Excel
    print(f"Writing report to {OUTPUT_FILE}...")
    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        media_df.to_excel(writer, sheet_name='URLs with Media', index=False)
        video_df.to_excel(writer, sheet_name='Videos Only', index=False)
        results_df.to_excel(writer, sheet_name='All Results', index=False)
        failed_df.to_excel(writer, sheet_name='Failed URLs', index=False)

    print()
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    for i, row in summary_df.iterrows():
        print(f"{row['Metric']}: {row['Value']}")
    print()
    print(f"Report saved to: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
