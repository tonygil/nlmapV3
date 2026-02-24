"""
Synonym Validator Tool
Validates synonym file structure and provides coverage statistics.
"""

import json
import sys
from pathlib import Path
from collections import Counter


def validate_synonym_file(file_path):
    """Validate a synonym JSON file."""
    print("=" * 80)
    print("SYNONYM FILE VALIDATOR")
    print("=" * 80)
    print(f"\nFile: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ ERROR: File not found: {file_path}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Invalid JSON syntax: {e}")
        return False

    # Check required fields
    print("\n1. STRUCTURE VALIDATION")
    print("-" * 80)

    required_fields = ['description', 'language', 'version', 'synonyms']
    missing = [f for f in required_fields if f not in data]

    if missing:
        print(f"❌ Missing required fields: {', '.join(missing)}")
        return False
    else:
        print("✓ All required fields present")

    # Check metadata
    print(f"\n   Description: {data.get('description', 'N/A')[:70]}...")
    print(f"   Language: {data.get('language', 'N/A')}")
    print(f"   Version: {data.get('version', 'N/A')}")
    print(f"   Last Updated: {data.get('last_updated', 'N/A')}")

    # Validate synonyms section
    print("\n2. SYNONYMS VALIDATION")
    print("-" * 80)

    synonyms = data.get('synonyms', {})

    if not synonyms:
        print("❌ ERROR: 'synonyms' section is empty")
        return False

    # Count statistics
    comment_keys = [k for k in synonyms.keys() if k.startswith('_comment')]
    topic_keys = [k for k in synonyms.keys() if not k.startswith('_comment')]

    print(f"✓ Total entries: {len(topic_keys)}")
    print(f"  Comment sections: {len(comment_keys)}")

    # Validate each synonym entry
    issues = []
    total_variations = 0
    variation_counts = []

    for key, value in synonyms.items():
        if key.startswith('_comment'):
            continue

        # Check value is list
        if not isinstance(value, list):
            issues.append(f"'{key}': Value is not a list (type: {type(value).__name__})")
            continue

        # Check not empty
        if len(value) == 0:
            issues.append(f"'{key}': Empty synonym list")
            continue

        # Check all items are strings
        non_strings = [i for i, v in enumerate(value) if not isinstance(v, str)]
        if non_strings:
            issues.append(f"'{key}': Non-string values at indices {non_strings}")

        total_variations += len(value)
        variation_counts.append(len(value))

    if issues:
        print(f"\n❌ Found {len(issues)} validation issues:")
        for issue in issues[:10]:  # Show first 10
            print(f"   - {issue}")
        if len(issues) > 10:
            print(f"   ... and {len(issues) - 10} more")
        return False
    else:
        print("✓ All synonym entries are valid")

    # Statistics
    print("\n3. COVERAGE STATISTICS")
    print("-" * 80)
    print(f"  Total topics: {len(topic_keys)}")
    print(f"  Total synonym variations: {total_variations:,}")
    print(f"  Average variations per topic: {total_variations / len(topic_keys):.1f}")
    print(f"  Min variations: {min(variation_counts)}")
    print(f"  Max variations: {max(variation_counts)}")
    print(f"  Median variations: {sorted(variation_counts)[len(variation_counts)//2]}")

    # Distribution
    print(f"\n  Distribution of variation counts:")
    ranges = [(1, 5), (6, 10), (11, 15), (16, 20), (21, 100)]
    for low, high in ranges:
        count = len([c for c in variation_counts if low <= c <= high])
        pct = count / len(variation_counts) * 100
        print(f"    {low:2d}-{high:2d} variations: {count:3d} topics ({pct:5.1f}%)")

    # Check for duplicates across synonym groups
    print("\n4. DUPLICATE ANALYSIS")
    print("-" * 80)

    all_variations = []
    for key, value in synonyms.items():
        if not key.startswith('_comment'):
            all_variations.extend([(v.lower(), key) for v in value])

    # Find duplicates
    variation_counts = Counter([v for v, _ in all_variations])
    duplicates = {v: count for v, count in variation_counts.items() if count > 1}

    if duplicates:
        print(f"  Found {len(duplicates)} variations appearing in multiple topics:")
        print(f"  (This is often intentional for cross-mapping)")
        print(f"\n  Top 10 most duplicated:")
        for variation, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:10]:
            topics = [k for v, k in all_variations if v.lower() == variation]
            print(f"    '{variation}' appears in {count} topics: {', '.join(topics[:3])}")
            if count > 3:
                print(f"      ... and {count - 3} more")
    else:
        print("  No duplicate variations found (all unique)")

    # Find very similar topic keys
    print("\n5. SIMILAR TOPIC KEYS")
    print("-" * 80)

    from difflib import SequenceMatcher

    similar_pairs = []
    topic_list = list(topic_keys)
    for i, key1 in enumerate(topic_list):
        for key2 in topic_list[i+1:]:
            ratio = SequenceMatcher(None, key1.lower(), key2.lower()).ratio()
            if ratio > 0.7:  # 70% similar
                similar_pairs.append((key1, key2, ratio))

    if similar_pairs:
        print(f"  Found {len(similar_pairs)} pairs of similar topic keys:")
        print(f"  (Consider consolidating if they represent the same concept)")
        for key1, key2, ratio in sorted(similar_pairs, key=lambda x: x[2], reverse=True)[:10]:
            print(f"    '{key1}' ~ '{key2}' ({ratio*100:.0f}% similar)")
    else:
        print("  No highly similar topic keys found")

    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"✓ File structure: VALID")
    print(f"✓ Synonym entries: {len(topic_keys)} topics")
    print(f"✓ Total variations: {total_variations:,}")
    print(f"✓ Coverage: {'GOOD' if total_variations >= 300 else 'NEEDS IMPROVEMENT'}")
    print("=" * 80)

    return True


