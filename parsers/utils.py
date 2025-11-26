"""Shared utilities and lightweight data models for diagram parsers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_TRIPLE_QUOTE_PATTERN = re.compile(r"(?:[rubf]|rb|br|fr|rf)?(\"\"\"|''')(.*?)(\1)", re.DOTALL)
_TIKZ_ENV_PATTERN = re.compile(r"\\begin\{tikzpicture\}(.*?)\\end\{tikzpicture\}", re.DOTALL)
_NUMERIC_PATTERN = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


@dataclass
class IRNode:
    node_id: str
    label: str = ""
    shape: Optional[str] = None
    color: Optional[str] = None
    fill_color: Optional[str] = None
    style: Optional[str] = None
    width: Optional[float] = None
    height: Optional[float] = None
    position: Optional[Dict[str, float]] = None
    stroke_width: Optional[float] = None
    text_color: Optional[str] = None
    font_size: Optional[float] = None
    font_weight: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.node_id,
            "label": self.label,
            "shape": self.shape,
            "color": self.color,
            "fillColor": self.fill_color,
            "style": self.style,
            "width": self.width,
            "height": self.height,
            "position": self.position,
            "stroke_width": self.stroke_width,
            "text_color": self.text_color,
            "font_size": self.font_size,
            "font_weight": self.font_weight,
            "metadata": self.metadata,
        }


@dataclass
class IREdge:
    source: str
    target: str
    directed: bool = True
    label: str = ""
    style: Optional[str] = None
    color: Optional[str] = None
    arrow_head: Optional[str] = None
    weight: Optional[float] = None
    stroke_width: Optional[float] = None
    dash: Optional[List[float]] = None
    metadata: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "source": self.source,
            "target": self.target,
            "directed": self.directed,
            "label": self.label,
            "style": self.style,
            "color": self.color,
            "arrowHead": self.arrow_head,
            "weight": self.weight,
            "stroke_width": self.stroke_width,
            "dash": self.dash,
            "metadata": self.metadata,
        }


@dataclass
class IRGroup:
    group_id: str
    label: str = ""
    nodes: List[str] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)
    style: Optional[str] = None
    color: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.group_id,
            "label": self.label,
            "nodes": self.nodes,
            "groups": self.groups,
            "style": self.style,
            "color": self.color,
            "metadata": self.metadata,
        }


def extract_triple_quoted_strings(text: str) -> List[str]:
    """Return triple-quoted string literals embedded in ``text``."""

    return [match.group(2) for match in _TRIPLE_QUOTE_PATTERN.finditer(text)]


def strip_latex_preamble(tex: str) -> Tuple[str, str, str]:
    """Split LaTeX source into preamble, document body, and tikzpicture content."""

    clean = tex.replace("\r\n", "\n").replace("\r", "\n")
    document_split = clean.split("\\begin{document}", 1)
    if len(document_split) == 2:
        preamble, rest = document_split
        body = rest.split("\\end{document}", 1)[0]
    else:
        preamble = ""
        body = clean
    tikz_match = _TIKZ_ENV_PATTERN.search(body)
    tikz_body = tikz_match.group(1).strip() if tikz_match else body.strip()
    tikz_body = _strip_leading_tikz_options(tikz_body)
    return preamble.strip(), body.strip(), tikz_body


def _strip_leading_tikz_options(content: str) -> str:
    stripped = content.lstrip()
    if not stripped.startswith("["):
        return content.strip()
    depth = 0
    end_index = None
    for idx, ch in enumerate(stripped):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end_index = idx + 1
                break
    if end_index is None:
        return content.strip()
    return stripped[end_index:].lstrip()


def extract_tikzpicture_options(body: str) -> Optional[str]:
    token = "\\begin{tikzpicture}"
    start = body.find(token)
    if start == -1:
        return None
    index = start + len(token)
    while index < len(body) and body[index].isspace():
        index += 1
    if index >= len(body) or body[index] != "[":
        return None
    index += 1
    depth = 1
    option_chars: List[str] = []
    while index < len(body) and depth > 0:
        ch = body[index]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                break
        option_chars.append(ch)
        index += 1
    if depth != 0:
        return None
    return "".join(option_chars)


def normalize_mermaid(code: str) -> List[str]:
    """Normalize Mermaid text into a list of lines without trailing whitespace."""

    text = code.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("\ufeff"):
        text = text[1:]
    return [line.rstrip() for line in text.split("\n")]


def _parse_dash(value) -> Optional[List[float]]:
    """Parse dash pattern from string/list/tuple to a list of floats."""

    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        try:
            result = [float(v) for v in value if v is not None]
            return result or None
        except (TypeError, ValueError):
            return None
    if isinstance(value, str):
        matches = _NUMERIC_PATTERN.findall(value)
        if not matches:
            return None
        try:
            return [float(m) for m in matches]
        except ValueError:
            return None
    return None


def _style_to_dash(style: Optional[str]) -> Optional[List[float]]:
    """Return a default dash array for common style keywords."""

    if not style:
        return None
    style_lower = style.lower()
    if "dashed" in style_lower:
        return [6, 4]
    if "dotted" in style_lower:
        return [2, 2]
    return None


def build_minimal_ir(
    title: str,
    orientation: Optional[str],
    nodes: List[Dict[str, object]],
    edges: List[Dict[str, object]],
    groups: List[Dict[str, object]],
    extras: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """
    Convert normalized IR dictionaries to the minimal IR format:

    - Top-level: title, orientation, nodes, edges, groups
    - Nodes: id, label, shape, pos, size, fill, stroke, strokeWidth, class
    - Edges: from, to, label, arrow, stroke, strokeWidth, dash
    """

    minimal_nodes: List[Dict[str, object]] = []
    for node in nodes:
        node_id = node.get("id")
        if not node_id:
            continue
        entry: Dict[str, object] = {"id": node_id}

        label = node.get("label")
        if label:
            entry["label"] = label

        shape = node.get("shape")
        if shape:
            entry["shape"] = shape

        pos = node.get("pos")
        if not pos and isinstance(node.get("position"), dict):
            pos_obj = node["position"]
            pos = [pos_obj.get("x"), pos_obj.get("y")]
        if pos:
            entry["pos"] = pos

        size = node.get("size")
        if not size and "width" in node and "height" in node:
            width = node.get("width")
            height = node.get("height")
            if width is not None and height is not None:
                size = [width, height]
        if size:
            entry["size"] = size

        for key in ("fill", "stroke", "strokeWidth", "dash"):
            if key in node and node[key] is not None:
                entry[key] = node[key]

        class_name = node.get("class")
        if not class_name:
            classes = node.get("classes")
            if isinstance(classes, list) and classes:
                class_name = classes[0]
        if class_name:
            entry["class"] = class_name

        # Preserve small set of drawing-relevant hints if present
        for hint_key in ("kind", "notePosition", "participants", "alias", "layoutHints"):
            if hint_key in node:
                entry[hint_key] = node[hint_key]

        minimal_nodes.append(entry)

    minimal_edges: List[Dict[str, object]] = []
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        entry: Dict[str, object] = {
            "from": source,
            "to": target,
            "arrow": bool(edge.get("directed", True)),
        }

        label = edge.get("label")
        if label:
            entry["label"] = label

        if edge.get("stroke") is not None:
            entry["stroke"] = edge["stroke"]
        if edge.get("strokeWidth") is not None:
            entry["strokeWidth"] = edge["strokeWidth"]

        dash = edge.get("dash")
        if dash is None:
            dash = _style_to_dash(edge.get("style"))
        dash = _parse_dash(dash)
        if dash:
            entry["dash"] = dash

        for hint_key in ("kind", "termination", "arrowToken"):
            if hint_key in edge:
                entry[hint_key] = edge[hint_key]

        minimal_edges.append(entry)

    minimal_groups: List[Dict[str, object]] = []
    for group in groups:
        group_id = group.get("id")
        if not group_id:
            continue
        entry: Dict[str, object] = {"id": group_id}
        if group.get("label"):
            entry["label"] = group["label"]
        if group.get("nodes"):
            entry["nodes"] = group["nodes"]
        if group.get("groups"):
            entry["groups"] = group["groups"]

        fill_value = group.get("fill")
        if fill_value is None and group.get("color"):
            fill_value = group.get("color")
        if fill_value is not None:
            entry["fill"] = fill_value

        if group.get("boundingBox"):
            entry["boundingBox"] = group["boundingBox"]

        minimal_groups.append(entry)

    ir: Dict[str, object] = {
        "title": title or "Untitled",
        "orientation": orientation or "TB",
        "nodes": minimal_nodes,
        "edges": minimal_edges,
    }
    if minimal_groups:
        ir["groups"] = minimal_groups
    if extras:
        for key, value in extras.items():
            if value is not None:
                ir[key] = value
    return ir
