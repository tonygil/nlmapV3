"""
Restructure Taxonomy - Convert Product 1-5 columns to single Product column

This utility converts taxonomy files with multiple Product columns (Product 1, Product 2, etc.)
to the standard format with a single Product column by expanding rows.

Example:
    INPUT (1 row):
    Productfamily | Product 1           | Product 2            | Domain | Topic 1
    Adsolut       | Adsolut boekhouding | Adsolut Jaarrekening | Welkom | Login

    OUTPUT (2 rows):
    Product               | Domain | Topic 1
    Adsolut boekhouding   | Welkom | Login
    Adsolut Jaarrekening  | Welkom | Login

Usage:
    python restructure_taxonomy.py -i "Taxonomy BE.xlsx" -o "taxonomy_standard.xlsx"
    python restructure_taxonomy.py -i "Taxonomy BE.xlsx"  # Auto-names output
"""

import pandas as pd
import argparse
import sys
from pathlib import Path
from datetime import datetime


def detect_product_columns(df):
    """
    Detect Product columns in the taxonomy file.

    Returns:
        tuple: (product_columns, productfamily_col)
            product_columns: List of Product N column names
            productfamily_col: Name of Productfamily column (or None)
    """
    # Look for Product 1, Product 2, etc.
    product_cols = [col for col in df.columns if col.startswith('Product ') and col.split()[-1].isdigit()]
    product_cols = sorted(product_cols, key=lambda x: int(x.split()[-1]))

    # Look for Productfamily
    productfamily_col = None
    for col in df.columns:
        if col.lower() == 'productfamily':
            productfamily_col = col
            break

    return product_cols, productfamily_col


def restructure_taxonomy(input_file, output_file=None, verbose=True):
    """
    Restructure taxonomy from Product 1-5 format to single Product column.

    Args:
        input_file: Path to input taxonomy Excel file
        output_file: Path to output file (auto-generated if None)
        verbose: Print progress messages

    Returns:
        dict: Statistics about the restructuring
    """
    if verbose:
        print(f"Loading taxonomy from: {input_file}")

    # Read input file
    df = pd.read_excel(input_file)

    if verbose:
        print(f"Input: {len(df)} rows, {len(df.columns)} columns")
        print(f"Columns: {list(df.columns)}")

    # Detect Product columns
    product_cols, productfamily_col = detect_product_columns(df)

    if not product_cols:
        print("ERROR: No Product columns found (expected 'Product 1', 'Product 2', etc.)")
        print(f"Available columns: {list(df.columns)}")
        return None

    if verbose:
        print(f"\nDetected {len(product_cols)} product columns: {product_cols}")
        if productfamily_col:
            print(f"Detected Productfamily column: {productfamily_col}")

    # Get all other columns (Domain, Segment, Topic 1-N)
    exclude_cols = set(product_cols)
    if productfamily_col:
        exclude_cols.add(productfamily_col)

    other_cols = [col for col in df.columns if col not in exclude_cols]

    if verbose:
        print(f"Other columns to preserve: {other_cols}")

    # Expand rows
    expanded_rows = []

    for idx, row in df.iterrows():
        # For each Product column that has a value
        for product_col in product_cols:
            product_value = row[product_col]

            # Skip empty/NaN product values
            if pd.isna(product_value) or str(product_value).strip() == '':
                continue

            # Create new row
            new_row = {'Product': product_value}

            # Copy all other columns
            for col in other_cols:
                new_row[col] = row[col]

            expanded_rows.append(new_row)

    # Create output dataframe
    output_df = pd.DataFrame(expanded_rows)

    # Reorder columns: Product first, then others in original order
    cols_order = ['Product'] + other_cols
    output_df = output_df[cols_order]

    if verbose:
        print(f"\nOutput: {len(output_df)} rows (expanded from {len(df)} rows)")
        print(f"Expansion factor: {len(output_df) / len(df):.2f}x")

    # Count topics (for validation)
    topic_cols = [col for col in output_df.columns if col.startswith('Topic')]
    input_topic_count = df[topic_cols].notna().sum().sum()
    output_topic_count = output_df[topic_cols].notna().sum().sum()

    if verbose:
        print(f"\nValidation:")
        print(f"  Input topics: {input_topic_count}")
        print(f"  Output topics: {output_topic_count}")
        if input_topic_count == output_topic_count:
            print("  ✓ Topic count preserved")
        else:
            print("  ⚠ WARNING: Topic count mismatch!")

    # Auto-generate output filename if not provided
    if output_file is None:
        input_path = Path(input_file)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = input_path.parent / f"{input_path.stem}_restructured_{timestamp}.xlsx"

    # Create backup of original if output would overwrite it
    output_path = Path(output_file)
    if output_path.exists():
        backup_path = output_path.parent / f"{output_path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        if verbose:
            print(f"\nCreating backup: {backup_path}")
        output_path.rename(backup_path)

    # Save output
    if verbose:
        print(f"\nSaving to: {output_file}")

    output_df.to_excel(output_file, index=False)

    if verbose:
        print("✓ Restructuring complete!")

    # Return statistics
    return {
        'input_rows': len(df),
        'output_rows': len(output_df),
        'expansion_factor': len(output_df) / len(df),
        'input_topics': input_topic_count,
        'output_topics': output_topic_count,
        'topics_preserved': input_topic_count == output_topic_count,
        'product_columns': len(product_cols),
        'output_file': str(output_file)
    }


def main():
    parser = argparse.ArgumentParser(
        description='Restructure taxonomy from Product 1-5 format to single Product column',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python restructure_taxonomy.py -i "Taxonomy BE.xlsx"
    python restructure_taxonomy.py -i "Taxonomy BE.xlsx" -o "taxonomy_standard.xlsx"
    python restructure_taxonomy.py -i "Taxonomy BE.xlsx" --quiet
        """
    )

    parser.add_argument('-i', '--input', required=True,
                        help='Input taxonomy Excel file (with Product 1-5 columns)')
    parser.add_argument('-o', '--output', default=None,
                        help='Output taxonomy Excel file (auto-generated if not specified)')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress progress messages')

    args = parser.parse_args()

    # Verify input file exists
    if not Path(args.input).exists():
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)

    # Restructure
    stats = restructure_taxonomy(args.input, args.output, verbose=not args.quiet)

    if stats is None:
        sys.exit(1)

    # Print summary
    if not args.quiet:
        print(f"\n{'='*60}")
        print("SUMMARY:")
        print(f"  Input rows: {stats['input_rows']}")
        print(f"  Output rows: {stats['output_rows']}")
        print(f"  Expansion: {stats['expansion_factor']:.2f}x")
        print(f"  Topics preserved: {'Yes' if stats['topics_preserved'] else 'NO'}")
        print(f"  Output file: {stats['output_file']}")
        print(f"{'='*60}")


if __name__ == '__main__':
    main()
