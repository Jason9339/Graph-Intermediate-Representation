"""Generate Graphviz DOT code from IR."""

from __future__ import annotations

from typing import Any, Dict, List

from .utils import (
    arrow_map_to_dot,
    escape_label,
    hex_to_dot_color,
    orientation_to_rankdir,
    shape_map_to_dot,
    style_map_to_dot,
)


def generate_dot(ir: Dict[str, Any]) -> str:
    graph = ir.get("graph", {})
    nodes: List[Dict[str, Any]] = ir.get("nodes", [])
    edges: List[Dict[str, Any]] = ir.get("edges", [])
    groups: List[Dict[str, Any]] = ir.get("groups", [])

    directed = bool(graph.get("directed", True))
    rankdir = orientation_to_rankdir(graph.get("orientation", "TB"))
    header = "digraph G" if directed else "graph G"
    connector = "->" if directed else "--"

    lines: List[str] = [f"{header} {{"]
    lines.append(f"  rankdir={rankdir};")
    if graph.get("title"):
        lines.append(f'  labelloc="t"; label="{escape_label(graph["title"])}";')

    grouped_nodes = set()
    for group in groups:
        gid = group.get("id", "cluster")
        label = group.get("label", gid)
        lines.append(f"  subgraph cluster_{gid} {{")
        lines.append(f'    label="{escape_label(label)}";')
        if group.get("color"):
            lines.append(f'    color="{hex_to_dot_color(group["color"])}";')
        if group.get("fillColor"):
            lines.append('    style="filled";')
            lines.append(f'    fillcolor="{hex_to_dot_color(group["fillColor"])}";')
        for node_id in group.get("nodes", []):
            grouped_nodes.add(node_id)
            lines.append(f'    "{node_id}";')
        lines.append("  }")

    for node in nodes:
        attrs: List[str] = []
        attrs.append(f'shape="{shape_map_to_dot(node.get("shape"))}"')
        if node.get("label"):
            attrs.append(f'label="{escape_label(node["label"])}"')
        if node.get("color"):
            attrs.append(f'color="{hex_to_dot_color(node["color"])}"')
        if node.get("fillColor"):
            attrs.append('style="filled"')
            attrs.append(f'fillcolor="{hex_to_dot_color(node["fillColor"])}"')
        style = style_map_to_dot(node.get("style"))
        if style != "solid":
            attrs.append(f'style="{style}"')
        lines.append(f'  "{node.get("id")}" [{", ".join(attrs)}];')

    for edge in edges:
        src = edge.get("source")
        dst = edge.get("target")
        if not src or not dst:
            continue
        attrs: List[str] = []
        if edge.get("color"):
            attrs.append(f'color="{hex_to_dot_color(edge["color"])}"')
        style = style_map_to_dot(edge.get("style"))
        if style != "solid":
            attrs.append(f'style="{style}"')
        if edge.get("label"):
            attrs.append(f'label="{escape_label(edge["label"])}"')
        if directed:
            arrow = arrow_map_to_dot(edge.get("arrowHead", "normal"))
            attrs.append(f'arrowhead="{arrow}"')
        if edge.get("weight") is not None:
            attrs.append(f'weight={float(edge["weight"])}')
        attr_str = f' [{", ".join(attrs)}]' if attrs else ""
        lines.append(f'  "{src}" {connector} "{dst}"{attr_str};')

    lines.append("}")
    return "\n".join(lines) + "\n"
