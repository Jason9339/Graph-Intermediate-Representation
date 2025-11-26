"""Mermaid parser with Phase 1 preprocessing and flowchart extraction."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .mermaid_svg import (
    MermaidRenderError,
    extract_node_geometries,
    render_mermaid_to_svg,
)
from .utils import IRGroup, IREdge, IRNode, build_minimal_ir, normalize_mermaid

DEFAULT_MERMAID_ORIENTATION = "LR"
_ARROW_TOKENS = ["-->", "-.->", "--x", "==>", "~~>", "->", "---", "--"]
SUBGRAPH_PREFIX = "subgraph"
PARTICIPANT_PATTERN = re.compile(r"^participant\s+(\S+)(?:\s+as\s+(.+))?$")
SEQUENCE_ARROWS = ["-->>", "->>", "-->", "->", "--x", "-x", "x--", "x-"]
NOTE_PATTERN = re.compile(
    r"^note\s+(?P<position>over|right of|left of)\s+(?P<targets>[A-Za-z0-9_, ]+):\s*(?P<text>.+)$",
    re.IGNORECASE,
)
MINDMAP_NODE_PATTERN = re.compile(r"^([A-Za-z0-9_]+)\((.+)\)$")
_NUMERIC_PATTERN = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


NodeLike = Union[IRNode, Dict[str, Any]]


def _get_node_label(node: NodeLike) -> str:
    if isinstance(node, IRNode):
        return node.label
    return node.get("label", "")


def _ensure_node_metadata(node: NodeLike) -> Dict[str, Any]:
    if isinstance(node, IRNode):
        return node.metadata
    metadata = node.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        node["metadata"] = metadata
    return metadata


def _set_node_value(node: NodeLike, field: str, value: Any) -> None:
    if isinstance(node, IRNode):
        setattr(node, field, value)
    else:
        node[field] = value


def _get_node_value(node: NodeLike, field: str) -> Any:
    if isinstance(node, IRNode):
        return getattr(node, field)
    return node.get(field)


def _normalize_css_key(key: str) -> str:
    return key.strip().lower().replace("_", "-")


def _merge_style_tokens(existing: Optional[str], additions: List[str]) -> Optional[str]:
    tokens: List[str] = []
    if existing:
        tokens = [token for token in existing.split() if token]
    for token in additions:
        clean = token.strip()
        if clean and clean not in tokens:
            tokens.append(clean)
    if not tokens:
        return existing if existing else None
    return " ".join(tokens)


def _parse_numeric_value(text: str) -> Optional[float]:
    match = _NUMERIC_PATTERN.search(text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _apply_css_declarations_to_node(node: NodeLike, declarations: Dict[str, str]) -> Set[str]:
    recognized: Set[str] = set()
    if not declarations:
        return recognized
    style_tokens: List[str] = []
    for raw_key, raw_value in declarations.items():
        if raw_value is None:
            continue
        key = _normalize_css_key(raw_key)
        value = raw_value.strip()
        if not value:
            continue
        if key in {"stroke", "stroke-color", "border", "border-color"}:
            _set_node_value(node, "color", value)  # IRNode uses 'color' internally
            recognized.add(key)
            continue
        if key in {"fill", "fill-color", "background", "background-color"}:
            _set_node_value(node, "fill_color", value)  # IRNode uses 'fill_color' internally
            recognized.add(key)
            continue
        if key == "stroke-width":
            width_value = _parse_numeric_value(value)
            if width_value is not None:
                _set_node_value(node, "stroke_width", width_value)
                if width_value >= 2.0:
                    style_tokens.append("bold")
            recognized.add(key)
            continue
        if key in {"stroke-dasharray", "stroke-dashpattern", "stroke-style"}:
            if "dash" in value or value not in {"0", "none", "0,0"}:
                style_tokens.append("dashed")
            recognized.add(key)
            continue
        if key == "font-weight":
            if value.lower() in {"bold", "600", "700", "800", "900"}:
                style_tokens.append("bold")
            recognized.add(key)
            continue
        if key == "color":
            # Text color (not stroke color)
            _set_node_value(node, "text_color", value)
            recognized.add(key)
            continue

    if style_tokens:
        merged = _merge_style_tokens(_get_node_value(node, "style"), style_tokens)
        if merged:
            _set_node_value(node, "style", merged)
            recognized.add("style")
    return recognized


def _ensure_edge_metadata(edge: Union[IREdge, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(edge, IREdge):
        return edge.metadata
    metadata = edge.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        edge["metadata"] = metadata
    return metadata


def _set_edge_value(edge: Union[IREdge, Dict[str, Any]], field: str, value: Any) -> None:
    if isinstance(edge, IREdge):
        setattr(edge, field, value)
    else:
        edge[field] = value


def _get_edge_value(edge: Union[IREdge, Dict[str, Any]], field: str) -> Any:
    if isinstance(edge, IREdge):
        return getattr(edge, field)
    return edge.get(field)


def _parse_dash_pattern(text: str) -> Optional[List[float]]:
    if not text:
        return None
    matches = _NUMERIC_PATTERN.findall(text)
    if not matches:
        return None
    try:
        values = [float(m) for m in matches]
        return values or None
    except ValueError:
        return None


def _apply_css_declarations_to_edge(edge: Union[IREdge, Dict[str, Any]], declarations: Dict[str, str]) -> Set[str]:
    recognized: Set[str] = set()
    if not declarations:
        return recognized
    for raw_key, raw_value in declarations.items():
        if raw_value is None:
            continue
        key = _normalize_css_key(raw_key)
        value = raw_value.strip()
        if not value:
            continue
        if key in {"stroke", "stroke-color", "border", "color", "line-color"}:
            _set_edge_value(edge, "color" if isinstance(edge, IREdge) else "stroke", value)
            recognized.add(key)
            continue
        if key in {"stroke-width", "penwidth"}:
            width_value = _parse_numeric_value(value)
            if width_value is not None:
                _set_edge_value(edge, "stroke_width" if isinstance(edge, IREdge) else "strokeWidth", width_value)
                recognized.add(key)
            continue
        if key in {"stroke-dasharray", "stroke-dashpattern", "stroke-style"}:
            dash = _parse_dash_pattern(value)
            if dash:
                _set_edge_value(edge, "dash", dash)
            else:
                _set_edge_value(edge, "style", "dashed")
            recognized.add(key)
            continue
    return recognized


def _promote_node_fields(node: Dict[str, Any]) -> None:
    metadata = node.get("metadata")
    if not isinstance(metadata, dict):
        return

    node_kind = metadata.pop("type", None)
    if node_kind and "kind" not in node:
        node["kind"] = node_kind
    alias = metadata.pop("alias", None)
    if alias and "alias" not in node:
        node["alias"] = alias
    participants = metadata.pop("participants", None)
    if participants and "participants" not in node:
        node["participants"] = participants
    note_position = metadata.pop("position", None)
    if note_position and "notePosition" not in node:
        node["notePosition"] = note_position

    classes = metadata.pop("classes", None)
    if classes and "classes" not in node:
        node["classes"] = classes

    # Merge styleOverrides directly into node (not as inlineStyleOverrides)
    overrides = metadata.pop("styleOverrides", None)
    if overrides:
        # Parse and merge CSS properties
        for key, value in overrides.items():
            normalized_key = _normalize_css_key(key)
            if normalized_key == "font-size":
                numeric_val = _parse_numeric_value(value)
                if numeric_val and "font_size" not in node:
                    node["font_size"] = numeric_val
            elif normalized_key == "font-weight":
                if "font_weight" not in node:
                    node["font_weight"] = value
            # Add more style properties as needed

    # Drop verbose geometry instances and rendered_classes
    metadata.pop("geometry_instances", None)
    metadata.pop("rendered_classes", None)

    if not metadata:
        node.pop("metadata", None)


def _standardize_node_fields(node: Dict[str, Any]) -> None:
    """Phase 3: Standardize field names to unified format.

    - fill_color → fill
    - color/stroke → stroke
    - stroke_width → strokeWidth
    - text_color → textColor
    - font_size → fontSize
    - font_weight → fontWeight
    - position → pos (array format)
    - width, height → size (array format)
    """

    # Rename fillColor (from IRNode.to_dict) or fill_color → fill
    if "fillColor" in node:
        val = node.pop("fillColor")
        if val is not None:
            node["fill"] = val
    elif "fill_color" in node:
        val = node.pop("fill_color")
        if val is not None:
            node["fill"] = val

    # Rename color → stroke (from IRNode.to_dict)
    if "color" in node:
        val = node.pop("color")
        if val is not None and "stroke" not in node:
            node["stroke"] = val

    # Rename stroke_width → strokeWidth
    if "stroke_width" in node:
        val = node.pop("stroke_width")
        if val is not None:
            node["strokeWidth"] = val

    # Rename text_color → textColor
    if "text_color" in node:
        val = node.pop("text_color")
        if val is not None:
            node["textColor"] = val

    # Rename font_size → fontSize
    if "font_size" in node:
        val = node.pop("font_size")
        if val is not None:
            node["fontSize"] = val

    # Rename font_weight → fontWeight
    if "font_weight" in node:
        val = node.pop("font_weight")
        if val is not None:
            node["fontWeight"] = val

    # Convert position object to pos array
    if "position" in node:
        pos_obj = node.pop("position")
        if isinstance(pos_obj, dict):
            node["pos"] = [pos_obj.get("x", 0), pos_obj.get("y", 0)]

    # Convert width, height to size array
    if "width" in node and "height" in node:
        width = node.pop("width")
        height = node.pop("height")
        # Only add size if both values are not None
        if width is not None and height is not None:
            node["size"] = [width, height]

    # Clean up None values to reduce clutter
    keys_to_remove = [key for key, value in list(node.items()) if value is None]
    for key in keys_to_remove:
        node.pop(key)

    # Clean up arrays containing only None values
    if "size" in node and all(v is None for v in node["size"]):
        node.pop("size")


def _standardize_edge_fields(edge: Dict[str, Any]) -> None:
    """Standardize edge field names."""

    # Rename stroke_width → strokeWidth for edges
    if "stroke_width" in edge:
        edge["strokeWidth"] = edge.pop("stroke_width")

    # Rename color → stroke for edges
    if "color" in edge and "stroke" not in edge:
        edge["stroke"] = edge.pop("color")

    # Apply inline style overrides if present
    overrides = edge.pop("inlineStyleOverrides", None)
    metadata = edge.get("metadata")
    metadata_overrides = None
    if isinstance(metadata, dict):
        metadata_overrides = metadata.pop("styleOverrides", None)
        if not metadata:
            edge.pop("metadata", None)
    combined_overrides: Dict[str, str] = {}
    if isinstance(metadata_overrides, dict):
        combined_overrides.update(metadata_overrides)
    if isinstance(overrides, dict):
        combined_overrides.update(overrides)
    if combined_overrides:
        _apply_css_declarations_to_edge(edge, combined_overrides)

    # Translate style keywords to dash arrays when possible
    style_value = edge.get("style")
    if style_value and "dash" not in edge:
        dash = _parse_dash_pattern(style_value)
        if not dash and "dash" in style_value.lower():
            dash = [6, 4]
        if dash:
            edge["dash"] = dash


def _promote_edge_fields(edge: Dict[str, Any]) -> None:
    metadata = edge.get("metadata")
    if not isinstance(metadata, dict):
        return
    edge_kind = metadata.pop("type", None)
    if edge_kind and "kind" not in edge:
        edge["kind"] = edge_kind
    arrow = metadata.pop("arrow_token", None)
    if arrow and "arrowToken" not in edge:
        edge["arrowToken"] = arrow
    src_act = metadata.pop("source_activation", None)
    if src_act and "sourceActivation" not in edge:
        edge["sourceActivation"] = src_act
    dst_act = metadata.pop("target_activation", None)
    if dst_act and "targetActivation" not in edge:
        edge["targetActivation"] = dst_act
    termination = metadata.pop("termination", None)
    if termination and "termination" not in edge:
        edge["termination"] = termination
    edge_id = metadata.pop("id", None)
    if edge_id and "id" not in edge:
        edge["id"] = edge_id
    overrides = metadata.pop("styleOverrides", None)
    if overrides and "inlineStyleOverrides" not in edge:
        edge["inlineStyleOverrides"] = overrides
    metadata.pop("classes", None)
    if not metadata:
        edge.pop("metadata", None)


def _promote_graph_fields(graph: Dict[str, Any]) -> None:
    metadata = graph.get("metadata")
    if not isinstance(metadata, dict):
        return
    diag_type = metadata.pop("diagram_type", None)
    if diag_type and "diagramType" not in graph:
        graph["diagramType"] = diag_type
    timeline = metadata.pop("sequence_timeline", None)
    if timeline and "sequenceTimeline" not in graph:
        graph["sequenceTimeline"] = timeline
    if not metadata:
        graph.pop("metadata", None)


def _format_graph_styles(graph_styles: Dict[str, Any]) -> Dict[str, Any]:
    """Return a simplified styles block for the IR graph."""

    normalized: Dict[str, Any] = {}
    node_styles = graph_styles.get("node") or {}
    edge_styles = graph_styles.get("edge") or {}

    node_defaults = node_styles.get("default") or {}
    if node_defaults:
        normalized["nodeDefaults"] = dict(node_defaults)
    node_classes = node_styles.get("classes") or {}
    if node_classes:
        normalized["nodeClasses"] = dict(node_classes)

    edge_defaults = edge_styles.get("default") or {}
    if edge_defaults:
        normalized["edgeDefaults"] = dict(edge_defaults)
    edge_classes = edge_styles.get("classes") or {}
    if edge_classes:
        normalized["edgeClasses"] = dict(edge_classes)

    return normalized


def _enrich_nodes_with_svg_geometry(
    code: str,
    nodes: List[NodeLike],
    metadata: Dict[str, Any],
    diagram_type: Optional[str] = None,
    svg_output_path: Optional[str] = None,
) -> None:
    """Populate node positions using Mermaid's SVG rendering output.

    Args:
        code: Mermaid diagram code
        nodes: List of nodes to enrich
        metadata: Metadata dict to update
        diagram_type: Type of diagram (flowchart, sequenceDiagram, mindmap, etc.)
        svg_output_path: Optional path to save the generated SVG file
    """

    if not nodes:
        return
    try:
        svg_text = render_mermaid_to_svg(code, save_svg_path=svg_output_path)
        svg_geometries = extract_node_geometries(svg_text, diagram_type=diagram_type)
    except MermaidRenderError as exc:
        message = str(exc).strip().splitlines()[0]
        metadata.setdefault("warnings", []).append(f"svg_enrichment_failed: {message}")
        return
    if not svg_geometries:
        metadata.setdefault("warnings", []).append("svg_enrichment_empty")
        return

    label_to_geoms: Dict[str, List[Tuple[int, SvgNodeGeometry]]] = defaultdict(list)
    for index, geom in enumerate(svg_geometries):
        label_key = (geom.label or "").strip()
        if not label_key:
            label_key = f"__index_{index}"
        label_to_geoms[label_key].append((index, geom))

    unmatched_indices: Set[int] = set(range(len(svg_geometries)))
    matched_instances = 0

    def _consume_geometries(key: str) -> List[Tuple[int, SvgNodeGeometry]]:
        entries = label_to_geoms.get(key) or []
        if entries:
            label_to_geoms[key] = []
        return entries

    for node in nodes:
        label = (_get_node_label(node) or "").strip()
        node_id = getattr(node, "node_id", None) if isinstance(node, IRNode) else node.get("id")
        candidates: List[Tuple[int, SvgNodeGeometry]] = []
        selected_key: Optional[str] = None

        for key in filter(None, [label, node_id]):
            entries = _consume_geometries(key)
            if entries:
                candidates = entries
                selected_key = key
                break

        if not candidates:
            # Fall back to the first remaining geometry bucket.
            for key, entries in label_to_geoms.items():
                if entries:
                    candidates = entries
                    label_to_geoms[key] = []
                    selected_key = key
                    break

        if not candidates:
            continue

        metadata_ref = _ensure_node_metadata(node)
        metadata_ref["geometry_instances"] = []
        geometry_instances = metadata_ref["geometry_instances"]

        for idx, geom in candidates:
            instance_entry = {
                "position": geom.to_position(),
                "width": geom.width,
                "height": geom.height,
                "raw_class": geom.raw_class,
                "svg_index": idx,
            }
            geometry_instances.append(instance_entry)
            unmatched_indices.discard(idx)
        matched_instances += len(candidates)

        primary = geometry_instances[0]
        position = primary.get("position")
        if position:
            _set_node_value(node, "position", {"x": position.get("x"), "y": position.get("y")})
        width = primary.get("width")
        height = primary.get("height")
        if width is not None:
            _set_node_value(node, "width", width)
        if height is not None:
            _set_node_value(node, "height", height)

        first_geom = candidates[0][1]
        classes = [cls for cls in first_geom.raw_class.split() if cls]
        if classes:
            existing_classes = metadata_ref.setdefault("rendered_classes", [])
            for cls in classes:
                if cls not in existing_classes:
                    existing_classes.append(cls)

    if unmatched_indices:
        metadata.setdefault("warnings", []).append(
            f"svg_enrichment_unmatched:{len(unmatched_indices)}"
        )
    svg_meta = metadata.setdefault("svg_enrichment", {})
    svg_meta["source"] = "mermaid_cli"
    svg_meta["adapter"] = "mmdc"
    svg_meta["nodeCount"] = len(svg_geometries)
    svg_meta["matchedInstances"] = matched_instances


def _parse_css_declarations(text: str) -> Dict[str, str]:
    declarations: Dict[str, str] = {}
    if not text:
        return declarations
    for raw in re.split(r"[;,]", text):
        entry = raw.strip()
        if not entry:
            continue
        if ":" in entry:
            key, value = entry.split(":", 1)
        elif "=" in entry:
            key, value = entry.split("=", 1)
        else:
            declarations[entry.strip()] = "true"
            continue
        declarations[key.strip()] = value.strip()
    return declarations


def _clean_label(text: str) -> str:
    value = text.strip()

    # Strip surrounding quotes first
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        value = value[1:-1]
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        value = value[1:-1]

    # Remove outer parentheses added by some Mermaid parsers
    if value.startswith("(") and value.endswith(")") and len(value) >= 2:
        value = value[1:-1].strip()

    # Normalize simple HTML line breaks/tags to plain text
    value = re.sub(r"<br\\s*/?>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)  # drop any remaining tags

    # Collapse whitespace
    value = " ".join(value.split())
    return value


def _slugify(text: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_")
    return slug.lower() or "group"


def _split_node_token(token: str) -> Tuple[str, str, str, Optional[str]]:
    token = token.strip()
    class_name: Optional[str] = None
    if ":::" in token:
        token, class_name = token.split(":::", 1)
        class_name = class_name.strip() or None
    match = re.match(r"^([A-Za-z0-9_]+)", token)
    if not match:
        identifier = token.strip()
        return identifier, _clean_label(identifier), "rect", class_name
    identifier = match.group(1)
    remainder = token[match.end():].strip()
    label = ""
    shape: Optional[str] = None
    if remainder.startswith("[["):
        end = remainder.find("]]")
        if end != -1:
            label = remainder[2:end]
            shape = "subroutine"
    elif remainder.startswith("["):
        end = remainder.find("]")
        if end != -1:
            label = remainder[1:end]
            shape = "rect"
    elif remainder.startswith("(("):
        end = remainder.find("))")
        if end != -1:
            label = remainder[2:end]
            shape = "circle"
    elif remainder.startswith("("):
        end = remainder.find(")")
        if end != -1:
            label = remainder[1:end]
            shape = "round"
    elif remainder.startswith("{"):
        end = remainder.find("}")
        if end != -1:
            label = remainder[1:end]
            shape = "diamond"
    elif remainder.startswith(">"):
        end = remainder.find("<", 1)
        if end != -1:
            label = remainder[1:end]
            shape = "subroutine"
    label = _clean_label(label)
    if shape is None:
        shape = "rect"
    return identifier, label, shape, class_name


def _add_node_to_group(node_id: str, groups: Dict[str, IRGroup], group_stack: List[str]) -> None:
    if not group_stack:
        return
    current_group = group_stack[-1]
    group = groups.get(current_group)
    if group is None:
        group = IRGroup(group_id=current_group, label=current_group)
        groups[current_group] = group
    if node_id not in group.nodes:
        group.nodes.append(node_id)


def _ensure_node(nodes: Dict[str, IRNode], token: str, groups: Dict[str, IRGroup], group_stack: List[str]) -> IRNode:
    node_id, label, shape, class_name = _split_node_token(token)
    node = nodes.get(node_id)
    if node is None:
        node = IRNode(node_id=node_id, label=label, shape=shape, metadata={})
        nodes[node_id] = node
    else:
        if label and not node.label:
            node.label = label
        if shape and not node.shape:
            node.shape = shape
    if class_name:
        classes = node.metadata.setdefault("classes", [])
        if class_name not in classes:
            classes.append(class_name)
    _add_node_to_group(node_id, groups, group_stack)
    return node


def _pop_trailing_label(segment: str) -> Tuple[str, str]:
    match = re.search(r"\|([^|]+)\|\s*$", segment)
    if match:
        label = _clean_label(match.group(1))
        segment = segment[: match.start()].strip()
        return segment, label
    return segment.strip(), ""


def _pop_leading_label(segment: str) -> Tuple[str, str]:
    stripped = segment.strip()
    if stripped.startswith("|"):
        end = stripped.find("|", 1)
        if end != -1:
            label = _clean_label(stripped[1:end])
            remainder = stripped[end + 1 :].strip()
            return remainder, label
    return stripped, ""


def _parse_flow_edge(line: str, nodes: Dict[str, IRNode], groups: Dict[str, IRGroup], group_stack: List[str]) -> Tuple[Optional[IREdge], bool]:
    arrow = None
    for token in _ARROW_TOKENS:
        if token in line:
            arrow = token
            break
    if not arrow:
        return None, False
    left, right = line.split(arrow, 1)
    left, label = _pop_trailing_label(left)
    right, right_label = _pop_leading_label(right)
    if not label:
        label = right_label
    source_node = _ensure_node(nodes, left, groups, group_stack)
    target_node = _ensure_node(nodes, right, groups, group_stack)
    directed = ">" in arrow
    if arrow == "--":
        directed = False
    style = None
    if "." in arrow:
        style = "dashed"
    elif "=" in arrow:
        style = "bold"
    edge = IREdge(
        source=source_node.node_id,
        target=target_node.node_id,
        directed=directed,
        label=label,
    )
    if style:
        edge.style = style
    if "x" in arrow:
        edge.metadata["termination"] = "cross"
    return edge, True


def _parse_flow_node(line: str, nodes: Dict[str, IRNode], groups: Dict[str, IRGroup], group_stack: List[str]) -> bool:
    node_id, label, shape, class_name = _split_node_token(line)
    if not node_id:
        return False
    node = nodes.get(node_id)
    if node is None:
        node = IRNode(node_id=node_id, label=label, shape=shape, metadata={})
        nodes[node_id] = node
    else:
        if label and not node.label:
            node.label = label
        if shape and not node.shape:
            node.shape = shape
    if class_name:
        classes = node.metadata.setdefault("classes", [])
        if class_name not in classes:
            classes.append(class_name)
    _add_node_to_group(node_id, groups, group_stack)
    return True


def _apply_graph_styles_to_nodes(nodes: List[IRNode], graph_styles: Dict[str, Dict[str, Dict[str, str]]]) -> None:
    if not nodes:
        return
    node_styles = graph_styles.get("node") or {}
    default_styles = node_styles.get("default") or {}
    class_styles = node_styles.get("classes") or {}

    for node in nodes:
        declarations: Dict[str, str] = {}
        if default_styles:
            declarations.update(default_styles)
        for class_name in node.metadata.get("classes", []):
            if not class_name:
                continue
            class_decl = class_styles.get(class_name)
            if class_decl:
                declarations.update(class_decl)
        overrides = node.metadata.get("styleOverrides")
        if overrides:
            declarations.update(overrides)
        recognized = _apply_css_declarations_to_node(node, declarations)
        if overrides:
            remaining = {k: v for k, v in overrides.items() if _normalize_css_key(k) not in recognized}
            if remaining:
                node.metadata["styleOverrides"] = remaining
            else:
                node.metadata.pop("styleOverrides", None)


def _parse_flowchart(lines: List[str]) -> Tuple[List[IRNode], List[IREdge], List[IRGroup], Dict[str, Any]]:
    nodes: Dict[str, IRNode] = {}
    edges: List[IREdge] = []
    groups: Dict[str, IRGroup] = {}
    group_stack: List[str] = []
    unprocessed: List[str] = []
    edge_style_overrides: Dict[int, Dict[str, str]] = {}
    graph_styles: Dict[str, Dict[str, Dict[str, str]]] = {
        "node": {"default": {}, "classes": {}},
        "edge": {"default": {}, "classes": {}},
    }

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        if stripped.startswith("flowchart ") or stripped.startswith("graph "):
            continue
        if stripped.startswith("classDef "):
            parts = stripped.split(None, 2)
            if len(parts) >= 3:
                _, class_name, decl = parts
                declarations = _parse_css_declarations(decl)
                if class_name == "default":
                    graph_styles["node"]["default"].update(declarations)
                else:
                    target = graph_styles["node"]["classes"].setdefault(class_name, {})
                    target.update(declarations)
            continue
        if stripped.startswith("linkStyle"):
            parts = stripped.split(None, 2)
            if len(parts) >= 3:
                _, target, decl = parts
                declarations = _parse_css_declarations(decl)
                target = target.strip()
                if target.lower() == "default":
                    graph_styles["edge"]["default"].update(declarations)
                else:
                    indices: List[int] = []
                    for token in target.split(","):
                        token = token.strip()
                        if not token:
                            continue
                        try:
                            indices.append(int(token))
                        except ValueError:
                            continue
                    for idx in indices:
                        style_entry = edge_style_overrides.setdefault(idx, {})
                        style_entry.update(declarations)
            continue
        if stripped.startswith("style "):
            parts = stripped.split(None, 2)
            if len(parts) >= 3:
                node_id = parts[1]
                node = _ensure_node(nodes, node_id, groups, group_stack)
                overrides_map = node.metadata.setdefault("styleOverrides", {})
                overrides_map.update(_parse_css_declarations(parts[2]))
            continue
        if stripped.startswith("class "):
            _, rest = stripped.split(None, 1)
            if " " in rest:
                node_part, class_name = rest.split(None, 1)
                class_name = class_name.strip()
                for node_id in node_part.split(","):
                    node = _ensure_node(nodes, node_id, groups, group_stack)
                    classes = node.metadata.setdefault("classes", [])
                    if class_name not in classes:
                        classes.append(class_name)
            continue
        if stripped.startswith(SUBGRAPH_PREFIX):
            label = stripped[len(SUBGRAPH_PREFIX) :].strip()
            group_id = _slugify(label)
            group = groups.get(group_id)
            if group is None:
                group = IRGroup(group_id=group_id, label=label)
                groups[group_id] = group
            if group_stack:
                parent = groups[group_stack[-1]]
                if group_id not in parent.groups:
                    parent.groups.append(group_id)
            group_stack.append(group_id)
            continue
        if stripped == "end":
            if group_stack:
                group_stack.pop()
            continue

        edge, matched = _parse_flow_edge(stripped, nodes, groups, group_stack)
        if matched and edge is not None:
            edges.append(edge)
            continue
        if _parse_flow_node(stripped, nodes, groups, group_stack):
            continue
        unprocessed.append(stripped)

    if edge_style_overrides:
        for index, decl in edge_style_overrides.items():
            if 0 <= index < len(edges):
                overrides_map = edges[index].metadata.setdefault("styleOverrides", {})
                overrides_map.update(decl)

    # Apply edge-level styles (default + per-edge overrides)
    default_edge_styles = graph_styles.get("edge", {}).get("default") or {}
    for idx, edge in enumerate(edges):
        declarations: Dict[str, str] = {}
        if default_edge_styles:
            declarations.update(default_edge_styles)
        edge_overrides = edge_style_overrides.get(idx)
        if edge_overrides:
            declarations.update(edge_overrides)
        metadata = _ensure_edge_metadata(edge)
        overrides = metadata.get("styleOverrides")
        if overrides:
            declarations.update(overrides)
        recognized = _apply_css_declarations_to_edge(edge, declarations)
        if overrides:
            remaining = {k: v for k, v in overrides.items() if _normalize_css_key(k) not in recognized}
            if remaining:
                metadata["styleOverrides"] = remaining
            else:
                metadata.pop("styleOverrides", None)

    metadata: Dict[str, Any] = {}
    if unprocessed:
        metadata["unprocessed"] = unprocessed
    if any(graph_styles["node"]["default"] or graph_styles["node"]["classes"] or graph_styles["edge"]["default"]):
        metadata["styles"] = graph_styles

    node_list = list(nodes.values())
    _apply_graph_styles_to_nodes(node_list, graph_styles)
    group_list = [group for group in groups.values() if group.nodes]
    return node_list, edges, group_list, metadata


def _ensure_sequence_node(nodes: Dict[str, IRNode], node_id: str, label: Optional[str] = None) -> IRNode:
    node = nodes.get(node_id)
    if node is None:
        node = IRNode(node_id=node_id, label=label or node_id, shape="rect", metadata={})
        nodes[node_id] = node
    else:
        if label and not node.label:
            node.label = label
    return node


def _parse_sequence(
    lines: List[str],
) -> Tuple[List[IRNode], List[IREdge], List[IRGroup], Dict[str, Any]]:
    participants: Dict[str, IRNode] = {}
    note_nodes: List[IRNode] = []
    edges: List[IREdge] = []
    groups: List[IRGroup] = []
    timeline: List[Dict[str, Any]] = []
    rect_stack: List[Dict[str, Any]] = []
    rect_sections: List[Dict[str, Any]] = []
    unprocessed: List[str] = []

    def current_block_id() -> Optional[str]:
        return rect_stack[-1]["id"] if rect_stack else None

    seen_participants: set[str] = set()
    note_counter = 0
    block_counter = 0

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        if stripped == "sequenceDiagram":
            continue

        if stripped.startswith("rect "):
            block_counter += 1
            block_id = f"block_{block_counter}"
            header = stripped
            color = None
            header_lower = header.lower()
            if "rect" in header_lower:
                _, _, remainder = header.partition(" ")
                color = remainder.strip() or None
            block_entry = {
                "id": block_id,
                "label": header,
                "color": color,
                "nodes": set(),
            }
            rect_sections.append(block_entry)
            rect_stack.append(block_entry)
            timeline.append({"type": "block_start", "block": block_id})
            continue

        if stripped == "end" and rect_stack:
            block_id = rect_stack[-1]["id"]
            rect_stack.pop()
            timeline.append({"type": "block_end", "block": block_id})
            continue

        participant_match = PARTICIPANT_PATTERN.match(stripped)
        if participant_match:
            ident, alias = participant_match.groups()
            label = alias.strip() if alias else ident
            node = _ensure_sequence_node(participants, ident, label)
            node.metadata["type"] = "participant"
            if alias:
                node.metadata["alias"] = alias.strip()
            if ident not in seen_participants:
                timeline.append({"type": "participant", "participant": ident})
                seen_participants.add(ident)
            continue

        note_match = NOTE_PATTERN.match(stripped)
        if note_match:
            note_counter += 1
            note_id = f"note_{note_counter}"
            position = note_match.group("position").lower()
            targets = [token.strip() for token in note_match.group("targets").split(",") if token.strip()]
            text = _clean_label(note_match.group("text"))
            node = IRNode(node_id=note_id, label=text, shape="note", metadata={})
            node.metadata["type"] = "note"
            node.metadata["position"] = position
            if targets:
                node.metadata["participants"] = targets
                for target in targets:
                    participant_node = _ensure_sequence_node(participants, target)
                    participant_node.metadata["type"] = "participant"
                    if target not in seen_participants:
                        timeline.append({"type": "participant", "participant": target})
                        seen_participants.add(target)
            note_nodes.append(node)
            timeline.append({"type": "note", "note": note_id})
            block_id = current_block_id()
            if block_id and targets:
                rect_stack[-1]["nodes"].update(targets)
            continue

        body, _, remainder = stripped.partition(":")
        arrow_token = None
        left = body
        right = ""
        for candidate in SEQUENCE_ARROWS:
            if candidate in body:
                arrow_token = candidate
                parts = body.split(candidate, 1)
                left, right = parts[0], parts[1]
                break
        if arrow_token is not None:
            src_token = left.strip()
            dst_token = right.strip()
            if not src_token or not dst_token:
                unprocessed.append(stripped)
                continue

            src_activation = None
            dst_activation = None
            if src_token.endswith("+"):
                src_activation = "activate"
                src_token = src_token[:-1]
            elif src_token.endswith("-"):
                src_activation = "deactivate"
                src_token = src_token[:-1]

            if dst_token.startswith("+"):
                dst_activation = "activate"
                dst_token = dst_token[1:]
            elif dst_token.startswith("-"):
                dst_activation = "deactivate"
                dst_token = dst_token[1:]

            src_token = src_token.rstrip(":")
            dst_token = dst_token.rstrip(":")

            label = _clean_label(remainder.strip()) if remainder else ""
            source_node = _ensure_sequence_node(participants, src_token)
            source_node.metadata["type"] = "participant"
            target_node = _ensure_sequence_node(participants, dst_token)
            target_node.metadata["type"] = "participant"

            if source_node.node_id not in seen_participants:
                timeline.append({"type": "participant", "participant": source_node.node_id})
                seen_participants.add(source_node.node_id)
            if target_node.node_id not in seen_participants:
                timeline.append({"type": "participant", "participant": target_node.node_id})
                seen_participants.add(target_node.node_id)

            edge_id = f"e{len(edges) + 1}"
            edge = IREdge(
                source=source_node.node_id,
                target=target_node.node_id,
                directed=True,
                label=label,
            )

            edge.metadata["type"] = "sequence_message"
            edge.metadata["arrow_token"] = arrow_token
            if "." in arrow_token:
                edge.style = "dashed"
            elif "=" in arrow_token:
                edge.style = "bold"
            if "x" in arrow_token:
                edge.metadata["termination"] = "destroy"
            if src_activation:
                edge.metadata["source_activation"] = src_activation
            if dst_activation:
                edge.metadata["target_activation"] = dst_activation

            block_id = current_block_id()
            if block_id:
                edge.metadata["block"] = block_id
                rect_stack[-1]["nodes"].update({source_node.node_id, target_node.node_id})
            edges.append(edge)
            edge.metadata["id"] = edge_id
            timeline.append({"type": "message", "edge": edge_id})
            continue

        if stripped.startswith(("loop ", "alt ", "opt ", "par ", "critical ", "box ")):
            unprocessed.append(stripped)
            continue

        unprocessed.append(stripped)

    for block in rect_sections:
        group = IRGroup(
            group_id=block["id"],
            label=block["label"],
            nodes=sorted(block["nodes"]),
            metadata={"type": "sequence_block"},
        )
        if block.get("color"):
            group.metadata["color"] = block["color"]
        groups.append(group)

    all_nodes: List[IRNode] = list(participants.values()) + note_nodes

    metadata: Dict[str, Any] = {}
    if timeline:
        metadata["sequence_timeline"] = timeline
    if unprocessed:
        metadata["unprocessed"] = unprocessed

    return all_nodes, edges, groups, metadata


def _make_unique_id(base: str, counters: Dict[str, int]) -> str:
    count = counters[base]
    counters[base] += 1
    return base if count == 0 else f"{base}_{count}"


def _parse_mindmap(lines: List[str]) -> Tuple[List[IRNode], List[IREdge], Dict[str, Any]]:
    nodes: Dict[str, IRNode] = {}
    edges: List[IREdge] = []
    stack: List[Tuple[int, str]] = []
    counters: Dict[str, int] = defaultdict(int)
    last_node_id: Optional[str] = None
    unprocessed: List[str] = []

    for raw_line in lines:
        stripped = raw_line.rstrip()
        if not stripped.strip() or stripped.strip().startswith("%%"):
            continue
        if stripped.strip() == "mindmap":
            continue

        indent = len(stripped) - len(stripped.lstrip(" "))
        level = indent // 2
        content = stripped.strip()

        if content.startswith("::icon"):
            if last_node_id and last_node_id in nodes:
                icons = nodes[last_node_id].metadata.setdefault("icons", [])
                icons.append(content)
            continue

        class_name: Optional[str] = None
        if ":::" in content:
            content, class_suffix = content.split(":::", 1)
            class_name = class_suffix.strip() or None
            content = content.strip()

        match = MINDMAP_NODE_PATTERN.match(content)
        if match:
            node_id = match.group(1)
            label = _clean_label(match.group(2))
        else:
            label = _clean_label(content)
            slug = _slugify(label or content)
            if not slug:
                slug = "node"
            node_id = _make_unique_id(slug, counters)

        # Ensure uniqueness if identifier already used
        if node_id in nodes:
            node_id = _make_unique_id(node_id, counters)

        node = IRNode(node_id=node_id, label=label or node_id, shape="rect", metadata={})
        if class_name:
            node.metadata["classes"] = [class_name]
        nodes[node_id] = node

        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack:
            parent_id = stack[-1][1]
            edges.append(IREdge(source=parent_id, target=node_id, directed=True, label=""))

        stack.append((level, node_id))
        last_node_id = node_id

    metadata: Dict[str, Any] = {}
    if unprocessed:
        metadata["unprocessed"] = unprocessed

    return list(nodes.values()), edges, metadata


def _classify_diagram(lines: List[str]) -> Dict[str, Any]:
    diagram_type = "unknown"
    orientation = DEFAULT_MERMAID_ORIENTATION
    first_statement = ""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        first_statement = stripped
        if stripped.startswith("flowchart"):
            diagram_type = "flowchart"
            parts = stripped.split()
            if len(parts) > 1:
                orientation = parts[1]
        elif stripped.startswith("graph"):
            diagram_type = "graph"
            parts = stripped.split()
            if len(parts) > 1:
                orientation = parts[1]
        elif stripped.startswith("sequenceDiagram"):
            diagram_type = "sequenceDiagram"
            orientation = "TB"
        elif stripped.startswith("mindmap"):
            diagram_type = "mindmap"
            orientation = DEFAULT_MERMAID_ORIENTATION
        break
    return {
        "diagram_type": diagram_type,
        "orientation": orientation,
        "first_statement": first_statement,
    }


def parse_mermaid_code(code: str, source_id: str, svg_output_path: Optional[str] = None) -> Dict[str, Any]:
    """Parse Mermaid code into IR-like structures with basic flowchart support.

    Args:
        code: Mermaid diagram code
        source_id: Identifier for the diagram
        svg_output_path: Optional path to save the generated SVG file

    Returns:
        Dict containing the parsed graph structure
    """

    lines = normalize_mermaid(code)
    classification = _classify_diagram(lines)
    metadata: Dict[str, Any] = {
        "source": {
            "id": source_id,
            "format": "mermaid",
        },
        "parser": "mermaid",
        "diagram_type": classification["diagram_type"],
    }
    config_blocks = [line.strip() for line in lines if line.strip().startswith("%%{")]
    if config_blocks:
        metadata["configBlocks"] = config_blocks

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    groups: List[Dict[str, Any]] = []

    diag_type = classification["diagram_type"]

    if diag_type in {"flowchart", "graph"}:
        parsed_nodes, parsed_edges, parsed_groups, extra_metadata = _parse_flowchart(lines)
        _enrich_nodes_with_svg_geometry(code, parsed_nodes, metadata, diagram_type=diag_type, svg_output_path=svg_output_path)
        nodes = [node.to_dict() for node in parsed_nodes]
        edges = [edge.to_dict() for edge in parsed_edges]
        groups = [group.to_dict() for group in parsed_groups]
        if extra_metadata:
            metadata.update(extra_metadata)
    elif diag_type == "sequenceDiagram":
        parsed_nodes, parsed_edges, parsed_groups, extra_metadata = _parse_sequence(lines)
        _enrich_nodes_with_svg_geometry(code, parsed_nodes, metadata, diagram_type=diag_type, svg_output_path=svg_output_path)
        nodes = [node.to_dict() for node in parsed_nodes]
        edges = [edge.to_dict() for edge in parsed_edges]
        groups = [group.to_dict() for group in parsed_groups]
        if extra_metadata:
            metadata.update(extra_metadata)
    elif diag_type == "mindmap":
        parsed_nodes, parsed_edges, extra_metadata = _parse_mindmap(lines)
        _enrich_nodes_with_svg_geometry(code, parsed_nodes, metadata, diagram_type=diag_type, svg_output_path=svg_output_path)
        nodes = [node.to_dict() for node in parsed_nodes]
        edges = [edge.to_dict() for edge in parsed_edges]
        if extra_metadata:
            metadata.update(extra_metadata)

    for node in nodes:
        _promote_node_fields(node)
        _standardize_node_fields(node)
    for edge in edges:
        _promote_edge_fields(edge)
        _standardize_edge_fields(edge)

    directed = diag_type != "mindmap"

    # Phase 2: Remove redundant metadata and styles
    # - No more graph.metadata (source, parser, svg_enrichment)
    # - No more graph.styles (already expanded to nodes)
    # - Keep only essential graph-level info and warnings

    # Clean up remaining metadata
    for node in nodes:
        node.pop("metadata", None)
    for edge in edges:
        edge.pop("metadata", None)
    for group in groups:
        group.pop("metadata", None)

    extras: Dict[str, Any] = {}
    if metadata.get("warnings"):
        extras["warnings"] = metadata["warnings"]
    if metadata.get("sequence_timeline"):
        extras["sequenceTimeline"] = metadata["sequence_timeline"]
    if metadata.get("sequenceTimeline"):
        extras["sequenceTimeline"] = metadata["sequenceTimeline"]

    return build_minimal_ir(
        title=source_id,
        orientation=classification["orientation"],
        nodes=nodes,
        edges=edges,
        groups=groups,
        extras=extras,
    )


def load_sample_irs(csv_path: Path, limit: int = 5) -> List[Dict[str, Any]]:
    """Return placeholder IR documents built from Mermaid CSV rows."""

    documents: List[Dict[str, Any]] = []
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            documents.append(parse_mermaid_code(row.get("code", ""), row.get("id", "")))
            if index + 1 >= limit:
                break
    return documents
