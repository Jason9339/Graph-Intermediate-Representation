#!/usr/bin/env python3
"""
Convert all diagrams from all formats to unified IR output.

This script processes all diagram formats (Mermaid, TikZ, Graphviz)
and outputs everything to a unified 'output/' directory with clear
subdirectories for each format.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from convert import batch_convert


def main():
    """Convert all diagram formats to IR."""
    print("=" * 70)
    print("CONVERTING ALL DIAGRAMS TO IR")
    print("=" * 70)

    unified_output = PROJECT_ROOT / "output"
    unified_output.mkdir(parents=True, exist_ok=True)

    formats = [
        ("mermaid", PROJECT_ROOT / "data" / "mermaid", unified_output / "mermaid"),
        ("tikz", PROJECT_ROOT / "data" / "latex", unified_output / "tikz"),
        ("graphviz", PROJECT_ROOT / "data" / "graphviz", unified_output / "graphviz"),
    ]

    all_stats = {}

    for format_name, input_dir, output_dir in formats:
        print(f"\n{'=' * 70}")
        print(f"Processing {format_name.upper()} diagrams")
        print(f"{'=' * 70}")

        if not input_dir.exists():
            print(f"⚠ Skipping: {input_dir} does not exist")
            continue

        try:
            summary = batch_convert(input_dir, output_dir, format_name, save_svg=True)
            all_stats[format_name] = summary["stats"]
        except Exception as e:
            print(f"✗ Failed to process {format_name}: {e}")
            all_stats[format_name] = {"error": str(e)}

    # Print overall summary
    print("\n" + "=" * 70)
    print("OVERALL SUMMARY")
    print("=" * 70)

    total_files = 0
    total_success = 0
    total_failed = 0

    for format_name, stats in all_stats.items():
        if "error" in stats:
            print(f"{format_name.upper()}: Error - {stats['error']}")
        else:
            print(f"{format_name.upper()}:")
            print(f"  Total: {stats['total']}, Success: {stats['success']}, Failed: {stats['failed']}")
            total_files += stats["total"]
            total_success += stats["success"]
            total_failed += stats["failed"]

    print(f"\nGRAND TOTAL:")
    print(f"  Files: {total_files}")
    print(f"  Success: {total_success}")
    print(f"  Failed: {total_failed}")

    print(f"\n✓ All outputs saved to: {unified_output}/")
    print(f"  - {unified_output}/mermaid/")
    print(f"  - {unified_output}/tikz/")
    print(f"  - {unified_output}/graphviz/")


if __name__ == "__main__":
    main()
