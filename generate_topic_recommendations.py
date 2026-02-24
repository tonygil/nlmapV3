"""
Generate Topic Recommendations Excel Report
Creates a comprehensive 6-sheet Excel workbook with topic recommendations
based on match analysis and taxonomy gap identification.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import Counter
import re

# Configuration
MATCH_FILE = r"C:\Users\Tony.Gilpin\Downloads\30thjan\taxonomy_match_GB_booster_30JAN_cleaned_3-53pm.xlsx"
TAXONOMY_FILE = r"C:\Users\Tony.Gilpin\Downloads\30thjan\Alternative taxonomy Ruth 30 JAN 4-04pm.xlsx"
OUTPUT_FILE = "TOPIC_RECOMMENDATIONS_30thJan.xlsx"

# Optional: Additional document source for discovering new topics
DOCUMENT_SOURCE_FILE = r"C:\Users\Tony.Gilpin\Downloads\userdocs.wolterskluwer.co.uk_2026-01-29T17-32-39.xlsx"

# Priority thresholds
CRITICAL_RATIO = 50  # URL:Topic ratio above this is critical
HIGH_RATIO = 30      # URL:Topic ratio above this is high priority


def sanitize_dataframe(df):
    """
    Sanitize a DataFrame for Excel export by removing problematic characters.
    Fixes 'we found a problem with some content' Excel errors.
    """
    df = df.copy()

    for col in df.columns:
        if df[col].dtype == 'object':
            # Convert to string and handle NaN
            df[col] = df[col].apply(lambda x: sanitize_cell_value(x) if pd.notna(x) else '')

    return df


def sanitize_cell_value(value):
    """
    Sanitize a single cell value for Excel compatibility.
    """
    if value is None:
        return ''

    # Convert to string
    s = str(value)

    # Remove control characters (except tab, newline, carriage return)
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', s)

    # Remove null bytes
    s = s.replace('\x00', '')

    # Truncate very long strings (Excel cell limit is ~32767 chars)
    if len(s) > 32000:
        s = s[:32000] + '...'

    # Replace problematic Unicode characters
    # Remove characters in the surrogate pair range
    s = re.sub(r'[\ud800-\udfff]', '', s)

    # Prevent Excel formula interpretation — values starting with these
    # characters are treated as formulas and cause "found a problem" errors
    s = s.strip()
    if s and s[0] in ('=', '+', '@', '{'):
        s = "'" + s

    return s


def load_data():
    """Load the match results and taxonomy files."""
    base_path = Path(__file__).parent

    # Try to load the cleaned match file (can be absolute or relative path)
    match_path = Path(MATCH_FILE) if Path(MATCH_FILE).is_absolute() else base_path / MATCH_FILE
    if not match_path.exists():
        # Fall back to the regular match file
        match_path = base_path / "taxonomy_match_GB.xlsx"

    print(f"Loading match data from: {match_path}")

    # Read match data - try Cleaned sheet first, then fall back to first sheet
    try:
        df_match = pd.read_excel(match_path, sheet_name='Cleaned')
        print(f"Loaded 'Cleaned' sheet")
    except:
        df_match = pd.read_excel(match_path, sheet_name=0)
        print(f"Loaded first sheet")

    print(f"Match data shape: {df_match.shape}")
    print(f"Columns: {list(df_match.columns)}")

    # Load taxonomy (can be absolute or relative path)
    taxonomy_path = Path(TAXONOMY_FILE) if Path(TAXONOMY_FILE).is_absolute() else base_path / TAXONOMY_FILE
    print(f"\nLoading taxonomy from: {taxonomy_path}")
    df_taxonomy = pd.read_excel(taxonomy_path)
    print(f"Taxonomy shape: {df_taxonomy.shape}")
    print(f"Columns: {list(df_taxonomy.columns)}")

    return df_match, df_taxonomy


def analyze_data_quality(df_taxonomy, df_match=None):
    """Identify data quality issues in taxonomy."""
    issues = []

    # Get topic columns
    topic_cols = [c for c in df_taxonomy.columns if c.startswith('Topic')]

    # Build topic frequency from match data if available
    topic_counts = Counter()
    if df_match is not None:
        match_topic_cols = [c for c in df_match.columns if c.startswith('Topic_')]
        for col in match_topic_cols:
            for topic in df_match[col].dropna():
                if topic and str(topic).strip():
                    topic_counts[str(topic).strip().lower()] += 1

    for idx, row in df_taxonomy.iterrows():
        row_num = idx + 2  # Excel rows are 1-indexed plus header
        product = row.get('Product', 'Unknown')

        for col in topic_cols:
            value = str(row[col]) if pd.notna(row[col]) else ""

            if not value.strip():
                continue

            # Check for reference errors
            if 'see row' in value.lower() or 'see topic' in value.lower():
                # Try to estimate URLs affected
                urls_affected = 50  # Estimate
                issues.append({
                    'Issue_Type': 'Reference Error',
                    'Location': f'Row {row_num}, {col}',
                    'Product': product,
                    'Current_Value': value,
                    'Recommended_Fix': 'Replace with actual topic name',
                    'URLs_Affected': urls_affected,
                    'Priority': 'P1-CRITICAL',
                    'Reason': 'Broken reference - no valid topic for matching'
                })

            # Check for typos (common patterns)
            typo_patterns = [
                ('Suporting', 'Supporting'),
                ('Worfklow', 'Workflow'),
                ('Worfkow', 'Workflow'),
                ('Managment', 'Management'),
                ('Documnet', 'Document'),
                ('Accoutning', 'Accounting'),
                ('Compiance', 'Compliance'),
                ('Analsis', 'Analysis'),
                ('Reportng', 'Reporting'),
                ('Intergration', 'Integration'),
            ]

            for typo, correct in typo_patterns:
                if typo.lower() in value.lower():
                    urls_affected = topic_counts.get(value.lower(), 20)
                    issues.append({
                        'Issue_Type': 'Typo',
                        'Location': f'Row {row_num}, {col}',
                        'Product': product,
                        'Current_Value': value,
                        'Recommended_Fix': value.replace(typo, correct).replace(typo.lower(), correct.lower()),
                        'URLs_Affected': urls_affected,
                        'Priority': 'P1-HIGH',
                        'Reason': 'Misspelling affects matching accuracy'
                    })

            # Check for trailing spaces
            if value and value != value.strip():
                urls_affected = topic_counts.get(value.strip().lower(), 15)
                issues.append({
                    'Issue_Type': 'Trailing/Leading Spaces',
                    'Location': f'Row {row_num}, {col}',
                    'Product': product,
                    'Current_Value': f'"{value}"',
                    'Recommended_Fix': value.strip(),
                    'URLs_Affected': urls_affected,
                    'Priority': 'P1-HIGH',
                    'Reason': 'Extra spaces cause matching issues'
                })

            # Check for duplicate topics within same row
            row_topics = [str(row[c]).strip().lower() for c in topic_cols if pd.notna(row[c]) and str(row[c]).strip()]
            if row_topics.count(value.strip().lower()) > 1:
                issues.append({
                    'Issue_Type': 'Duplicate Topic',
                    'Location': f'Row {row_num}, {col}',
                    'Product': product,
                    'Current_Value': value,
                    'Recommended_Fix': 'Remove duplicate or replace with different topic',
                    'URLs_Affected': 0,
                    'Priority': 'P2-MEDIUM',
                    'Reason': 'Duplicate topic wastes taxonomy capacity'
                })

    # Remove duplicates
    seen = set()
    unique_issues = []
    for issue in issues:
        key = (issue['Issue_Type'], issue['Location'], issue['Current_Value'])
        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)

    return pd.DataFrame(unique_issues) if unique_issues else pd.DataFrame(columns=[
        'Issue_Type', 'Location', 'Product', 'Current_Value', 'Recommended_Fix',
        'URLs_Affected', 'Priority', 'Reason'
    ])


def analyze_product_gaps(df_match, df_taxonomy):
    """Analyze gaps in topic coverage per product."""

    # Count unique URLs and topics per product
    product_stats = []

    # Get topic columns from taxonomy
    topic_cols = [c for c in df_taxonomy.columns if c.startswith('Topic')]

    # Count unique topics per product in taxonomy (excluding empty and reference errors)
    taxonomy_topic_counts = {}
    taxonomy_topics_list = {}
    for _, row in df_taxonomy.iterrows():
        product = row.get('Product', 'Unknown')
        if pd.isna(product):
            continue

        # Count valid topics (not empty, not references)
        valid_topics = []
        for col in topic_cols:
            val = str(row[col]) if pd.notna(row[col]) else ""
            val = val.strip()
            if val and 'see row' not in val.lower() and 'see topic' not in val.lower():
                valid_topics.append(val)

        if product not in taxonomy_topic_counts:
            taxonomy_topic_counts[product] = set()
        taxonomy_topic_counts[product].update(valid_topics)

        if product not in taxonomy_topics_list:
            taxonomy_topics_list[product] = []
        taxonomy_topics_list[product].extend(valid_topics)

    # Convert sets to counts
    for product in taxonomy_topic_counts:
        taxonomy_topic_counts[product] = len(taxonomy_topic_counts[product])

    # Analyze match data
    for product in df_match['Product'].unique():
        if pd.isna(product):
            continue

        product_data = df_match[df_match['Product'] == product]
        unique_urls = product_data['URL'].nunique()

        # Get topic count from taxonomy
        current_topics = taxonomy_topic_counts.get(product, 0)
        if current_topics == 0:
            current_topics = 1  # Avoid division by zero

        ratio = unique_urls / current_topics

        # Determine gap level with more specific thresholds
        if ratio >= CRITICAL_RATIO:
            gap_level = 'CRITICAL'
            priority = 'P1'
            # Recommend topics to get ratio down to ~10:1
            low = max(int(unique_urls / 12) - current_topics, 5)
            high = max(int(unique_urls / 8) - current_topics, low + 5)
            topics_needed = f'{low}-{high}'
        elif ratio >= HIGH_RATIO:
            gap_level = 'HIGH'
            priority = 'P1' if ratio >= 40 else 'P2'
            low = max(int(unique_urls / 15) - current_topics, 3)
            high = max(int(unique_urls / 10) - current_topics, low + 5)
            topics_needed = f'{low}-{high}'
        elif ratio >= 20:
            gap_level = 'MEDIUM'
            priority = 'P2'
            low = max(int(unique_urls / 20) - current_topics, 2)
            high = max(int(unique_urls / 15) - current_topics, low + 3)
            topics_needed = f'{low}-{high}'
        elif ratio >= 10:
            gap_level = 'LOW'
            priority = 'P3'
            topics_needed = '0-3'
        else:
            gap_level = 'OK'
            priority = 'P3'
            topics_needed = '0'

        # Build detailed reason
        if gap_level == 'CRITICAL':
            reason = f'Severe under-coverage: only {current_topics} topics for {unique_urls} URLs'
        elif gap_level == 'HIGH':
            reason = f'Major product with insufficient topics ({current_topics} for {unique_urls} URLs)'
        elif gap_level == 'MEDIUM':
            reason = f'Could benefit from more topics to improve coverage'
        else:
            reason = 'Adequate topic coverage'

        product_stats.append({
            'Product': product,
            'Unique_URLs': unique_urls,
            'Current_Topics': current_topics,
            'URL_to_Topic_Ratio': f'{ratio:.1f}:1',
            'Gap_Level': gap_level,
            'Topics_Needed': topics_needed,
            'Priority': priority,
            'Reason': reason
        })

    df_gaps = pd.DataFrame(product_stats)

    # Sort by gap level then ratio
    gap_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3, 'OK': 4}
    df_gaps['_gap_order'] = df_gaps['Gap_Level'].map(gap_order)
    df_gaps = df_gaps.sort_values(['_gap_order', 'Unique_URLs'], ascending=[True, False])
    df_gaps = df_gaps.drop('_gap_order', axis=1)

    return df_gaps


def generate_topic_recommendations(df_match, df_taxonomy):
    """Generate specific topic recommendations based on keyword analysis."""
    recommendations = []

    # Get topic columns from match data (exclude Topic_Frequency_Penalty which is boolean)
    topic_cols = [c for c in df_match.columns if c.startswith('Topic_') and c != 'Topic_Frequency_Penalty']

    # Build a set of existing taxonomy topics per product
    taxonomy_topic_cols = [c for c in df_taxonomy.columns if c.startswith('Topic')]
    existing_topics_by_product = {}

    # Also build a set of "shared" topics from General domain (applies to all products)
    shared_topics = set()

    # Build a set of ALL topics across entire taxonomy (for "Existing (Other)" check)
    all_taxonomy_topics = set()

    # Track which product each topic belongs to
    topic_to_products = {}

    for _, row in df_taxonomy.iterrows():
        product = row.get('Product', 'Unknown')
        domain = str(row.get('Domain', '')).strip().lower() if pd.notna(row.get('Domain')) else ''

        if pd.isna(product):
            continue

        if product not in existing_topics_by_product:
            existing_topics_by_product[product] = set()

        for col in taxonomy_topic_cols:
            val = str(row[col]) if pd.notna(row[col]) else ""
            if val.strip():
                topic_lower = val.strip().lower()
                existing_topics_by_product[product].add(topic_lower)
                all_taxonomy_topics.add(topic_lower)

                # Track which products have this topic
                if topic_lower not in topic_to_products:
                    topic_to_products[topic_lower] = []
                if product not in topic_to_products[topic_lower]:
                    topic_to_products[topic_lower].append(product)

                # Topics in "General" domain are shared across all products
                if domain == 'general':
                    shared_topics.add(topic_lower)

    print(f"  Found {len(shared_topics)} shared topics in General domain")
    print(f"  Found {len(all_taxonomy_topics)} total unique topics in taxonomy")

    # For each product, analyze what topics are matching
    for product in df_match['Product'].unique():
        if pd.isna(product):
            continue

        product_data = df_match[df_match['Product'] == product]
        total_urls = product_data['URL'].nunique()

        # Count topic occurrences and track sample URLs
        topic_counts = Counter()
        topic_urls = {}
        for _, row in product_data.iterrows():
            url = row.get('URL', '')
            for col in topic_cols:
                topic = row[col]
                if pd.notna(topic) and str(topic).strip():
                    topic_str = str(topic).strip()
                    topic_counts[topic_str] += 1
                    if topic_str not in topic_urls:
                        topic_urls[topic_str] = []
                    if len(topic_urls[topic_str]) < 3:
                        topic_urls[topic_str].append(url)

        # Get existing topics for this product
        existing = existing_topics_by_product.get(product, set())

        # Get the most common topics for this product
        for topic, count in topic_counts.most_common(25):
            pct = round(count / total_urls * 100, 1)

            # Check where this topic exists
            topic_lower = topic.lower()
            is_in_product = topic_lower in existing
            is_in_shared = topic_lower in shared_topics
            is_in_other = topic_lower in all_taxonomy_topics and not is_in_product and not is_in_shared

            # Determine status
            if is_in_product:
                status = 'Existing (Product)'
                other_products = ''
            elif is_in_shared:
                status = 'Existing (General)'
                other_products = ''
            elif is_in_other:
                status = 'Existing (Other)'
                # Find which products have this topic
                prods = topic_to_products.get(topic_lower, [])
                other_products = ', '.join(prods[:3])
                if len(prods) > 3:
                    other_products += f' (+{len(prods)-3} more)'
            else:
                status = 'New'
                other_products = ''

            # Determine priority based on percentage and status
            if pct >= 25:
                priority = 'P1'
                impact = 'Core feature - high coverage'
            elif pct >= 15:
                priority = 'P1'
                impact = 'Major feature'
            elif pct >= 8:
                priority = 'P2'
                impact = 'Common feature'
            elif pct >= 3:
                priority = 'P2'
                impact = 'Regular feature'
            else:
                priority = 'P3'
                impact = 'Minor feature'

            # Generate detailed reason
            if is_in_product:
                reason = f'Already in product taxonomy - matching {count} URLs ({pct}%)'
            elif is_in_shared:
                reason = f'In General domain - matching {count} URLs ({pct}%)'
            elif is_in_other:
                reason = f'Exists under: {other_products} - consider adding to {product}'
            elif pct >= 30:
                reason = f'High-frequency matches ({pct}%) - consider adding to taxonomy'
            elif pct >= 15:
                reason = f'Common matching topic - would improve direct assignment'
            else:
                reason = f'Regular occurrence - may benefit from synonym or topic addition'

            # Get sample URLs (shortened)
            sample_urls = topic_urls.get(topic, [])[:2]
            sample_str = '; '.join([u[-50:] if len(u) > 50 else u for u in sample_urls])

            recommendations.append({
                'Product': product,
                'Recommended_Topic': topic,
                'Status': status,
                'Current_Matches': count,
                'URLs_Affected': count,
                'Pct_of_Product': f'{pct}%',
                'Priority': priority,
                'Reason': reason,
                'Impact': impact,
                'Sample_URLs': sample_str
            })

    df_recs = pd.DataFrame(recommendations)

    # Sort by product then by priority then by current matches
    if not df_recs.empty:
        priority_order = {'P1': 0, 'P2': 1, 'P3': 2}
        df_recs['_priority_order'] = df_recs['Priority'].map(priority_order)
        df_recs = df_recs.sort_values(['Product', '_priority_order', 'Current_Matches'],
                                       ascending=[True, True, False])
        df_recs = df_recs.drop('_priority_order', axis=1)

    return df_recs, all_taxonomy_topics


def generate_suggested_new_topics(df_match, all_taxonomy_topics, top_n=5):
    """
    Suggest up to N truly NEW topics that don't exist anywhere in the taxonomy.
    Based on frequently occurring topics in the match data.
    """
    suggestions = []

    # Get topic columns from match data
    topic_cols = [c for c in df_match.columns if c.startswith('Topic_') and c != 'Topic_Frequency_Penalty']

    # Count all topic occurrences across entire dataset
    global_topic_counts = Counter()
    topic_products = {}  # Track which products use each topic

    for _, row in df_match.iterrows():
        product = row.get('Product', '')
        for col in topic_cols:
            topic = row[col]
            if pd.notna(topic) and str(topic).strip():
                topic_str = str(topic).strip()
                global_topic_counts[topic_str] += 1

                if topic_str not in topic_products:
                    topic_products[topic_str] = set()
                if product:
                    topic_products[topic_str].add(product)

    # Filter to only truly NEW topics (not in taxonomy at all)
    new_topics = []
    for topic, count in global_topic_counts.most_common():
        topic_lower = topic.lower()
        if topic_lower not in all_taxonomy_topics:
            products_using = topic_products.get(topic, set())
            new_topics.append({
                'Suggested_Topic': topic,
                'Source': 'Match Data',
                'Total_Matches': count,
                'Products_Using': len(products_using),
                'Product_List': ', '.join(sorted(products_using)[:5]),
                'Recommendation': 'Consider adding to General domain' if len(products_using) >= 3 else f'Consider adding to specific product(s)'
            })

            if len(new_topics) >= top_n:
                break

    return pd.DataFrame(new_topics) if new_topics else pd.DataFrame(columns=[
        'Suggested_Topic', 'Source', 'Total_Matches', 'Products_Using', 'Product_List', 'Recommendation'
    ])


def generate_topics_from_document_source(doc_source_path, all_taxonomy_topics, top_n=10):
    """
    Analyze a document source file (crawled URLs with keywords) to discover
    potential new topics that are NOT in the taxonomy.

    Args:
        doc_source_path: Path to the document source Excel file
        all_taxonomy_topics: Set of all taxonomy topics (lowercase)
        top_n: Number of top suggestions to return

    Returns:
        DataFrame with suggested new topics from document source
    """
    if not doc_source_path or not Path(doc_source_path).exists():
        return pd.DataFrame(columns=[
            'Suggested_Topic', 'Source', 'Occurrences', 'Sample_URLs', 'Recommendation'
        ])

    try:
        df_docs = pd.read_excel(doc_source_path)
        print(f"  Loaded document source: {len(df_docs)} URLs")
    except Exception as e:
        print(f"  Warning: Could not load document source: {e}")
        return pd.DataFrame()

    # Extract keywords from document source
    keyword_cols = [c for c in df_docs.columns if c.lower().startswith('keyword')]
    if not keyword_cols:
        print("  Warning: No keyword columns found in document source")
        return pd.DataFrame()

    # Count keyword occurrences and track URLs
    keyword_counts = Counter()
    keyword_urls = {}

    for _, row in df_docs.iterrows():
        url = row.get('URL', '')
        for col in keyword_cols:
            val = row[col]
            if pd.notna(val) and str(val).strip():
                keyword = str(val).strip()
                keyword_counts[keyword] += 1

                if keyword not in keyword_urls:
                    keyword_urls[keyword] = []
                if len(keyword_urls[keyword]) < 3:
                    keyword_urls[keyword].append(url)

    print(f"  Found {len(keyword_counts)} unique keywords in document source")

    # Find keywords NOT in taxonomy (using fuzzy matching)
    suggestions = []
    for keyword, count in keyword_counts.most_common():
        keyword_lower = keyword.lower()

        # Check if keyword matches any taxonomy topic (exact or partial)
        is_in_taxonomy = False
        for topic in all_taxonomy_topics:
            # Exact match or significant overlap
            if keyword_lower == topic:
                is_in_taxonomy = True
                break
            # Check if keyword is contained in topic or vice versa (for multi-word)
            if len(keyword_lower) > 5 and len(topic) > 5:
                if keyword_lower in topic or topic in keyword_lower:
                    is_in_taxonomy = True
                    break

        if not is_in_taxonomy:
            sample_urls = keyword_urls.get(keyword, [])[:2]
            url_str = '; '.join([u[-60:] if len(u) > 60 else u for u in sample_urls])

            # Determine recommendation based on occurrence count
            if count >= 5:
                recommendation = 'HIGH: Consider adding to General domain'
            elif count >= 3:
                recommendation = 'MEDIUM: Consider adding to relevant product'
            else:
                recommendation = 'LOW: Review for potential addition'

            suggestions.append({
                'Suggested_Topic': keyword,
                'Source': 'Document Source',
                'Occurrences': count,
                'Sample_URLs': url_str,
                'Recommendation': recommendation
            })

            if len(suggestions) >= top_n:
                break

    print(f"  Found {len(suggestions)} potential new topics from document source")

    return pd.DataFrame(suggestions) if suggestions else pd.DataFrame(columns=[
        'Suggested_Topic', 'Source', 'Occurrences', 'Sample_URLs', 'Recommendation'
    ])


def generate_urls_by_product(df_match):
    """Generate URL breakdown by product."""
    url_stats = []

    total_rows = len(df_match)

    for product in df_match['Product'].unique():
        if pd.isna(product):
            continue

        product_data = df_match[df_match['Product'] == product]
        unique_urls = product_data['URL'].nunique()
        product_rows = len(product_data)

        # Calculate average topics per URL
        avg_topics = round(product_rows / unique_urls, 2) if unique_urls > 0 else 0

        url_stats.append({
            'Product': product,
            'Unique_URLs': unique_urls,
            'Total_Rows': product_rows,
            'Pct_of_Total': f'{round(product_rows / total_rows * 100, 1)}%',
            'Avg_Topics_Per_URL': avg_topics
        })

    df_urls = pd.DataFrame(url_stats)
    df_urls = df_urls.sort_values('Unique_URLs', ascending=False)

    return df_urls


def generate_impact_summary(df_gaps, df_quality):
    """Generate impact summary if recommendations implemented."""
    impacts = []

    # Count data quality issues by type
    quality_counts = df_quality['Issue_Type'].value_counts() if not df_quality.empty else {}
    error_count = quality_counts.get('Reference Error', 0)
    typo_count = quality_counts.get('Typo', 0)
    space_count = quality_counts.get('Trailing/Leading Spaces', 0)

    # Add data quality fixes first
    if error_count > 0:
        urls = df_quality[df_quality['Issue_Type'] == 'Reference Error']['URLs_Affected'].sum()
        impacts.append({
            'Action': f'Fix {error_count} reference errors',
            'Product': 'Multiple',
            'URLs_Affected': urls,
            'Before_Ratio': 'N/A',
            'After_Ratio': 'N/A',
            'Improvement': 'Correct broken references'
        })

    if typo_count > 0:
        urls = df_quality[df_quality['Issue_Type'] == 'Typo']['URLs_Affected'].sum()
        impacts.append({
            'Action': f'Fix {typo_count} typos',
            'Product': 'Multiple',
            'URLs_Affected': urls,
            'Before_Ratio': 'N/A',
            'After_Ratio': 'N/A',
            'Improvement': 'Better matching accuracy'
        })

    if space_count > 0:
        urls = df_quality[df_quality['Issue_Type'] == 'Trailing/Leading Spaces']['URLs_Affected'].sum()
        impacts.append({
            'Action': f'Fix {space_count} spacing issues',
            'Product': 'Multiple',
            'URLs_Affected': urls,
            'Before_Ratio': 'N/A',
            'After_Ratio': 'N/A',
            'Improvement': 'Eliminate match failures'
        })

    # Add topic additions for gap products
    total_urls_improved = 0
    total_topics_added = 0

    for _, row in df_gaps.iterrows():
        if row['Gap_Level'] in ['CRITICAL', 'HIGH']:
            topics_needed = row['Topics_Needed']
            if '-' in str(topics_needed):
                topics_low = int(topics_needed.split('-')[0])
            else:
                topics_low = int(topics_needed) if topics_needed != '0' else 0

            if topics_low > 0:
                # Parse current ratio
                ratio_str = str(row['URL_to_Topic_Ratio']).replace(':1', '')
                try:
                    current_ratio = float(ratio_str)
                except:
                    current_ratio = row['Unique_URLs'] / max(row['Current_Topics'], 1)

                new_topics = row['Current_Topics'] + topics_low
                new_ratio = round(row['Unique_URLs'] / new_topics, 1)
                improvement = round((1 - new_ratio / current_ratio) * 100)

                impacts.append({
                    'Action': f'Add {topics_low} topics',
                    'Product': row['Product'],
                    'URLs_Affected': row['Unique_URLs'],
                    'Before_Ratio': f'{current_ratio:.1f}:1',
                    'After_Ratio': f'{new_ratio}:1',
                    'Improvement': f'{improvement}% better'
                })

                total_urls_improved += row['Unique_URLs']
                total_topics_added += topics_low

    # Add summary row
    if total_topics_added > 0:
        gap_products = len(df_gaps[df_gaps['Gap_Level'].isin(['CRITICAL', 'HIGH'])])
        impacts.append({
            'Action': f'TOTAL: Add {total_topics_added} topics',
            'Product': f'{gap_products} Products',
            'URLs_Affected': total_urls_improved,
            'Before_Ratio': 'Various',
            'After_Ratio': 'Improved',
            'Improvement': 'Significant coverage increase'
        })

    return pd.DataFrame(impacts)


def generate_topics_to_add(df_recs, df_gaps):
    """
    Generate specific list of topics to add for each gap product.
    Shows exactly which topics should be added based on match frequency.

    Priority order:
    1. New topics (not in taxonomy at all)
    2. Existing (Other) - topics in taxonomy but under different product
    3. Existing (General) - high-use General topics to add specifically to product
    """
    topics_to_add = []

    # Get gap products (CRITICAL and HIGH)
    gap_products = df_gaps[df_gaps['Gap_Level'].isin(['CRITICAL', 'HIGH'])]

    for _, gap_row in gap_products.iterrows():
        product = gap_row['Product']
        topics_needed = gap_row['Topics_Needed']

        # Parse number of topics needed
        if '-' in str(topics_needed):
            num_topics = int(topics_needed.split('-')[0])
        else:
            num_topics = int(topics_needed) if topics_needed != '0' else 0

        if num_topics == 0:
            continue

        # Get all recommendations for this product (excluding Existing (Product))
        all_product_recs = df_recs[
            (df_recs['Product'] == product) &
            (df_recs['Status'] != 'Existing (Product)')
        ].copy()

        # Sort by priority: New > Existing (Other) > Existing (General), then by matches
        status_priority = {'New': 0, 'Existing (Other)': 1, 'Existing (General)': 2}
        all_product_recs['_status_priority'] = all_product_recs['Status'].map(status_priority)
        all_product_recs = all_product_recs.sort_values(
            ['_status_priority', 'Current_Matches'],
            ascending=[True, False]
        )

        # Take top N topics
        top_topics = all_product_recs.head(num_topics)

        for rank, (_, topic_row) in enumerate(top_topics.iterrows(), 1):
            status = topic_row['Status']

            # Determine action based on status
            if status == 'New':
                action = 'Create new topic in taxonomy'
            elif status == 'Existing (Other)':
                action = 'Add to this product (exists under other product)'
            else:  # Existing (General)
                action = 'Consider adding specifically to product (currently in General)'

            topics_to_add.append({
                'Product': product,
                'Gap_Level': gap_row['Gap_Level'],
                'Rank': rank,
                'Topic_to_Add': topic_row['Recommended_Topic'],
                'Current_Status': status,
                'Matches': topic_row['Current_Matches'],
                'Pct_of_Product': topic_row['Pct_of_Product'],
                'Reason': topic_row['Reason'],
                'Action': action
            })

    return pd.DataFrame(topics_to_add) if topics_to_add else pd.DataFrame(columns=[
        'Product', 'Gap_Level', 'Rank', 'Topic_to_Add', 'Current_Status',
        'Matches', 'Pct_of_Product', 'Reason', 'Action'
    ])


def generate_executive_summary(df_match, df_taxonomy, df_gaps, df_quality):
    """Generate executive summary metrics."""

    total_urls = df_match['URL'].nunique()
    total_rows = len(df_match)

    # Count unmapped (check for 'UNMAPPED' in Domain or check Top_Score = 0)
    if 'Domain' in df_match.columns:
        unmapped = len(df_match[df_match['Domain'] == 'UNMAPPED'])
        unmapped_urls = df_match[df_match['Domain'] == 'UNMAPPED']['URL'].nunique()
    else:
        unmapped = 0
        unmapped_urls = 0

    match_rate = round((total_urls - unmapped_urls) / total_urls * 100, 1) if total_urls > 0 else 0

    # Count products with gaps by level
    critical_gaps = len(df_gaps[df_gaps['Gap_Level'] == 'CRITICAL'])
    high_gaps = len(df_gaps[df_gaps['Gap_Level'] == 'HIGH'])
    products_with_gaps = critical_gaps + high_gaps

    # Count data quality issues
    quality_issues = len(df_quality) if not df_quality.empty else 0
    critical_issues = len(df_quality[df_quality['Priority'] == 'P1-CRITICAL']) if not df_quality.empty else 0

    # Estimate recommended new topics
    def parse_topics_needed(x):
        try:
            if '-' in str(x):
                return int(str(x).split('-')[0])
            return int(x) if x != '0' else 0
        except:
            return 0

    recommended_topics_low = df_gaps[df_gaps['Gap_Level'].isin(['CRITICAL', 'HIGH'])]['Topics_Needed'].apply(parse_topics_needed).sum()
    recommended_topics_high = int(recommended_topics_low * 1.3)

    # URLs that would benefit
    urls_benefit = df_gaps[df_gaps['Gap_Level'].isin(['CRITICAL', 'HIGH'])]['Unique_URLs'].sum()
    benefit_pct = round(urls_benefit / total_urls * 100) if total_urls > 0 else 0

    # Count total topics in taxonomy
    topic_cols = [c for c in df_taxonomy.columns if c.startswith('Topic')]
    total_taxonomy_topics = 0
    for _, row in df_taxonomy.iterrows():
        for col in topic_cols:
            if pd.notna(row[col]) and str(row[col]).strip():
                total_taxonomy_topics += 1

    summary = pd.DataFrame([
        {'Metric': 'Total Matched URLs', 'Value': f'{total_urls:,}'},
        {'Metric': 'Total Match Rows', 'Value': f'{total_rows:,}'},
        {'Metric': 'Match Success Rate', 'Value': f'{match_rate}%'},
        {'Metric': 'Unmapped URLs', 'Value': f'{unmapped_urls:,}'},
        {'Metric': 'Total Products', 'Value': df_match['Product'].nunique()},
        {'Metric': 'Total Taxonomy Topics', 'Value': f'{total_taxonomy_topics:,}'},
        {'Metric': 'Products with Critical Gaps', 'Value': critical_gaps},
        {'Metric': 'Products with High Gaps', 'Value': high_gaps},
        {'Metric': 'Data Quality Issues', 'Value': quality_issues},
        {'Metric': 'Critical Data Issues', 'Value': critical_issues},
        {'Metric': 'Recommended New Topics', 'Value': f'{recommended_topics_low}-{recommended_topics_high}'},
        {'Metric': 'URLs That Would Benefit', 'Value': f'{urls_benefit:,} ({benefit_pct}%)'},
        {'Metric': 'Report Generated', 'Value': datetime.now().strftime('%Y-%m-%d %H:%M')}
    ])

    return summary


def main():
    """Main execution function."""
    print("=" * 60)
    print("Topic Recommendations Report Generator")
    print("=" * 60)

    # Load data
    print("\n[1/7] Loading data...")
    df_match, df_taxonomy = load_data()

    # Analyze data quality
    print("\n[2/7] Analyzing data quality issues...")
    df_quality = analyze_data_quality(df_taxonomy, df_match)
    print(f"Found {len(df_quality)} data quality issues")

    # Analyze product gaps
    print("\n[3/7] Analyzing product gaps...")
    df_gaps = analyze_product_gaps(df_match, df_taxonomy)
    gaps_critical = len(df_gaps[df_gaps['Gap_Level'] == 'CRITICAL'])
    gaps_high = len(df_gaps[df_gaps['Gap_Level'] == 'HIGH'])
    print(f"Found {gaps_critical} critical gaps, {gaps_high} high gaps")

    # Generate topic recommendations
    print("\n[4/8] Generating topic recommendations...")
    df_recs, all_taxonomy_topics = generate_topic_recommendations(df_match, df_taxonomy)
    print(f"Generated {len(df_recs)} topic recommendations")

    # Generate suggested new topics (truly new - not in taxonomy at all)
    print("\n[5/9] Generating suggested new topics from match data...")
    df_new_topics_match = generate_suggested_new_topics(df_match, all_taxonomy_topics, top_n=5)
    print(f"Found {len(df_new_topics_match)} suggested new topics from match data")

    # Generate suggested topics from document source (if configured)
    print("\n[6/10] Analyzing document source for new topics...")
    doc_source = DOCUMENT_SOURCE_FILE if DOCUMENT_SOURCE_FILE else None
    df_new_topics_docs = generate_topics_from_document_source(
        doc_source,
        all_taxonomy_topics,
        top_n=10
    )

    # Combine both sources of new topic suggestions
    df_new_topics = pd.concat([df_new_topics_match, df_new_topics_docs], ignore_index=True)
    print(f"Total suggested new topics: {len(df_new_topics)}")

    # Generate URLs by product
    print("\n[7/10] Generating URLs by product breakdown...")
    df_urls = generate_urls_by_product(df_match)
    print(f"Analyzed {len(df_urls)} products")

    # Generate impact summary
    print("\n[8/10] Generating impact summary...")
    df_impact = generate_impact_summary(df_gaps, df_quality)
    print(f"Generated {len(df_impact)} impact items")

    # Generate specific topics to add for gap products
    print("\n[9/10] Generating specific topics to add...")
    df_topics_to_add = generate_topics_to_add(df_recs, df_gaps)
    print(f"Generated {len(df_topics_to_add)} specific topic additions")

    # Generate executive summary
    print("\n[10/10] Generating executive summary...")
    df_summary = generate_executive_summary(df_match, df_taxonomy, df_gaps, df_quality)

    # Write to Excel with formatting
    output_path = Path(__file__).parent / OUTPUT_FILE
    print(f"\nWriting report to: {output_path}")

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Sanitize all DataFrames before writing to prevent Excel corruption
        # Sheet 1: Executive Summary
        sanitize_dataframe(df_summary).to_excel(writer, sheet_name='Executive Summary', index=False)

        # Sheet 2: Data Quality Issues
        sanitize_dataframe(df_quality).to_excel(writer, sheet_name='Data Quality Issues', index=False)

        # Sheet 3: Product Gap Analysis
        sanitize_dataframe(df_gaps).to_excel(writer, sheet_name='Product Gap Analysis', index=False)

        # Sheet 4: Topic Recommendations
        sanitize_dataframe(df_recs).to_excel(writer, sheet_name='Topic Recommendations', index=False)

        # Sheet 5: Suggested New Topics (truly new - not in taxonomy)
        sanitize_dataframe(df_new_topics).to_excel(writer, sheet_name='Suggested New Topics', index=False)

        # Sheet 6: URLs by Product
        sanitize_dataframe(df_urls).to_excel(writer, sheet_name='URLs by Product', index=False)

        # Sheet 7: Impact Summary
        sanitize_dataframe(df_impact).to_excel(writer, sheet_name='Impact Summary', index=False)

        # Sheet 8: Topics to Add (specific recommendations for gap products)
        sanitize_dataframe(df_topics_to_add).to_excel(writer, sheet_name='Topics to Add', index=False)

        # Apply formatting
        try:
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter

            # Define styles
            header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
            header_font = Font(bold=True, color='FFFFFF')
            critical_fill = PatternFill(start_color='FF6B6B', end_color='FF6B6B', fill_type='solid')
            high_fill = PatternFill(start_color='FFB347', end_color='FFB347', fill_type='solid')
            p1_fill = PatternFill(start_color='FF9999', end_color='FF9999', fill_type='solid')
            p2_fill = PatternFill(start_color='FFCC99', end_color='FFCC99', fill_type='solid')
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
                                max_length = min(len(str(cell.value)), 50)
                        except:
                            pass
                    adjusted_width = max_length + 2
                    ws.column_dimensions[column_letter].width = adjusted_width

                # Apply conditional formatting for priority columns
                for row in ws.iter_rows(min_row=2):
                    for cell in row:
                        cell.border = thin_border

                        # Color priority cells
                        if cell.value:
                            val = str(cell.value)
                            if 'CRITICAL' in val or val == 'P1':
                                cell.fill = p1_fill
                            elif 'HIGH' in val or val == 'P2':
                                cell.fill = p2_fill

        except Exception as e:
            print(f"Warning: Could not apply formatting: {e}")

    print("\n" + "=" * 60)
    print("Report generated successfully!")
    print(f"Output file: {output_path}")
    print("=" * 60)

    # Print summary
    print("\nSUMMARY:")
    for _, row in df_summary.iterrows():
        print(f"  {row['Metric']}: {row['Value']}")


if __name__ == '__main__':
    main()
