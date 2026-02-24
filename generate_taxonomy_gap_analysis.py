"""
Taxonomy Gap Analysis Report Generator
Generates a comprehensive 7-sheet Excel report analyzing taxonomy coverage gaps.

Sheets:
1. Executive Summary - Key metrics and recommendations
2. Phantom Topics - Topics appearing in matches that don't exist in taxonomy
3. Never-Matched Topics - Taxonomy topics that never matched any URL
4. Taxonomy Comparison - Compare current vs alternative taxonomy
5. Synonym Recommendations - Suggested keywords for never-matched topics
6. Product Breakdown - URL and match statistics by product
7. Action Items - Prioritized recommendations

Usage:
    python generate_taxonomy_gap_analysis.py

Configure file paths at top of script before running.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
import re
import json

# ============================================================================
# CONFIGURATION - Edit these paths before running
# ============================================================================
MATCH_FILE = r"C:\Users\Tony.Gilpin\Downloads\30thjan\taxonomy_match_GB_30thJan_GB_cleaned.xlsx"
TAXONOMY_FILE = r"C:\Users\Tony.Gilpin\Downloads\30thjan\Alternative taxonomy Ruth 30 JAN 4-04pm.xlsx"
SEMANTIC_FILE = r"C:\Users\Tony.Gilpin\Downloads\2ndFeb\userdocs.wolterskluwer.co.uk_2026-01-30T18-43-46.xlsx"
COMPARISON_TAXONOMY_FILE = r"C:\url spreasheets\vs_projects\nlmapV3\countries\GB\taxonomy.xlsx"  # Optional: for comparison
OUTPUT_FILE = "TAXONOMY_GAP_ANALYSIS_REPORT.xlsx"

# Thresholds — defaults shown; at runtime derived from THRESHOLD as threshold-20/threshold-5/threshold-15
SYNONYM_SCORE_THRESHOLD = 60  # Default (= THRESHOLD - 20); minimum fuzzy match for synonym suggestions
HIGH_PRIORITY_SCORE = 75      # Default (= THRESHOLD - 5);  score threshold for HIGH priority
MEDIUM_PRIORITY_SCORE = 65    # Default (= THRESHOLD - 15); score threshold for MEDIUM priority
MIN_KEYWORD_FREQUENCY = 3     # Minimum keyword occurrences to suggest as synonym (not threshold-derived)
THRESHOLD = 80                # Main matcher threshold — drives the three scores above
COUNTRY_CODE = ''             # Optional: tag runs for progress tracking (e.g. 'GB', 'BE')


def sanitize_dataframe(df):
    """
    Sanitize a DataFrame for Excel export by removing problematic characters.
    Fixes 'we found a problem with some content' Excel errors.
    """
    df = df.copy()

    for col in df.columns:
        # Handle all columns, not just object dtype
        df[col] = df[col].apply(lambda x: sanitize_cell_value(x))

    return df


def sanitize_cell_value(value):
    """Sanitize a single cell value for Excel compatibility."""
    # Handle None, NaN, inf
    if value is None:
        return ''
    if isinstance(value, float):
        if np.isnan(value) or np.isinf(value):
            return ''
        return value
    if isinstance(value, (int, bool)):
        return value

    s = str(value)

    # Return empty string for 'nan' or 'None' strings
    if s.lower() in ('nan', 'none', 'null', '<na>'):
        return ''

    # Remove null bytes first
    s = s.replace('\x00', '')

    # Remove ALL control characters (0x00-0x1F except tab, newline, carriage return)
    # Also remove 0x7F (DEL) and 0x80-0x9F (C1 control codes)
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', s)

    # Remove Unicode surrogate pairs (invalid in XML)
    s = re.sub(r'[\ud800-\udfff]', '', s)

    # Remove other problematic Unicode characters
    # Remove Unicode replacement character and other specials
    s = re.sub(r'[\ufffe\uffff\ufeff]', '', s)

    # Remove any remaining non-printable characters
    s = ''.join(char for char in s if char.isprintable() or char in '\t\n\r')

    # Truncate very long strings (Excel limit is 32,767 but leave margin)
    if len(s) > 32000:
        s = s[:32000] + '...'

    # Escape strings that look like formulas (start with =, +, -, @)
    # by prepending with apostrophe (Excel will display without the apostrophe)
    if s and s[0] in '=+-@':
        s = "'" + s

    return s.strip()


def _append_progress_entry(json_path, entry):
    """
    Append one run's metrics to the gap_analysis_progress.json log.
    Creates the file if missing. Silently resets on corruption.
    Returns the full history list (including this entry).
    """
    history = []
    try:
        if Path(json_path).exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                history = data
    except (json.JSONDecodeError, OSError, ValueError):
        print(f"  Warning: Progress log corrupted — starting fresh: {json_path}")
    history.append(entry)
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"  Warning: Could not write progress log: {e}")
    return history


def load_data():
    """Load all required data files."""
    print("\n[1/8] Loading data files...")

    # Load match results
    match_path = Path(MATCH_FILE)
    print(f"  Loading match file: {match_path.name}")
    try:
        df_match = pd.read_excel(match_path, sheet_name='Cleaned')
        print(f"    Loaded 'Cleaned' sheet: {len(df_match)} rows")
    except:
        df_match = pd.read_excel(match_path, sheet_name=0)
        print(f"    Loaded first sheet: {len(df_match)} rows")

    # Load taxonomy
    taxonomy_path = Path(TAXONOMY_FILE)
    print(f"  Loading taxonomy: {taxonomy_path.name}")
    df_taxonomy = pd.read_excel(taxonomy_path)
    print(f"    Loaded: {len(df_taxonomy)} rows")

    # Load semantic carriers (optional)
    df_semantic = None
    if SEMANTIC_FILE:
        semantic_path = Path(SEMANTIC_FILE)
        if semantic_path.exists():
            print(f"  Loading semantic file: {semantic_path.name}")
            df_semantic = pd.read_excel(semantic_path)
            print(f"    Loaded: {len(df_semantic)} rows")
        else:
            print(f"  Semantic file not found, skipping")

    # Load comparison taxonomy (optional)
    df_comparison = None
    if COMPARISON_TAXONOMY_FILE:
        comparison_path = Path(COMPARISON_TAXONOMY_FILE)
        if comparison_path.exists():
            print(f"  Loading comparison taxonomy: {comparison_path.name}")
            df_comparison = pd.read_excel(comparison_path)
            print(f"    Loaded: {len(df_comparison)} rows")
        else:
            print(f"  Comparison taxonomy not found, skipping")

    return df_match, df_taxonomy, df_semantic, df_comparison


def get_all_taxonomy_topics(df_taxonomy):
    """Extract all unique topics from taxonomy."""
    topic_cols = [c for c in df_taxonomy.columns if c.startswith('Topic')]
    all_topics = set()
    topic_to_product = {}
    topic_to_segment = {}

    for _, row in df_taxonomy.iterrows():
        product = row.get('Product', 'Unknown')
        segment = row.get('Segment', 'Unknown')

        for col in topic_cols:
            val = row[col]
            if pd.notna(val) and str(val).strip():
                topic = str(val).strip()
                all_topics.add(topic.lower())
                topic_to_product[topic.lower()] = product
                topic_to_segment[topic.lower()] = segment

    return all_topics, topic_to_product, topic_to_segment


def get_matched_topics(df_match):
    """Extract all topics that appeared in match results."""
    topic_cols = [c for c in df_match.columns if c.startswith('Topic_') and c != 'Topic_Frequency_Penalty']
    matched_topics = set()
    topic_match_counts = Counter()

    for _, row in df_match.iterrows():
        for col in topic_cols:
            val = row[col]
            if pd.notna(val) and str(val).strip():
                topic = str(val).strip().lower()
                matched_topics.add(topic)
                topic_match_counts[topic] += 1

    return matched_topics, topic_match_counts


def generate_executive_summary(df_match, df_taxonomy, df_semantic, never_matched_count, phantom_count):
    """Generate executive summary metrics."""
    print("\n[2/8] Generating Executive Summary...")

    total_urls = df_match['URL'].nunique()
    total_rows = len(df_match)

    # Unmapped stats
    if 'Domain' in df_match.columns:
        unmapped_urls = df_match[df_match['Domain'] == 'UNMAPPED']['URL'].nunique()
    else:
        unmapped_urls = 0

    mapped_urls = total_urls - unmapped_urls
    match_rate = round(mapped_urls / total_urls * 100, 1) if total_urls > 0 else 0

    # Taxonomy stats
    topic_cols = [c for c in df_taxonomy.columns if c.startswith('Topic')]
    total_topics = 0
    for _, row in df_taxonomy.iterrows():
        for col in topic_cols:
            if pd.notna(row[col]) and str(row[col]).strip():
                total_topics += 1

    unique_products = df_taxonomy['Product'].nunique() if 'Product' in df_taxonomy.columns else 0

    # Semantic stats
    semantic_urls = len(df_semantic) if df_semantic is not None else 'N/A'

    summary = pd.DataFrame([
        {'Metric': 'Report Generated', 'Value': datetime.now().strftime('%Y-%m-%d %H:%M')},
        {'Metric': '', 'Value': ''},
        {'Metric': '=== MATCH RESULTS ===', 'Value': ''},
        {'Metric': 'Total URLs Processed', 'Value': f'{total_urls:,}'},
        {'Metric': 'Matched URLs', 'Value': f'{mapped_urls:,}'},
        {'Metric': 'Unmapped URLs', 'Value': f'{unmapped_urls:,}'},
        {'Metric': 'Match Rate', 'Value': f'{match_rate}%'},
        {'Metric': 'Total Match Rows', 'Value': f'{total_rows:,}'},
        {'Metric': '', 'Value': ''},
        {'Metric': '=== TAXONOMY ANALYSIS ===', 'Value': ''},
        {'Metric': 'Total Taxonomy Topics', 'Value': f'{total_topics:,}'},
        {'Metric': 'Products in Taxonomy', 'Value': unique_products},
        {'Metric': 'Never-Matched Topics', 'Value': never_matched_count},
        {'Metric': 'Phantom Topics (in matches, not in taxonomy)', 'Value': phantom_count},
        {'Metric': '', 'Value': ''},
        {'Metric': '=== SOURCE DATA ===', 'Value': ''},
        {'Metric': 'Semantic Carriers URLs', 'Value': semantic_urls},
        {'Metric': 'Taxonomy File', 'Value': Path(TAXONOMY_FILE).name},
        {'Metric': 'Match File', 'Value': Path(MATCH_FILE).name},
        {'Metric': '', 'Value': ''},
        {'Metric': '=== KEY FINDINGS ===', 'Value': ''},
        {'Metric': 'Finding 1', 'Value': f'{never_matched_count} topics in taxonomy never matched any URL'},
        {'Metric': 'Finding 2', 'Value': f'{phantom_count} topics in matches not found in taxonomy'},
        {'Metric': 'Finding 3', 'Value': f'Match rate is {match_rate}% - {"Good" if match_rate >= 80 else "Needs improvement"}'},
    ])

    # Append noise-filtering note so readers know what was excluded upstream
    noise_rows = pd.DataFrame([
        {'Metric': '', 'Value': ''},
        {'Metric': '=== KEYWORD NOISE FILTERING ===', 'Value': ''},
        {'Metric': 'Note', 'Value': 'The phrases below are filtered by ContentKeywordExtractor (NOISE_PHRASE_STARTS) before keywords reach this report. Their absence from recommendations is intentional, not a gap.'},
        {'Metric': '', 'Value': ''},
        {'Metric': 'Dutch UI Chrome — BE/NL Salesforce community sites', 'Value': 'artikel vind, artikel lees, artikel legt, artikel leggen, alle artikelen, mijn artikelen, nieuw artikel, zoek artikel'},
        {'Metric': 'Why filtered', 'Value': 'Every page on the community site is an article; these Dutch nav-action phrases leak from UI chrome into every page\'s extracted text. Without filtering they generated ~614 false near-miss recommendations per run (Artikelen topic).'},
        {'Metric': '', 'Value': ''},
        {'Metric': 'English CMS Generic Language — all countries', 'Value': 'enabling, allowing, providing, ensuring, facilitating, managing, creating, updating, configuring, displaying, showing, accessing, visiting, starting, guidance on, effectively, automatically, properly, correctly'},
        {'Metric': 'Why filtered', 'Value': 'Gerund-form phrases that describe page actions rather than taxonomy topics. Appear across all CMS help sites and pollute synonym recommendations.'},
        {'Metric': '', 'Value': ''},
        {'Metric': 'To add new noise phrases', 'Value': 'Use the Noise Phrases Editor tab in the GUI, or edit countries/{CC}/noise_phrases.json directly. Uses prefix matching — shortest unambiguous prefix covers the whole noise family.'},
    ])
    summary = pd.concat([summary, noise_rows], ignore_index=True)

    print(f"  Match rate: {match_rate}%")
    print(f"  Never-matched topics: {never_matched_count}")
    print(f"  Phantom topics: {phantom_count}")

    return summary


def generate_phantom_topics(df_match, all_taxonomy_topics, topic_match_counts):
    """Find topics in match results that don't exist in taxonomy."""
    print("\n[3/8] Identifying Phantom Topics...")

    matched_topics, _ = get_matched_topics(df_match)

    phantom_topics = []
    for topic in matched_topics:
        if topic not in all_taxonomy_topics:
            count = topic_match_counts.get(topic, 0)
            phantom_topics.append({
                'Topic': topic.title(),
                'Match_Count': count,
                'Issue': 'Topic appears in matches but not in taxonomy',
                'Recommendation': 'Add to taxonomy or investigate source'
            })

    df_phantom = pd.DataFrame(phantom_topics)
    if not df_phantom.empty:
        df_phantom = df_phantom.sort_values('Match_Count', ascending=False)

    print(f"  Found {len(df_phantom)} phantom topics")

    return df_phantom


