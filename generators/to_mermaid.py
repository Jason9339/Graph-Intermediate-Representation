"""Generate Mermaid code from IR."""

from __future__ import annotations

from typing import Any, Dict, List

from .utils import escape_label, orientation_to_mermaid


def _render_class_defs(graph_metadata: Dict[str, Any]) -> List[str]:
    class_defs = graph_metadata.get("class_defs") or []
    return [f"  {line}" for line in class_defs]


def _render_link_styles(graph_metadata: Dict[str, Any]) -> List[str]:
    link_styles = graph_metadata.get("link_styles") or []
    return [f"  {line}" for line in link_styles]


def _render_styles(styles: List[str]) -> List[str]:
    return [f"  {line}" for line in styles]


def _render_flowchart(ir: Dict[str, Any]) -> str:
    graph = ir.get("graph", {})
    nodes: List[Dict[str, Any]] = ir.get("nodes", [])
    edges: List[Dict[str, Any]] = ir.get("edges", [])
    groups: List[Dict[str, Any]] = ir.get("groups", [])
    graph_metadata = graph.get("metadata", {})

    orientation = orientation_to_mermaid(graph.get("orientation", "TB"))
    directed = bool(graph.get("directed", True))
    arrow = "-->" if directed else "---"

    lines: List[str] = [f"flowchart {orientation}"]
    styles: List[str] = []

    lines.extend(_render_class_defs(graph_metadata))

    for node in nodes:
        node_line = _mermaid_shape(node)
        lines.append(f"  {node_line}")
        style_parts: List[str] = []
        if node.get("color"):
            style_parts.append(f'stroke:{node["color"]}')
        if node.get("fillColor"):
            style_parts.append(f'fill:{node["fillColor"]}')
        node_style = (node.get("style") or "").lower()
        if "bold" in node_style or "thick" in node_style:
            style_parts.append("stroke-width:2px")
        if "dashed" in node_style:
            style_parts.append("stroke-dasharray:4 2")
        metadata = node.get("metadata") or {}
        if metadata.get("style_overrides"):
            style_parts.extend(metadata["style_overrides"])
        if metadata.get("classes"):
            class_list = metadata["classes"]
            lines.append(f"  class {node['id']} {','.join(class_list)}")
        if style_parts:
            styles.append(f"style {node['id']} " + ",".join(style_parts))

    for group in groups:
        label = group.get("label", group.get("id", "group"))
        lines.append(f"  subgraph {label}")
        for node_id in group.get("nodes", []):
            lines.append(f"    {node_id}")
        lines.append("  end")

    for edge in edges:
        src = edge.get("source")
        dst = edge.get("target")
        if not src or not dst:
            continue
        label = edge.get("label")
        if label:
            lines.append(f"  {src} {arrow}|{escape_label(label)}| {dst}")
        else:
            lines.append(f"  {src} {arrow} {dst}")

    lines.extend(_render_link_styles(graph_metadata))
    if styles:
        lines.extend(_render_styles(styles))
    return "\n".join(lines) + "\n"


def _render_mindmap(ir: Dict[str, Any]) -> str:
    graph = ir.get("graph", {})
    nodes: List[Dict[str, Any]] = ir.get("nodes", [])
    edges: List[Dict[str, Any]] = ir.get("edges", [])
    graph_metadata = graph.get("metadata", {})

    lines: List[str] = ["mindmap"]
    children_map: Dict[str, List[str]] = {}
    for node in nodes:
        children_map.setdefault(node.get("id"), [])
    for edge in edges:
        src = edge.get("source")
        dst = edge.get("target")
        if src and dst:
            children_map.setdefault(src, []).append(dst)

    node_lookup = {node.get("id"): node for node in nodes}
    root_nodes = [node for node in nodes if all(edge.get("target") != node.get("id") for edge in edges)]

    config_lines = graph_metadata.get("config") or []

    def render_node(node_id: str, depth: int = 1, include_config: bool = False) -> None:
        node = node_lookup.get(node_id)
        if not node:
            return
        indent = "  " * depth
        label = escape_label(node.get("label", node_id))
        metadata = node.get("metadata") or {}
        if depth == 1:
            lines.append(f"{indent}{node_id}(\"{label}\")")
        else:
            lines.append(f"{indent}{label}")
        extra_indent = indent + "  "
        if include_config:
            for line in config_lines:
                lines.append(f"{extra_indent}{line}")
        for icon in metadata.get("icons", []):
            lines.append(f"{extra_indent}{icon}")
        for child_id in children_map.get(node_id, []):
            render_node(child_id, depth + 1)

    for idx, root_node in enumerate(root_nodes):
        render_node(root_node.get("id"), include_config=(idx == 0))

    return "\n".join(lines) + "\n"


def _mermaid_shape(node: Dict[str, Any]) -> str:
    node_id = node.get("id", "node")
    label = escape_label(node.get("label", node_id))
    shape = (node.get("shape") or "rect").lower()
    if shape in {"rect", "rectangle", "box", "parallelogram", "trapezium", "hexagon", "stadium"}:
        return f'{node_id}["{label}"]'
    if shape in {"circle", "ellipse", "oval"}:
        return f'{node_id}("{label}")'
    if shape in {"diamond", "rhombus"}:
        return f'{node_id}{{"{label}"}}'
    return f'{node_id}["{label}"]'


def generate_mermaid(ir: Dict[str, Any]) -> str:
    diagram_type = ir.get("graph", {}).get("metadata", {}).get("diagram_type")
    if diagram_type == "mindmap":
        return _render_mindmap(ir)
    return _render_flowchart(ir)
