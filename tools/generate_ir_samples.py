#!/usr/bin/env python3
"""Generate IR JSON samples for the first five entries of each code format."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Callable, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"

from parsers import parse_mermaid_code, parse_tikz_code

OUTPUT_DIR = PROJECT_ROOT / "out"
OUTPUT_DIR.mkdir(exist_ok=True)

Validator = Callable[[Dict[str, object]], None]


def validate_ir(doc: Dict[str, object]) -> None:
    assert isinstance(doc, dict), "IR must be a dictionary"
    assert "graph" in doc and "nodes" in doc and "edges" in doc and "groups" in doc, "Missing top-level keys"
    graph = doc["graph"]
    assert isinstance(graph, dict), "graph must be a dictionary"
    for key in ("title", "orientation", "layout"):
        assert key in graph, f"graph.{key} missing"
    assert isinstance(graph.get("title"), str)
    assert isinstance(graph.get("directed"), bool)
    assert isinstance(graph.get("metadata"), dict)
    assert isinstance(doc["nodes"], list)
    assert isinstance(doc["edges"], list)
    assert isinstance(doc["groups"], list)


def emit_samples(
    csv_path: Path,
    parser_fn: Callable[[str, str], Dict[str, object]],
    prefix: str,
    *,
    limit: int,
) -> None:
    target_dir = OUTPUT_DIR / prefix
    target_dir.mkdir(exist_ok=True)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            ir_doc = parser_fn(row.get("code", ""), row.get("id", f"{prefix}_{index}"))
            validate_ir(ir_doc)
            target = target_dir / f"{index + 1}.json"
            target.write_text(json.dumps(ir_doc, ensure_ascii=False, indent=2), encoding="utf-8")
            if index + 1 >= limit:
                break


def main() -> None:
    emit_samples(DATA_DIR / "cosyn_id_code_mermaid.csv", parse_mermaid_code, "mermaid", limit=10)
    emit_samples(DATA_DIR / "cosyn_id_code_latex.csv", parse_tikz_code, "latex", limit=5)


if __name__ == "__main__":
    main()
