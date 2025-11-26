#!/usr/bin/env python3
"""Verify conversion results for all diagram formats."""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"


def format_size(bytes_size):
    """Format byte size in human-readable format."""
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    else:
        return f"{bytes_size / (1024 * 1024):.1f} MB"


def load_summary(format_name):
    """Load conversion summary for a format."""
    summary_file = OUTPUT_DIR / format_name / "conversion_summary.json"
    if not summary_file.exists():
        return None

    with open(summary_file) as f:
        return json.load(f)


def print_format_summary(format_name, summary):
    """Print summary for a specific format."""
    if not summary:
        print(f"\n⚠ No data for {format_name}")
        return

    results = summary["results"]
    stats = summary["stats"]

    print(f"\n{'=' * 74}")
    print(f"  {format_name.upper()} - Conversion Summary")
    print(f"{'=' * 74}")
    print(f"  Total:    {stats['total']} files")
    print(f"  Success:  {stats['success']} files")
    print(f"  Failed:   {stats['failed']} files")
    print(f"  Empty:    {stats.get('empty', 0)} files")

    if results:
        print(f"\n  Top 5 Results:")
        print(f"  {'ID':<25} {'Nodes':<8} {'Edges':<8} {'Groups':<8} {'Position':<10}")
        print(f"  {'-' * 70}")

        for result in results[:5]:
            file_id = result["id"][:24]
            nodes = result["nodes"]
            edges = result.get("edges", 0)
            groups = result.get("groups", 0)
            pos_cov = result.get("position_coverage", "N/A")

            print(f"  {file_id:<25} {nodes:<8} {edges:<8} {groups:<8} {pos_cov:<10}")


def main():
    """Display verification results for all formats."""
    print("╔" + "=" * 72 + "╗")
    print("║" + " " * 20 + "CONVERSION VERIFICATION REPORT" + " " * 22 + "║")
    print("╚" + "=" * 72 + "╝")

    formats = ["mermaid", "tikz", "graphviz"]
    all_summaries = {}

    for format_name in formats:
        summary = load_summary(format_name)
        if summary:
            all_summaries[format_name] = summary
            print_format_summary(format_name, summary)
        else:
            print(f"\n⚠ No results found for {format_name}")
            print(f"  Run: python convert_all.py")

    # Overall totals
    if all_summaries:
        print(f"\n{'=' * 74}")
        print("  OVERALL TOTALS")
        print(f"{'=' * 74}")

        grand_total = 0
        grand_success = 0
        grand_failed = 0
        grand_nodes = 0
        grand_edges = 0

        for format_name, summary in all_summaries.items():
            stats = summary["stats"]
            grand_total += stats["total"]
            grand_success += stats["success"]
            grand_failed += stats["failed"]

            # Count nodes and edges
            for result in summary["results"]:
                grand_nodes += result["nodes"]
                grand_edges += result.get("edges", 0)

        print(f"  Total files:  {grand_total}")
        print(f"  Success:      {grand_success}")
        print(f"  Failed:       {grand_failed}")
        print(f"  Total nodes:  {grand_nodes}")
        print(f"  Total edges:  {grand_edges}")
        print()

        coverage_pct = (grand_success / grand_total * 100) if grand_total > 0 else 0
        print(f"  ✓ Overall success rate: {coverage_pct:.1f}%")
    else:
        print("\n⚠ No conversion results found.")
        print("  Run: python convert_all.py")

    print(f"\n📁 Output directory: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