def generate_never_matched_topics(df_match, df_taxonomy, all_taxonomy_topics, topic_to_product, topic_to_segment):
    """Find taxonomy topics that never matched any URL."""
    print("\n[4/8] Identifying Never-Matched Topics...")

    matched_topics, topic_match_counts = get_matched_topics(df_match)

    never_matched = []
    for topic in all_taxonomy_topics:
        if topic not in matched_topics:
            never_matched.append({
                'Topic': topic.title(),
                'Product': topic_to_product.get(topic, 'Unknown'),
                'Segment': topic_to_segment.get(topic, 'Unknown'),
                'Status': 'Never matched',
                'Recommendation': 'Review topic relevance or add synonyms'
            })

    df_never_matched = pd.DataFrame(never_matched)
    if not df_never_matched.empty:
        df_never_matched = df_never_matched.sort_values(['Product', 'Segment', 'Topic'])

    print(f"  Found {len(df_never_matched)} never-matched topics")

    return df_never_matched


def generate_taxonomy_comparison(df_taxonomy, df_comparison):
    """Compare two taxonomies."""
    print("\n[5/8] Generating Taxonomy Comparison...")

    if df_comparison is None:
        print("  No comparison taxonomy provided, skipping")
        return pd.DataFrame([{
            'Message': 'No comparison taxonomy file configured',
            'Action': 'Set COMPARISON_TAXONOMY_FILE path to enable comparison'
        }])

    # Get topics from each taxonomy
    def get_topics(df):
        topic_cols = [c for c in df.columns if c.startswith('Topic')]
        topics = set()
        for _, row in df.iterrows():
            for col in topic_cols:
                if pd.notna(row[col]) and str(row[col]).strip():
                    topics.add(str(row[col]).strip().lower())
        return topics

    topics_current = get_topics(df_taxonomy)
    topics_comparison = get_topics(df_comparison)

    only_in_current = topics_current - topics_comparison
    only_in_comparison = topics_comparison - topics_current
    in_both = topics_current & topics_comparison

    comparison_data = []

    # Summary stats
    comparison_data.append({
        'Aspect': 'Total Rows',
        'Current_Taxonomy': len(df_taxonomy),
        'Comparison_Taxonomy': len(df_comparison),
        'Difference': len(df_taxonomy) - len(df_comparison)
    })
    comparison_data.append({
        'Aspect': 'Unique Topics',
        'Current_Taxonomy': len(topics_current),
        'Comparison_Taxonomy': len(topics_comparison),
        'Difference': len(topics_current) - len(topics_comparison)
    })
    comparison_data.append({
        'Aspect': 'Topics in Both',
        'Current_Taxonomy': len(in_both),
        'Comparison_Taxonomy': len(in_both),
        'Difference': 0
    })
    comparison_data.append({
        'Aspect': 'Unique to Current',
        'Current_Taxonomy': len(only_in_current),
        'Comparison_Taxonomy': 0,
        'Difference': len(only_in_current)
    })
    comparison_data.append({
        'Aspect': 'Unique to Comparison',
        'Current_Taxonomy': 0,
        'Comparison_Taxonomy': len(only_in_comparison),
        'Difference': -len(only_in_comparison)
    })

    # Add product counts
    if 'Product' in df_taxonomy.columns and 'Product' in df_comparison.columns:
        comparison_data.append({
            'Aspect': 'Products',
            'Current_Taxonomy': df_taxonomy['Product'].nunique(),
            'Comparison_Taxonomy': df_comparison['Product'].nunique(),
            'Difference': df_taxonomy['Product'].nunique() - df_comparison['Product'].nunique()
        })

    print(f"  Current taxonomy: {len(topics_current)} topics")
    print(f"  Comparison taxonomy: {len(topics_comparison)} topics")
    print(f"  Topics only in current: {len(only_in_current)}")
    print(f"  Topics only in comparison: {len(only_in_comparison)}")

    return pd.DataFrame(comparison_data)


