"""TikZ parser with Phase 1 preprocessing and metadata capture."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .utils import IRNode, IREdge, strip_latex_preamble

DEFAULT_TIKZ_ORIENTATION = "LR"

_LIB_PATTERN = re.compile(r"\\usetikzlibrary\{([^}]*)\}")
_BEGIN_TIKZ_PATTERN = re.compile(r"\\begin\{tikzpicture\}(?:\[([^]]+)\])?")
_NODE_PATTERN = re.compile(r"\\node[^;]*;", re.MULTILINE)
_DRAW_PATTERN = re.compile(r"\\draw[^;]*;", re.MULTILINE)
_PATH_PATTERN = re.compile(r"\\path[^;]*;", re.MULTILINE)
_EDGE_NODE_LABEL_PATTERN = re.compile(r"node\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")
_EDGE_KEYWORD_PATTERN = re.compile(
    r"\((?P<src>[^)]+)\)\s*edge(?:\[(?P<opts>[^\]]+)\])?\s*(?:node\s*(?:\[[^\]]*\])?\s*\{(?P<label>[^}]*)\})?\s*\((?P<dst>[^)]+)\)"
)

SHAPE_KEYWORDS = {
    "rectangle": "rect",
    "circle": "circle",
    "ellipse": "ellipse",
    "diamond": "diamond",
    "star": "star",
    "cloud": "cloud",
}


def _clean_text(text: str) -> str:
    value = text.strip()
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        value = value[1:-1]
    return value


def _extract_libraries(preamble: str) -> List[str]:
    libs: List[str] = []
    for match in _LIB_PATTERN.finditer(preamble):
        for item in match.group(1).split(","):
            name = item.strip()
            if name:
                libs.append(name)
    return libs


def _split_options(option_text: str) -> List[str]:
    return [opt.strip() for opt in option_text.split(",") if opt.strip()]


def _parse_node_statement(statement: str) -> Optional[IRNode]:
    label_match = re.search(r"\{([^}]*)\}", statement)
    id_match = re.search(r"\(([^)]+)\)", statement)
    if not label_match or not id_match:
        return None

    node_id = id_match.group(1).strip()
    label = _clean_text(label_match.group(1))

    options_segment = statement[: label_match.start()]
    option_tokens: List[str] = []
    for match in re.finditer(r"\[([^\]]+)\]", options_segment):
        option_tokens.extend(_split_options(match.group(1)))

    shape: Optional[str] = None
    color: Optional[str] = None
    fill_color: Optional[str] = None
    style: Optional[str] = None
    metadata: Dict[str, Any] = {}

    for token in option_tokens:
        lower = token.lower()
        if lower in SHAPE_KEYWORDS:
            shape = SHAPE_KEYWORDS[lower]
        elif lower == "draw":
            style = (style + ",draw" if style else "draw")
        elif lower == "dashed":
            style = "dashed"
        elif lower.startswith("draw="):
            color = token.split("=", 1)[1]
        elif lower.startswith("fill="):
            fill_color = token.split("=", 1)[1]
        elif "=" in token:
            key, value = token.split("=", 1)
            metadata.setdefault("options", {})[key.strip()] = value.strip()
        else:
            metadata.setdefault("flags", []).append(token)

    node = IRNode(
        node_id=node_id,
        label=label,
        shape=shape,
        color=color,
        fill_color=fill_color,
        style=style,
        metadata=metadata,
    )
    return node


def _ensure_node(nodes: Dict[str, IRNode], node_id: str) -> IRNode:
    node = nodes.get(node_id)
    if node is None:
        node = IRNode(node_id=node_id, label=node_id, shape=None, metadata={})
        nodes[node_id] = node
    return node


def _parse_draw_statement(statement: str, nodes: Dict[str, IRNode], default_directed: bool) -> List[IREdge]:
    edges: List[IREdge] = []
    before_semicolon = statement.rstrip(";")
    option_tokens: List[str] = []
    for match in re.finditer(r"\[([^\]]+)\]", before_semicolon):
        option_tokens.extend(_split_options(match.group(1)))

    style: Optional[str] = None
    color: Optional[str] = None
    metadata: Dict[str, Any] = {}

    for token in option_tokens:
        lower = token.lower()
        if lower == "dashed":
            style = "dashed"
        elif lower.startswith("bend"):
            metadata.setdefault("geometry", []).append(token)
        elif lower.startswith("color=") or lower.startswith("draw="):
            color = token.split("=", 1)[1]
        elif lower.startswith("style="):
            metadata.setdefault("styles", []).append(token.split("=", 1)[1])

    keyword_edges = list(_EDGE_KEYWORD_PATTERN.finditer(before_semicolon))
    if keyword_edges:
        for match in keyword_edges:
            src = match.group("src").strip()
            dst = match.group("dst").strip()
            label = match.group("label") or ""
            opts = match.group("opts") or ""
            opts_tokens = _split_options(opts) if opts else []
            edge_style = style
            edge_color = color
            edge_metadata = metadata.copy() if metadata else {}
            directed = default_directed or "->" in before_semicolon or any("->" in opt for opt in opts_tokens)
            for opt in opts_tokens:
                lower = opt.lower()
                if lower == "dashed":
                    edge_style = "dashed"
                elif lower.startswith("bend"):
                    edge_metadata.setdefault("geometry", []).append(opt)
                elif lower.startswith("color=") or lower.startswith("draw="):
                    edge_color = opt.split("=", 1)[1]
            source_node = _ensure_node(nodes, src)
            target_node = _ensure_node(nodes, dst)
            edges.append(
                IREdge(
                    source=source_node.node_id,
                    target=target_node.node_id,
                    directed=directed,
            label=_clean_text(label),
                    style=edge_style,
                    color=edge_color,
                    metadata=edge_metadata,
                )
            )
        return edges

    refs = [ref.strip() for ref in re.findall(r"\(([^)]+)\)", before_semicolon)]
    node_refs = [ref for ref in refs if ref and "," not in ref and " " not in ref]

    if len(node_refs) < 2:
        return edges

    label = ""
    label_match = _EDGE_NODE_LABEL_PATTERN.search(before_semicolon)
    if label_match:
        label = label_match.group(1).strip()

    directed = default_directed or "->" in before_semicolon or any(token.strip().startswith("->") for token in option_tokens)

    for source_id, target_id in zip(node_refs, node_refs[1:]):
        source_node = _ensure_node(nodes, source_id)
        target_node = _ensure_node(nodes, target_id)
        edges.append(
            IREdge(
                source=source_node.node_id,
                target=target_node.node_id,
                directed=directed,
                label=label,
                style=style,
                color=color,
                metadata=metadata.copy() if metadata else {},
            )
        )

    return edges


def _extract_graph_elements(tikz_body: str, default_directed: bool) -> Tuple[List[IRNode], List[IREdge]]:
    nodes: Dict[str, IRNode] = {}
    edges: List[IREdge] = []

    for match in _NODE_PATTERN.finditer(tikz_body):
        node = _parse_node_statement(match.group(0))
        if node:
            nodes[node.node_id] = node

    for match in _DRAW_PATTERN.finditer(tikz_body):
        edges.extend(_parse_draw_statement(match.group(0), nodes, default_directed))

    for match in _PATH_PATTERN.finditer(tikz_body):
        edges.extend(_parse_draw_statement(match.group(0), nodes, default_directed))

    return [node.to_dict() for node in nodes.values()], [edge.to_dict() for edge in edges]


def parse_tikz_code(code: str, source_id: str) -> Dict[str, Any]:
    """Return an IR skeleton enriched with LaTeX metadata."""

    preamble, body, tikz_body = strip_latex_preamble(code)
    metadata: Dict[str, Any] = {
        "source_id": source_id,
        "parser": "tikz",
        "original_code": code,
    }
    libraries = _extract_libraries(preamble)
    if libraries:
        metadata["libraries"] = libraries
    if preamble:
        metadata["preamble"] = preamble
    begin_match = _BEGIN_TIKZ_PATTERN.search(body)
    if begin_match and begin_match.group(1):
        metadata["tikz_options"] = begin_match.group(1)
    metadata["tikzpicture"] = tikz_body

    directed = any(token in tikz_body for token in ("->", "-->", "<->", "rightarrow"))

    nodes, edges = _extract_graph_elements(tikz_body, directed)

    return {
        "graph": {
            "title": source_id,
            "directed": directed,
            "orientation": DEFAULT_TIKZ_ORIENTATION,
            "layout": "hierarchical",
            "metadata": metadata,
        },
        "nodes": nodes,
        "edges": edges,
        "groups": [],
    }


def load_sample_irs(csv_path: Path, limit: int = 5) -> List[Dict[str, Any]]:
    """Read up to ``limit`` rows from a TikZ CSV file and return placeholder IRs."""

    documents: List[Dict[str, Any]] = []
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            documents.append(parse_tikz_code(row.get("code", ""), row.get("id", "")))
            if index + 1 >= limit:
                break
    return documents
