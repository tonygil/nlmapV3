"""
apply_synonym_patch.py  —  Taxonomy Mapper V3
================================================
Merges a synonym_patch_*.json file (exported from synonym_review.html)
into the country's synonyms.json file.

Usage:
    python apply_synonym_patch.py -i synonym_patch_BE_2026-02-18.json
    python apply_synonym_patch.py -i synonym_patch_BE_2026-02-18.json -c BE
    python apply_synonym_patch.py -i synonym_patch_BE_2026-02-18.json --dry-run

The country code is auto-detected from the patch filename if not given via -c.
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# ── project root is this script's directory ──────────────────────────────────
ROOT = Path(__file__).parent


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def backup_synonyms(synonyms_path: Path) -> Path:
    """Create a timestamped backup of synonyms.json before modifying it."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = synonyms_path.with_name(f"synonyms_backup_{ts}.json")
    shutil.copy2(synonyms_path, backup_path)
    return backup_path


def detect_country(patch_path: Path) -> str:
    """Extract country code from filename, e.g. synonym_patch_BE_2026-02-18.json → 'BE'."""
    m = re.search(r"_([A-Z]{2})_?\d{4}", patch_path.name)
    return m.group(1) if m else ""


def apply_patch(patch_path: Path, country: str, dry_run: bool) -> None:
    # ── load patch ────────────────────────────────────────────────────────────
    patch = load_json(patch_path)
    patch_synonyms: dict[str, list[str]] = patch.get("synonyms", {})

    if not patch_synonyms:
        print("Patch file contains no synonyms — nothing to do.")
        return

    # ── locate synonyms.json ──────────────────────────────────────────────────
    synonyms_path = ROOT / "countries" / country / "synonyms.json"
    if not synonyms_path.exists():
        print(f"ERROR: synonyms.json not found at {synonyms_path}")
        sys.exit(1)

    # ── load existing synonyms ────────────────────────────────────────────────
    existing = load_json(synonyms_path)
    syn_dict: dict[str, list[str]] = existing.get("synonyms", {})

    # ── compute changes ───────────────────────────────────────────────────────
    stats = {"topics_updated": 0, "topics_new": 0, "added": 0, "already_present": 0}
    changes: list[str] = []

    for topic, new_kws in sorted(patch_synonyms.items()):
        if topic not in syn_dict:
            # Topic doesn't exist in synonyms.json yet — create it
            if not dry_run:
                syn_dict[topic] = []
            stats["topics_new"] += 1

        existing_kws = syn_dict.get(topic, [])
        existing_lower = {k.lower() for k in existing_kws}

        added_for_topic: list[str] = []
        for kw in new_kws:
            kw_clean = kw.lower().strip()
            if kw_clean in existing_lower:
                stats["already_present"] += 1
            else:
                added_for_topic.append(kw_clean)
                if not dry_run:
                    syn_dict.setdefault(topic, []).append(kw_clean)
                stats["added"] += 1
                existing_lower.add(kw_clean)

        if added_for_topic:
            stats["topics_updated"] += 1
            changes.append(f"  [{topic}]  +{added_for_topic}")

    # ── report ────────────────────────────────────────────────────────────────
    print(f"\nPatch file : {patch_path.name}")
    print(f"Country    : {country}")
    print(f"Source file: {patch.get('source_file', '—')}")
    print(f"Exported at: {patch.get('exported_at', '—')}")
    print()

    if not changes:
        print("Nothing new to add — all keywords already exist in synonyms.json.")
        return

    label = "[DRY RUN] Would add" if dry_run else "Adding"
    print(f"{label} {stats['added']} synonym(s) to {stats['topics_updated']} topic(s):\n")
    for c in changes:
        print(c)

    if stats["already_present"]:
        print(f"\n  ({stats['already_present']} already present — skipped)")

    if dry_run:
        print("\n[DRY RUN] No files modified. Re-run without --dry-run to apply.")
        return

    # ── backup + save ─────────────────────────────────────────────────────────
    backup = backup_synonyms(synonyms_path)
    print(f"\nBackup saved -> {backup.name}")

    existing["synonyms"] = syn_dict
    save_json(synonyms_path, existing)

    print(f"synonyms.json updated OK ({synonyms_path})")
    print()
    print(f"Summary: +{stats['added']} synonyms across {stats['topics_updated']} topics "
          f"({stats['topics_new']} new topic entries created)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply a synonym patch JSON to a country's synonyms.json"
    )
    parser.add_argument(
        "-i", "--input", required=True,
        help="Path to the synonym_patch_*.json file (exported from synonym_review.html)"
    )
    parser.add_argument(
        "-c", "--country",
        help="Country code (e.g. BE, NL, GB, SE). Auto-detected from filename if omitted."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would be added without modifying any files"
    )
    args = parser.parse_args()

    patch_path = Path(args.input).resolve()
    if not patch_path.exists():
        print(f"ERROR: Patch file not found: {patch_path}")
        sys.exit(1)

    country = args.country or detect_country(patch_path)
    if not country:
        print("ERROR: Could not detect country code from filename.")
        print("       Please specify it with -c (e.g. -c BE)")
        sys.exit(1)

    country = country.upper()
    apply_patch(patch_path, country, args.dry_run)


if __name__ == "__main__":
    main()
