"""
apply_url_exclusions.py  —  Taxonomy Mapper V3
==================================================
Reads an exclusions JSON file (exported from unmapped_review.html) and
creates a filtered copy of the semantic Excel file with excluded URLs removed.

Usage:
    # Auto-detect semantic file from JSON country/date
    python apply_url_exclusions.py -i unmapped_exclusions_BE_2026-02-19.json

    # Specify semantic file explicitly
    python apply_url_exclusions.py -i unmapped_exclusions_BE_2026-02-19.json -s Semantic_BE_20260219.xlsx

    # Preview without writing
    python apply_url_exclusions.py -i unmapped_exclusions_BE_2026-02-19.json --dry-run

Output: {semantic_stem}_filtered.xlsx in the same folder as the semantic file.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent


# ── helpers ──────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def detect_country(path: Path) -> str:
    m = re.search(r"_([A-Z]{2})_?\d{4}", path.name)
    return m.group(1) if m else ""


def strip_anchor(url: str) -> str:
    """Remove URL fragment (#...) for comparison."""
    return url.split("#")[0].strip()


def find_semantic_file(country: str) -> Path | None:
    """
    Auto-locate the most recently modified semantic/Semantic file for the
    given country.  Tries several naming patterns in order.
    """
    patterns = [
        f"Semantic_{country}_*.xlsx",
        f"Semantic_*_{country}_*.xlsx",
        "Semantic_*.xlsx",
        f"semantic_carriers_{country}.xlsx",
        "semantic_carriers_list.xlsx",
    ]
    for pat in patterns:
        found = sorted(ROOT.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
        if found:
            return found[0]
    return None


# ── main logic ────────────────────────────────────────────────────────────────

def apply_exclusions(excl_path: Path, semantic_path: Path, dry_run: bool) -> None:
    # Load exclusions
    data = load_json(excl_path)
    excluded_urls: list[str] = data.get("excluded_urls", [])

    if not excluded_urls:
        print("Exclusions file contains no URLs — nothing to do.")
        return

    excluded_clean = {strip_anchor(u) for u in excluded_urls}

    print(f"\nExclusions file : {excl_path.name}")
    print(f"Country         : {data.get('country', '?')}")
    print(f"Exported at     : {data.get('exported_at', '?')}")
    print(f"Source match    : {data.get('source_file', '?')}")
    print(f"URLs to exclude : {len(excluded_clean)}")
    print(f"\nSemantic file   : {semantic_path}")

    if not semantic_path.exists():
        print(f"ERROR: Semantic file not found: {semantic_path}")
        sys.exit(1)

    # Load semantic file
    print("Reading semantic file…")
    df = pd.read_excel(semantic_path, dtype=str)

    if "URL" not in df.columns:
        print("ERROR: Semantic file has no 'URL' column.")
        sys.exit(1)

    total = len(df)

    # Normalise for comparison (strip anchor, strip whitespace)
    df_urls_clean = df["URL"].fillna("").str.strip().str.split("#").str[0]
    mask_remove   = df_urls_clean.isin(excluded_clean)
    n_remove = int(mask_remove.sum())
    n_keep   = total - n_remove

    print(f"\nTotal rows in semantic file : {total}")
    print(f"Rows matched for removal    : {n_remove}")
    print(f"Rows to keep                : {n_keep}")

    if n_remove == 0:
        print("\nNo matching URLs found in semantic file — nothing changed.")
        print("Tip: verify the semantic file is the one that was used to generate the match output.")
        return

    if dry_run:
        print("\n[DRY RUN] First 25 URLs that would be removed:")
        removed_urls = df.loc[mask_remove, "URL"].unique()
        for url in sorted(removed_urls)[:25]:
            print(f"  {url}")
        if len(removed_urls) > 25:
            print(f"  … and {len(removed_urls) - 25} more")
        print("\n[DRY RUN] No files modified. Re-run without --dry-run to apply.")
        return

    # Write filtered file
    df_out   = df[~mask_remove].copy()
    out_path = semantic_path.with_name(semantic_path.stem + "_filtered.xlsx")

    print(f"\nWriting: {out_path.name}")
    df_out.to_excel(out_path, index=False)

    print(f"\nDone.")
    print(f"  Kept   : {n_keep:,} rows")
    print(f"  Removed: {n_remove:,} rows")
    print(f"  Output : {out_path}")
    print()
    print("Next step: use the filtered file as the semantic file for the next match run.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Apply URL exclusions from unmapped_review.html "
            "to filter a semantic Excel file."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python apply_url_exclusions.py -i unmapped_exclusions_BE_2026-02-19.json
  python apply_url_exclusions.py -i unmapped_exclusions_BE_2026-02-19.json -s Semantic_BE.xlsx
  python apply_url_exclusions.py -i unmapped_exclusions_BE_2026-02-19.json --dry-run
""",
    )
    parser.add_argument(
        "-i", "--input", required=True,
        help="Path to the unmapped_exclusions_*.json file exported from unmapped_review.html"
    )
    parser.add_argument(
        "-s", "--semantic",
        help=(
            "Path to the semantic Excel file to filter. "
            "If omitted, auto-searches for Semantic_{CODE}_*.xlsx in the project root."
        )
    )
    parser.add_argument(
        "-c", "--country",
        help="Country code (auto-detected from input filename if omitted)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would be removed without writing any files"
    )
    args = parser.parse_args()

    excl_path = Path(args.input).resolve()
    if not excl_path.exists():
        print(f"ERROR: File not found: {excl_path}")
        sys.exit(1)

    # Resolve semantic file
    if args.semantic:
        semantic_path = Path(args.semantic).resolve()
    else:
        detected_country = args.country or detect_country(excl_path)
        if not detected_country:
            print("ERROR: Could not detect country code from filename.")
            print("       Specify it with -c (e.g. -c BE) or use -s to give the semantic file path.")
            sys.exit(1)
        detected_country = detected_country.upper()
        semantic_path = find_semantic_file(detected_country)
        if not semantic_path:
            print(f"ERROR: No semantic file found for country '{detected_country}' in {ROOT}")
            print("       Use -s <path> to specify the file explicitly.")
            sys.exit(1)
        print(f"Auto-detected semantic file: {semantic_path.name}")

    apply_exclusions(excl_path, semantic_path, args.dry_run)


if __name__ == "__main__":
    main()
