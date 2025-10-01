"""Generate TikZ code from IR."""

from __future__ import annotations

from math import sqrt
from typing import Any, Dict, List

from .utils import (
    escape_label,
    hex_to_tikz_color,
    shape_map_to_tikz,
    style_map_to_tikz,
)


def _node_options(node: Dict[str, Any]) -> str:
    options: List[str] = [shape_map_to_tikz(node.get("shape"))]
    if node.get("color"):
        options.append(f'draw={hex_to_tikz_color(node["color"])}')
    if node.get("fillColor"):
        options.append(f'fill={hex_to_tikz_color(node["fillColor"])}')
    options.extend(style_map_to_tikz(node.get("style")))
    return ", ".join(filter(None, options))


def _edge_options(edge: Dict[str, Any]) -> str:
    options: List[str] = []
    if edge.get("color"):
        options.append(f'draw={hex_to_tikz_color(edge["color"])}')
    options.extend(style_map_to_tikz(edge.get("style")))
    return ", ".join(filter(None, options))


def generate_tikz(ir: Dict[str, Any]) -> str:
    graph = ir.get("graph", {})
    nodes: List[Dict[str, Any]] = ir.get("nodes", [])
    edges: List[Dict[str, Any]] = ir.get("edges", [])

    directed = bool(graph.get("directed", True))
    arrow = "->" if directed else "-"

    header = [
        "\\begin{tikzpicture}[",
        f"{arrow},",
        ">=stealth,",
        "node distance=2.2cm,",
        "every node/.style={draw,thick,minimum size=6mm,inner sep=3pt,align=center},",
        "every edge/.style={draw,thick}",
        "]\n",
    ]

    manual_positions = any("position" in node for node in nodes)
    node_commands: List[str] = []
    declared = set()

    columns = max(1, int(sqrt(len(nodes)))) if not manual_positions and nodes else 1

    for index, node in enumerate(nodes):
        node_id = node.get("id", f"node_{index}")
        label = escape_label(node.get("label", node_id)).replace("\n", "\\\\")
        options = _node_options(node)
        if "position" in node:
            pos = node["position"]
            x = pos.get("x", 0) / 50.0
            y = -pos.get("y", 0) / 50.0
            node_commands.append(f'\\node[{options}] ({node_id}) at ({x:.2f},{y:.2f}) {{{label}}};')
        else:
            col = index % columns
            row = index // columns
            node_commands.append(f'\\node[{options}] ({node_id}) at ({col*3.0:.2f},{-row*2.2:.2f}) {{{label}}};')
        declared.add(node_id)

    edge_commands: List[str] = []
    for edge in edges:
        src = edge.get("source")
        dst = edge.get("target")
        if not src or not dst or src not in declared or dst not in declared:
            continue
        options = _edge_options(edge)
        opt_str = f'[{options}]' if options else ""
        label = edge.get("label")
        if label:
            safe_label = escape_label(label).replace("\n", "\\\\")
            edge_commands.append(f'\\path ({src}) edge{opt_str} node[above] {{{safe_label}}} ({dst});')
        else:
            edge_commands.append(f'\\path ({src}) edge{opt_str} ({dst});')

    footer = ["\\end{tikzpicture}\n"]
    return "".join(header + node_commands + edge_commands + footer)
