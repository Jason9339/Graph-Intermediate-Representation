#!/usr/bin/env python3
"""Standalone CLI for converting IR JSON into diagram code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from generators import generate_dot, generate_mermaid, generate_tikz

FORMAT_TO_GENERATOR = {
    "tikz": generate_tikz,
    "dot": generate_dot,
    "mermaid": generate_mermaid,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Diagram IR (JSON) to TikZ / Graphviz DOT / Mermaid code.")
    parser.add_argument("--in", dest="infile", required=True, help="Path to IR JSON file")
    parser.add_argument("--fmt", dest="fmt", required=True, choices=sorted(FORMAT_TO_GENERATOR), help="Output format")
    args = parser.parse_args()

    ir = json.loads(Path(args.infile).read_text(encoding="utf-8"))
    code = FORMAT_TO_GENERATOR[args.fmt](ir)
    print(code, end="")


if __name__ == "__main__":
    main()
