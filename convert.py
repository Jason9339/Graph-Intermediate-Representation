#!/usr/bin/env python3
"""
Unified diagram-to-IR converter.

Converts diagram source code (Mermaid, TikZ, Graphviz) to a clean,
human-readable intermediate representation (IR) in JSON format.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parsers import parse_mermaid_code, parse_tikz_code, parse_dot_code


def detect_format(code: str, file_path: Optional[Path] = None) -> Optional[str]:
    """Auto-detect diagram format from code or file extension."""
    if file_path:
        suffix = file_path.suffix.lower()
        if suffix in ['.mmd', '.mermaid']:
            return 'mermaid'
        elif suffix in ['.tex', '.tikz']:
            return 'tikz'
        elif suffix in ['.dot', '.gv', '.py']:
            return 'graphviz'

    # Content-based detection
    code_lower = code.lower().strip()

    # Mermaid patterns
    mermaid_keywords = ['flowchart', 'sequencediagram', 'mindmap', 'graph td', 'graph lr']
    if any(kw in code_lower for kw in mermaid_keywords):
        return 'mermaid'

    # TikZ patterns
    if '\\begin{tikzpicture}' in code or '\\tikz' in code:
        return 'tikz'

    # Graphviz patterns
    if 'import graphviz' in code or 'from graphviz' in code:
        return 'graphviz'
    if code_lower.startswith('digraph') or code_lower.startswith('graph'):
        return 'graphviz'

    return None


def convert_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    format_type: Optional[str] = None,
    save_svg: bool = True
) -> Dict[str, Any]:
    """
    Convert a single diagram file to IR.

    Args:
        input_path: Path to input diagram file
        output_path: Path to output JSON file (default: same name with .json)
        format_type: Format type (mermaid/tikz/graphviz), auto-detect if None
        save_svg: Whether to save SVG file alongside JSON

    Returns:
        IR document as dictionary
    """
    # Read input
    code = input_path.read_text(encoding='utf-8')

    # Detect format if not specified
    if not format_type:
        format_type = detect_format(code, input_path)
        if not format_type:
            raise ValueError(f"Could not detect diagram format for {input_path}")

    # Set up output paths
    if not output_path:
        output_path = input_path.with_suffix('.json')

    svg_path = output_path.with_suffix('.svg') if save_svg else None
    source_id = input_path.stem

    # Parse based on format
    if format_type == 'mermaid':
        ir_doc = parse_mermaid_code(code, source_id, svg_output_path=str(svg_path) if svg_path else None)
    elif format_type == 'tikz':
        ir_doc = parse_tikz_code(code, source_id, svg_output_path=str(svg_path) if svg_path else None)
    elif format_type == 'graphviz':
        ir_doc = parse_dot_code(code, source_id, svg_output_path=str(svg_path) if svg_path else None)
    else:
        raise ValueError(f"Unsupported format: {format_type}")

    # Save JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(ir_doc, f, ensure_ascii=False, indent=2)

    return ir_doc


def batch_convert(
    input_dir: Path,
    output_dir: Path,
    format_type: str,
    save_svg: bool = True
) -> Dict[str, Any]:
    """
    Batch convert all diagrams in a directory.

    Args:
        input_dir: Input directory containing diagram files
        output_dir: Output directory for JSON and SVG files
        format_type: Format type (mermaid/tikz/graphviz)
        save_svg: Whether to save SVG files

    Returns:
        Summary statistics
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find input files
    if format_type == 'mermaid':
        pattern = '*.txt'
    elif format_type == 'tikz':
        pattern = '*.txt'
    elif format_type == 'graphviz':
        pattern = '*.py'
    else:
        raise ValueError(f"Unsupported format: {format_type}")

    input_files = sorted(input_dir.glob(pattern))

    if not input_files:
        print(f"No {format_type} files found in {input_dir}")
        return {"total": 0, "success": 0, "failed": 0}

    stats = {"total": 0, "success": 0, "failed": 0, "empty": 0}
    results = []

    print(f"Found {len(input_files)} {format_type} files")
    print("=" * 70)

    for input_file in input_files:
        file_id = input_file.stem
        stats["total"] += 1

        print(f"\n[{stats['total']}] Processing: {file_id}")

        try:
            # Read code
            code = input_file.read_text(encoding='utf-8')

            # Check if empty
            if not code.strip():
                print(f"  ⊘ Skipped: empty file")
                stats["empty"] += 1
                continue

            # Convert
            json_path = output_dir / f"{file_id}.json"
            svg_path = (output_dir / f"{file_id}.svg") if save_svg else None

            ir_doc = convert_file(input_file, json_path, format_type, save_svg)

            # Extract stats
            node_count = len(ir_doc["nodes"])
            edge_count = len(ir_doc["edges"])
            group_count = len(ir_doc.get("groups", []))
            nodes_with_pos = sum(1 for n in ir_doc["nodes"] if n.get("pos"))

            svg_exists = svg_path and svg_path.exists()

            # Determine status
            if node_count == 0:
                status = "⊘ Empty"
                stats["empty"] += 1
            else:
                status = "✓ Success"
                stats["success"] += 1

            # Print info
            print(f"  Nodes: {node_count}, Edges: {edge_count}, Groups: {group_count}")
            print(f"  Position coverage: {nodes_with_pos}/{node_count}")
            if svg_exists:
                print(f"  SVG: Yes ({svg_path.stat().st_size:,} bytes)")
            print(f"  {status}")

            results.append({
                "id": file_id,
                "nodes": node_count,
                "edges": edge_count,
                "groups": group_count,
                "position_coverage": f"{nodes_with_pos}/{node_count}",
                "svg": svg_exists,
            })

        except Exception as e:
            print(f"  ✗ Failed: {e}")
            stats["failed"] += 1

    # Save summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total: {stats['total']}, Success: {stats['success']}, Failed: {stats['failed']}, Empty: {stats['empty']}")

    summary = {"stats": stats, "results": results}
    summary_file = output_dir / "conversion_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\nOutput: {output_dir}")
    print(f"Summary: {summary_file}")

    return summary


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Convert diagram source code to IR JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Convert single file (auto-detect format)
  python convert.py diagram.mmd

  # Convert single file with explicit format
  python convert.py --format mermaid diagram.txt -o output.json

  # Batch convert directory
  python convert.py --batch data/mermaid --format mermaid -o output/

  # Convert without SVG
  python convert.py diagram.tex --no-svg
        '''
    )

    parser.add_argument('input', type=Path, help='Input file or directory')
    parser.add_argument('-o', '--output', type=Path, help='Output file or directory')
    parser.add_argument('-f', '--format', choices=['mermaid', 'tikz', 'graphviz'],
                        help='Diagram format (auto-detect if not specified)')
    parser.add_argument('-b', '--batch', action='store_true',
                        help='Batch convert all files in input directory')
    parser.add_argument('--no-svg', action='store_true',
                        help='Do not generate SVG files')

    args = parser.parse_args()

    try:
        if args.batch:
            # Batch mode
            if not args.input.is_dir():
                print(f"Error: {args.input} is not a directory")
                sys.exit(1)

            if not args.format:
                print("Error: --format is required for batch mode")
                sys.exit(1)

            output_dir = args.output or (PROJECT_ROOT / "output")
            batch_convert(args.input, output_dir, args.format, save_svg=not args.no_svg)
        else:
            # Single file mode
            if not args.input.is_file():
                print(f"Error: {args.input} is not a file")
                sys.exit(1)

            ir_doc = convert_file(args.input, args.output, args.format, save_svg=not args.no_svg)

            # Print result
            print(f"\n✓ Converted {args.input}")
            print(f"  Format: {args.format or detect_format(args.input.read_text(encoding='utf-8'), args.input)}")
            print(f"  Nodes: {len(ir_doc['nodes'])}")
            print(f"  Edges: {len(ir_doc['edges'])}")
            print(f"  Groups: {len(ir_doc.get('groups', []))}")
            print(f"  Orientation: {ir_doc.get('orientation')}")

            output_file = args.output or args.input.with_suffix('.json')
            print(f"  Output: {output_file}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