def generate_synonym_recommendations(df_match, df_semantic, df_taxonomy, all_taxonomy_topics, topic_to_product, threshold=80):
    """Generate synonym recommendations for never-matched topics."""
    print("\n[6/8] Generating Synonym Recommendations...")
    # Derive thresholds relative to main matcher threshold (mirrors taxonomy_matcher.py logic)
    _syn_score_threshold = max(50, threshold - 20)
    _high_threshold = threshold - 5
    _med_threshold = threshold - 15

    from rapidfuzz import fuzz

    # Get matched and never-matched topics
    matched_topics, _ = get_matched_topics(df_match)
    never_matched_topics = all_taxonomy_topics - matched_topics

    if not never_matched_topics:
        print("  No never-matched topics found")
        return pd.DataFrame([{'Message': 'All taxonomy topics have matches'}])

    # Extract keywords from semantic file WITH URL tracking
    keyword_counts = Counter()
    keyword_urls = defaultdict(list)  # Track URLs for each keyword

    if df_semantic is not None:
        keyword_cols = [c for c in df_semantic.columns if 'keyword' in c.lower()]
        url_col = 'URL' if 'URL' in df_semantic.columns else df_semantic.columns[0]

        for _, row in df_semantic.iterrows():
            url = str(row.get(url_col, ''))
            for col in keyword_cols:
                val = row[col]
                if pd.notna(val) and str(val).strip():
                    kw = str(val).strip().lower()
                    keyword_counts[kw] += 1
                    # Store up to 5 sample URLs per keyword
                    if len(keyword_urls[kw]) < 5:
                        keyword_urls[kw].append(url)
    else:
        # Fall back to keywords from match file if no semantic file
        print("  No semantic file, extracting keywords from match data...")
        # This is a simplified fallback

    print(f"  Found {len(keyword_counts)} unique keywords")
    print(f"  Analyzing {len(never_matched_topics)} never-matched topics...")

    recommendations = []

    for topic in never_matched_topics:
        topic_title = topic.title()
        suggested_keywords = []

        # Find keywords that fuzzy match this topic
        for kw, freq in keyword_counts.most_common():
            if freq < MIN_KEYWORD_FREQUENCY:
                continue

            score = fuzz.ratio(topic, kw)
            partial_score = fuzz.partial_ratio(topic, kw)
            best_score = max(score, partial_score)

            if best_score >= _syn_score_threshold:
                # Include URLs for this keyword
                urls = keyword_urls.get(kw, [])
                suggested_keywords.append((kw, freq, best_score, urls))

        # Sort by score descending
        suggested_keywords.sort(key=lambda x: (-x[2], -x[1]))

        if suggested_keywords:
            # Format suggested keywords with frequencies
            kw_str = ', '.join([f"{kw} ({freq})" for kw, freq, score, urls in suggested_keywords[:5]])
            best_score = suggested_keywords[0][2]

            # Collect sample URLs from top suggested keywords
            sample_urls = []
            for kw, freq, score, urls in suggested_keywords[:5]:
                sample_urls.extend(urls[:2])  # Take up to 2 URLs per keyword
            # Remove duplicates while preserving order
            seen = set()
            unique_urls = []
            for u in sample_urls:
                if u not in seen:
                    seen.add(u)
                    unique_urls.append(u)
            # Keep up to 5 full URLs
            unique_urls = unique_urls[:5]

            # Determine priority (relative to main matcher threshold)
            if best_score >= _high_threshold:
                priority = 'HIGH'
            elif best_score >= _med_threshold:
                priority = 'MEDIUM'
            else:
                priority = 'LOW'

            rec = {
                'Taxonomy_Topic': topic_title,
                'Status': 'In taxonomy - never matched',
                'Suggested_Synonyms': kw_str,
                'Priority': priority,
                'Best_Match_Score': best_score,
                'Product': topic_to_product.get(topic, 'Unknown'),
            }
            # Add up to 5 sample URLs as separate columns (clickable in Excel)
            for i, url in enumerate(unique_urls, start=1):
                rec[f'Sample_URL_{i}'] = url
            # Fill remaining URL columns with empty string
            for i in range(len(unique_urls) + 1, 6):
                rec[f'Sample_URL_{i}'] = ''
            recommendations.append(rec)

    df_recs = pd.DataFrame(recommendations)
    if not df_recs.empty:
        # Sort by priority then best score
        priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        df_recs['_priority_order'] = df_recs['Priority'].map(priority_order)
        df_recs = df_recs.sort_values(['_priority_order', 'Best_Match_Score'], ascending=[True, False])
        df_recs = df_recs.drop('_priority_order', axis=1)

    high_count = len(df_recs[df_recs['Priority'] == 'HIGH']) if not df_recs.empty else 0
    print(f"  Generated {len(df_recs)} synonym recommendations ({high_count} HIGH priority)")

    return df_recs


