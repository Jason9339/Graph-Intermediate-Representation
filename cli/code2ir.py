"""CLI entry point for converting code snippets to the unified IR."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parsers import (
    parse_dot_code,
    parse_mermaid_code,
    parse_tikz_code,
)

ParserFn = Callable[[str, str], Dict[str, object]]

FORMAT_TO_PARSER: Dict[str, ParserFn] = {
    "tikz": parse_tikz_code,
    "dot": parse_dot_code,
    "mermaid": parse_mermaid_code,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert diagram code to IR JSON.")
    parser.add_argument("--in", dest="input_path", required=True, help="Path to the code file")
    parser.add_argument(
        "--fmt",
        dest="format",
        required=True,
        choices=sorted(FORMAT_TO_PARSER),
        help="Input format",
    )
    parser.add_argument("--id", dest="source_id", default=None, help="Optional override for the IR graph title")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    parser_fn = FORMAT_TO_PARSER[args.format]
    input_path = Path(args.input_path)
    code = input_path.read_text(encoding="utf-8")
    source_id = args.source_id or input_path.stem
    ir_doc = parser_fn(code, source_id)
    print(json.dumps(ir_doc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