def compare_synonym_files(file1, file2):
    """Compare two synonym files."""
    print("=" * 80)
    print("SYNONYM FILE COMPARISON")
    print("=" * 80)

    try:
        with open(file1, 'r', encoding='utf-8') as f:
            data1 = json.load(f)
        with open(file2, 'r', encoding='utf-8') as f:
            data2 = json.load(f)
    except Exception as e:
        print(f"❌ ERROR loading files: {e}")
        return

    syn1 = {k: v for k, v in data1.get('synonyms', {}).items() if not k.startswith('_comment')}
    syn2 = {k: v for k, v in data2.get('synonyms', {}).items() if not k.startswith('_comment')}

    topics1 = set(syn1.keys())
    topics2 = set(syn2.keys())

    # Topics comparison
    print(f"\nFile 1: {file1}")
    print(f"  Topics: {len(topics1)}")
    print(f"  Variations: {sum(len(v) for v in syn1.values())}")

    print(f"\nFile 2: {file2}")
    print(f"  Topics: {len(topics2)}")
    print(f"  Variations: {sum(len(v) for v in syn2.values())}")

    # Differences
    only_in_1 = topics1 - topics2
    only_in_2 = topics2 - topics1
    common = topics1 & topics2

    print(f"\nComparison:")
    print(f"  Topics in both: {len(common)}")
    print(f"  Only in File 1: {len(only_in_1)}")
    print(f"  Only in File 2: {len(only_in_2)}")

    if only_in_1:
        print(f"\n  Topics only in File 1:")
        for topic in sorted(only_in_1)[:10]:
            print(f"    - {topic}")
        if len(only_in_1) > 10:
            print(f"    ... and {len(only_in_1) - 10} more")

    if only_in_2:
        print(f"\n  Topics only in File 2:")
        for topic in sorted(only_in_2)[:10]:
            print(f"    - {topic}")
        if len(only_in_2) > 10:
            print(f"    ... and {len(only_in_2) - 10} more")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Validate: python synonym_validator.py <synonym_file.json>")
        print("  Compare:  python synonym_validator.py <file1.json> <file2.json>")
        sys.exit(1)

    if len(sys.argv) == 2:
        validate_synonym_file(sys.argv[1])
    elif len(sys.argv) == 3:
        compare_synonym_files(sys.argv[1], sys.argv[2])