def generate_product_breakdown(df_match, df_taxonomy):
    """Generate URL and match statistics by product."""
    print("\n[7/8] Generating Product Breakdown...")

    product_stats = []

    # Get taxonomy topic counts per product
    topic_cols = [c for c in df_taxonomy.columns if c.startswith('Topic')]
    taxonomy_topics_by_product = {}

    for _, row in df_taxonomy.iterrows():
        product = row.get('Product', 'Unknown')
        if pd.isna(product):
            continue

        if product not in taxonomy_topics_by_product:
            taxonomy_topics_by_product[product] = 0

        for col in topic_cols:
            if pd.notna(row[col]) and str(row[col]).strip():
                taxonomy_topics_by_product[product] += 1

    # Analyze match data by product
    total_urls = df_match['URL'].nunique()

    for product in df_match['Product'].unique():
        if pd.isna(product):
            continue

        product_data = df_match[df_match['Product'] == product]
        unique_urls = product_data['URL'].nunique()
        total_rows = len(product_data)

        # Count unmapped
        unmapped = len(product_data[product_data['Domain'] == 'UNMAPPED']) if 'Domain' in product_data.columns else 0
        mapped = total_rows - unmapped
        match_rate = round(mapped / total_rows * 100, 1) if total_rows > 0 else 0

        taxonomy_topics = taxonomy_topics_by_product.get(product, 0)
        url_to_topic_ratio = round(unique_urls / taxonomy_topics, 1) if taxonomy_topics > 0 else 'N/A'

        product_stats.append({
            'Product': product,
            'Unique_URLs': unique_urls,
            'Total_Rows': total_rows,
            'Mapped_Rows': mapped,
            'Unmapped_Rows': unmapped,
            'Match_Rate': f'{match_rate}%',
            'Taxonomy_Topics': taxonomy_topics,
            'URL_to_Topic_Ratio': url_to_topic_ratio,
            'Pct_of_Total_URLs': f'{round(unique_urls / total_urls * 100, 1)}%'
        })

    df_products = pd.DataFrame(product_stats)
    if not df_products.empty:
        df_products = df_products.sort_values('Unique_URLs', ascending=False)

    print(f"  Analyzed {len(df_products)} products")

    return df_products


