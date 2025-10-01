"""CLI entry point for converting IR JSON back to diagram code."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from generators import generate_dot, generate_mermaid, generate_tikz

GeneratorFn = Callable[[Dict[str, object]], str]

FORMAT_TO_GENERATOR: Dict[str, GeneratorFn] = {
    "tikz": generate_tikz,
    "dot": generate_dot,
    "mermaid": generate_mermaid,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert IR JSON to diagram code.")
    parser.add_argument("--in", dest="input_path", required=True, help="Path to the IR JSON file")
    parser.add_argument(
        "--fmt",
        dest="format",
        required=True,
        choices=sorted(FORMAT_TO_GENERATOR),
        help="Output format",
    )
    parser.add_argument(
        "--out",
        dest="output_path",
        default=None,
        help="Optional path to write the generated code; defaults to stdout",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    generator_fn = FORMAT_TO_GENERATOR[args.format]
    input_path = Path(args.input_path)
    with input_path.open("r", encoding="utf-8") as handle:
        ir_doc = json.load(handle)
    result = generator_fn(ir_doc)
    if args.output_path:
        Path(args.output_path).write_text(result, encoding="utf-8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
