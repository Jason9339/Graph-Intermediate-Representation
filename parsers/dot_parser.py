"""Graphviz parser with Phase 1 preprocessing for Python-based DOT builders."""

from __future__ import annotations

import ast
import csv
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .utils import IRNode, IREdge, extract_triple_quoted_strings

DEFAULT_DOT_ORIENTATION = "LR"

_IMPORT_PATTERN = re.compile(r"^(?:from\s+\S+\s+import\s+\S+|import\s+\S+)")
_COMMENT_PATTERN = re.compile(r"comment\s*=\s*(['\"])(.+?)\1")
_RANKDIR_PATTERN = re.compile(r"rankdir\s*=\s*['\"]([A-Z]{2})['\"]")
_LAYOUT_PATTERN = re.compile(r"layout\s*=\s*['\"]([a-zA-Z0-9_]+)['\"]")


def _literal_or_source(code: str, node: ast.AST) -> Tuple[str, bool]:
    try:
        value = ast.literal_eval(node)
        if isinstance(value, (str, int, float, bool)):
            return str(value), True
    except Exception:  # noqa: BLE001 - literal_eval may raise many exceptions
        pass
    try:
        source = ast.get_source_segment(code, node)
    except Exception:  # pragma: no cover - fallback for older Python versions
        source = None
    if source is None and hasattr(ast, "unparse"):
        try:
            source = ast.unparse(node)
        except Exception:  # noqa: BLE001
            source = None
    return (source or ""), False


def _collect_dot_calls(code: str) -> Tuple[List[IRNode], List[IREdge]]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return [], []

    nodes: Dict[str, IRNode] = {}
    edges: List[IREdge] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if not isinstance(func.value, ast.Name) or func.value.id != "dot":
            continue

        if func.attr == "node" and node.args:
            node_id_text, id_literal = _literal_or_source(code, node.args[0])
            label_text = ""
            label_literal = False
            if len(node.args) >= 2:
                label_text, label_literal = _literal_or_source(code, node.args[1])
            metadata: Dict[str, Any] = {}
            if not id_literal:
                metadata["id_expr"] = node_id_text
            if node.keywords:
                props = {}
                for kw in node.keywords:
                    if kw.arg is None:
                        continue
                    value_text, value_literal = _literal_or_source(code, kw.value)
                    props[kw.arg] = value_text
                    if not value_literal:
                        metadata.setdefault("dynamic_properties", []).append(kw.arg)
                if props:
                    metadata["properties"] = props
            label_value = label_text if label_literal else ""
            node_entry = IRNode(
                node_id=node_id_text,
                label=label_value or node_id_text,
                metadata=metadata,
            )
            nodes[node_entry.node_id] = node_entry

        elif func.attr == "edge" and len(node.args) >= 2:
            src_text, src_literal = _literal_or_source(code, node.args[0])
            dst_text, dst_literal = _literal_or_source(code, node.args[1])
            label_text = ""
            label_literal = False
            if len(node.args) >= 3:
                label_text, label_literal = _literal_or_source(code, node.args[2])
            metadata: Dict[str, Any] = {}
            if not src_literal or not dst_literal:
                metadata["dynamic_nodes"] = True
            if node.keywords:
                props = {}
                for kw in node.keywords:
                    if kw.arg is None:
                        continue
                    value_text, value_literal = _literal_or_source(code, kw.value)
                    props[kw.arg] = value_text
                    if not value_literal:
                        metadata.setdefault("dynamic_properties", []).append(kw.arg)
                if props:
                    metadata["properties"] = props
            node_a = nodes.setdefault(src_text, IRNode(node_id=src_text, label=src_text, metadata={}))
            node_b = nodes.setdefault(dst_text, IRNode(node_id=dst_text, label=dst_text, metadata={}))
            edges.append(
                IREdge(
                    source=node_a.node_id,
                    target=node_b.node_id,
                    directed=True,
                    label=label_text if label_literal else "",
                    metadata=metadata,
                )
            )

    return list(nodes.values()), edges



def _collect_imports(code: str) -> List[str]:
    imports: List[str] = []
    for line in code.splitlines():
        stripped = line.strip()
        if _IMPORT_PATTERN.match(stripped):
            imports.append(stripped)
    return imports


def parse_dot_code(code: str, source_id: str) -> Dict[str, Any]:
    """Generate an IR skeleton from Python Graphviz helper code."""

    metadata: Dict[str, Any] = {
        "source_id": source_id,
        "parser": "dot",
        "original_code": code,
    }
    imports = _collect_imports(code)
    if imports:
        metadata["imports"] = imports
    embedded_strings = extract_triple_quoted_strings(code)
    if embedded_strings:
        metadata["embedded_strings"] = embedded_strings

    directed = "graphviz.Graph" not in code
    title = source_id
    comment_match = _COMMENT_PATTERN.search(code)
    if comment_match:
        title = comment_match.group(2)

    orientation = DEFAULT_DOT_ORIENTATION
    rankdir_match = _RANKDIR_PATTERN.search(code)
    if rankdir_match:
        orientation = rankdir_match.group(1)

    layout = "hierarchical"
    layout_match = _LAYOUT_PATTERN.search(code)
    if layout_match:
        layout = layout_match.group(1)

    metadata_hints: Dict[str, Any] = {}
    if rankdir_match:
        metadata_hints["rankdir"] = rankdir_match.group(1)
    if layout_match:
        metadata_hints["layout"] = layout_match.group(1)
    if metadata_hints:
        metadata["graphviz_hints"] = metadata_hints

    parsed_nodes, parsed_edges = _collect_dot_calls(code)
    nodes = [node.to_dict() for node in parsed_nodes]
    edges = [edge.to_dict() for edge in parsed_edges]

    return {
        "graph": {
            "title": title,
            "directed": directed,
            "orientation": orientation,
            "layout": layout,
            "metadata": metadata,
        },
        "nodes": nodes,
        "edges": edges,
        "groups": [],
    }


def load_sample_irs(csv_path: Path, limit: int = 5) -> List[Dict[str, Any]]:
    """Return placeholder IRs from the DOT CSV sample."""

    documents: List[Dict[str, Any]] = []
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            documents.append(parse_dot_code(row.get("code", ""), row.get("id", "")))
            if index + 1 >= limit:
                break
    return documents