def generate_action_items(df_phantom, df_never_matched, df_synonym_recs, df_products):
    """Generate prioritized action items."""
    print("\n[8/8] Generating Action Items...")

    actions = []
    action_id = 1

    # Action 1: Fix phantom topics (HIGH priority)
    if not df_phantom.empty and len(df_phantom) > 0:
        phantom_count = len(df_phantom)
        top_phantoms = df_phantom.head(5)['Topic'].tolist() if len(df_phantom) > 0 else []
        actions.append({
            'ID': action_id,
            'Priority': 'P1-CRITICAL',
            'Category': 'Data Quality',
            'Action': f'Investigate {phantom_count} phantom topics appearing in matches but not in taxonomy',
            'Details': f'Top examples: {", ".join(top_phantoms[:3])}',
            'Impact': f'{phantom_count} topics need review',
            'Effort': 'Medium'
        })
        action_id += 1

    # Action 2: Add synonyms for high-priority never-matched topics
    if not df_synonym_recs.empty and 'Priority' in df_synonym_recs.columns:
        high_priority = df_synonym_recs[df_synonym_recs['Priority'] == 'HIGH']
        if len(high_priority) > 0:
            actions.append({
                'ID': action_id,
                'Priority': 'P1-HIGH',
                'Category': 'Synonym Enhancement',
                'Action': f'Add synonyms for {len(high_priority)} HIGH-priority never-matched topics',
                'Details': 'These topics have strong keyword matches but no synonyms configured',
                'Impact': f'Could improve matching for {len(high_priority)} taxonomy topics',
                'Effort': 'Low'
            })
            action_id += 1

    # Action 3: Review never-matched topics
    if not df_never_matched.empty:
        never_matched_count = len(df_never_matched)
        if never_matched_count > 10:
            actions.append({
                'ID': action_id,
                'Priority': 'P2-MEDIUM',
                'Category': 'Taxonomy Review',
                'Action': f'Review {never_matched_count} never-matched topics for relevance',
                'Details': 'Topics in taxonomy that never matched any URL may be obsolete or need synonyms',
                'Impact': 'Cleaner taxonomy, better coverage',
                'Effort': 'Medium'
            })
            action_id += 1

    # Action 4: Products with poor URL:Topic ratio
    if not df_products.empty and 'URL_to_Topic_Ratio' in df_products.columns:
        # Find products with high ratio (more than 20:1)
        high_ratio_products = []
        for _, row in df_products.iterrows():
            ratio = row['URL_to_Topic_Ratio']
            if ratio != 'N/A' and float(ratio) > 20:
                high_ratio_products.append(row['Product'])

        if high_ratio_products:
            actions.append({
                'ID': action_id,
                'Priority': 'P2-MEDIUM',
                'Category': 'Coverage Gap',
                'Action': f'Add topics for {len(high_ratio_products)} products with poor URL:Topic ratio',
                'Details': f'Products: {", ".join(high_ratio_products[:3])}{"..." if len(high_ratio_products) > 3 else ""}',
                'Impact': 'Better topic coverage for under-served products',
                'Effort': 'High'
            })
            action_id += 1

    # Action 5: Medium priority synonyms
    if not df_synonym_recs.empty and 'Priority' in df_synonym_recs.columns:
        medium_priority = df_synonym_recs[df_synonym_recs['Priority'] == 'MEDIUM']
        if len(medium_priority) > 0:
            actions.append({
                'ID': action_id,
                'Priority': 'P3-LOW',
                'Category': 'Synonym Enhancement',
                'Action': f'Review {len(medium_priority)} MEDIUM-priority synonym suggestions',
                'Details': 'Lower confidence matches that may still be valuable',
                'Impact': 'Incremental matching improvement',
                'Effort': 'Low'
            })
            action_id += 1

    if not actions:
        actions.append({
            'ID': 1,
            'Priority': 'P3-LOW',
            'Category': 'General',
            'Action': 'No critical issues found',
            'Details': 'Taxonomy appears to be in good shape',
            'Impact': 'N/A',
            'Effort': 'N/A'
        })

    print(f"  Generated {len(actions)} action items")

    return pd.DataFrame(actions)


def apply_excel_formatting(writer):
    """Apply formatting to all sheets."""
    try:
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        header_font = Font(bold=True, color='FFFFFF')
        p1_fill = PatternFill(start_color='FF6B6B', end_color='FF6B6B', fill_type='solid')
        p2_fill = PatternFill(start_color='FFB347', end_color='FFB347', fill_type='solid')
        high_fill = PatternFill(start_color='FF9999', end_color='FF9999', fill_type='solid')
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]

            # Format header row
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                cell.border = thin_border

            # Auto-adjust column widths
            for column in ws.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = min(len(str(cell.value)), 60)
                    except:
                        pass
                ws.column_dimensions[column_letter].width = max_length + 2

            # Apply conditional formatting for priority cells
            for row in ws.iter_rows(min_row=2):
                for cell in row:
                    cell.border = thin_border

                    if cell.value:
                        val = str(cell.value)
                        if 'P1' in val or 'CRITICAL' in val:
                            cell.fill = p1_fill
                        elif 'P2' in val or 'HIGH' == val:
                            cell.fill = p2_fill
                        elif val == 'HIGH':
                            cell.fill = high_fill

        print("  Applied Excel formatting")

    except Exception as e:
        print(f"  Warning: Could not apply formatting: {e}")


def main():
    """Main execution function."""
    print("=" * 70)
    print("TAXONOMY GAP ANALYSIS REPORT GENERATOR")
    print("=" * 70)

    # Load data
    df_match, df_taxonomy, df_semantic, df_comparison = load_data()

    # Get taxonomy topics
    all_taxonomy_topics, topic_to_product, topic_to_segment = get_all_taxonomy_topics(df_taxonomy)
    matched_topics, topic_match_counts = get_matched_topics(df_match)

    # Generate all sheets
    df_phantom = generate_phantom_topics(df_match, all_taxonomy_topics, topic_match_counts)
    df_never_matched = generate_never_matched_topics(df_match, df_taxonomy, all_taxonomy_topics, topic_to_product, topic_to_segment)
    df_comparison_sheet = generate_taxonomy_comparison(df_taxonomy, df_comparison)
    df_synonym_recs = generate_synonym_recommendations(df_match, df_semantic, df_taxonomy, all_taxonomy_topics, topic_to_product, threshold=THRESHOLD)
    df_products = generate_product_breakdown(df_match, df_taxonomy)
    df_actions = generate_action_items(df_phantom, df_never_matched, df_synonym_recs, df_products)

    # Generate executive summary (needs counts from above)
    df_summary = generate_executive_summary(
        df_match, df_taxonomy, df_semantic,
        never_matched_count=len(df_never_matched),
        phantom_count=len(df_phantom)
    )

    # === PROGRESS TRACKING ===
    print("\n[8/8] Updating progress log...")
    total_urls = df_match['URL'].nunique()
    unmapped_urls = df_match[df_match['Domain'] == 'UNMAPPED']['URL'].nunique() if 'Domain' in df_match.columns else 0
    match_rate = round((total_urls - unmapped_urls) / total_urls * 100, 1) if total_urls > 0 else 0
    all_taxonomy_topics_set, _, _ = get_all_taxonomy_topics(df_taxonomy)
    matched_topics_set, _ = get_matched_topics(df_match)

    progress_entry = {
        'run_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'country_code': COUNTRY_CODE,
        'match_rate_pct': match_rate,
        'total_urls': int(total_urls),
        'mapped_urls': int(total_urls - unmapped_urls),
        'unmapped_urls': int(unmapped_urls),
        'never_matched_topics_count': len(df_never_matched),
        'phantom_topics_count': len(df_phantom),
        'total_taxonomy_topics': len(all_taxonomy_topics_set),
        'threshold_used': THRESHOLD,
    }
    json_path = Path(__file__).parent / 'gap_analysis_progress.json'
    progress_history = _append_progress_entry(json_path, progress_entry)
    print(f"  Progress log updated: {len(progress_history)} total runs recorded")

    _progress_cols = ['run_datetime', 'country_code', 'match_rate_pct', 'total_urls',
                      'mapped_urls', 'unmapped_urls', 'never_matched_topics_count',
                      'phantom_topics_count', 'total_taxonomy_topics', 'threshold_used']
    df_progress = pd.DataFrame(progress_history).reindex(columns=_progress_cols)

    # Write to Excel
    output_path = Path(__file__).parent / OUTPUT_FILE
    print(f"\nWriting report to: {output_path}")

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        sanitize_dataframe(df_summary).to_excel(writer, sheet_name='Executive Summary', index=False)
        sanitize_dataframe(df_phantom).to_excel(writer, sheet_name='Phantom Topics', index=False)
        sanitize_dataframe(df_never_matched).to_excel(writer, sheet_name='Never-Matched Topics', index=False)
        sanitize_dataframe(df_comparison_sheet).to_excel(writer, sheet_name='Taxonomy Comparison', index=False)
        sanitize_dataframe(df_synonym_recs).to_excel(writer, sheet_name='Synonym Recommendations', index=False)
        sanitize_dataframe(df_products).to_excel(writer, sheet_name='Product Breakdown', index=False)
        sanitize_dataframe(df_actions).to_excel(writer, sheet_name='Action Items', index=False)
        sanitize_dataframe(df_progress).to_excel(writer, sheet_name='Progress', index=False)

        apply_excel_formatting(writer)

    print("\n" + "=" * 70)
    print("REPORT GENERATED SUCCESSFULLY!")
    print(f"Output: {output_path}")
    print("=" * 70)

    # Print summary
    print("\nSHEET SUMMARY:")
    print(f"  1. Executive Summary - Key metrics")
    print(f"  2. Phantom Topics - {len(df_phantom)} topics in matches not in taxonomy")
    print(f"  3. Never-Matched Topics - {len(df_never_matched)} taxonomy topics with no matches")
    print(f"  4. Taxonomy Comparison - Current vs comparison taxonomy")
    print(f"  5. Synonym Recommendations - {len(df_synonym_recs)} suggestions")
    print(f"  6. Product Breakdown - {len(df_products)} products analyzed")
    print(f"  7. Action Items - {len(df_actions)} prioritized actions")
    print(f"  8. Progress - {len(progress_history)} runs tracked ({match_rate}% match rate this run)")


if __name__ == '__main__':
    main()
