"""Mermaid parser with Phase 1 preprocessing and flowchart extraction."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .utils import IRGroup, IREdge, IRNode, normalize_mermaid

DEFAULT_MERMAID_ORIENTATION = "LR"
_ARROW_TOKENS = ["-->", "-.->", "--x", "==>", "~~>", "->", "---", "--"]
SUBGRAPH_PREFIX = "subgraph"
PARTICIPANT_PATTERN = re.compile(r"^participant\s+(\S+)(?:\s+as\s+(.+))?$")
SEQUENCE_ARROWS = ["-->>", "->>", "-->", "->", "--x", "-x", "x--", "x-"]
MINDMAP_NODE_PATTERN = re.compile(r"^([A-Za-z0-9_]+)\((.+)\)$")


def _clean_label(text: str) -> str:
    value = text.strip()
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        value = value[1:-1]
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


def _parse_flowchart(lines: List[str]) -> Tuple[List[IRNode], List[IREdge], List[IRGroup], Dict[str, Any]]:
    nodes: Dict[str, IRNode] = {}
    edges: List[IREdge] = []
    groups: Dict[str, IRGroup] = {}
    group_stack: List[str] = []
    link_styles: List[str] = []
    style_statements: List[str] = []
    unprocessed: List[str] = []

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        if stripped.startswith("flowchart ") or stripped.startswith("graph "):
            continue
        if stripped.startswith("classDef "):
            continue
        if stripped.startswith("linkStyle"):
            link_styles.append(stripped)
            continue
        if stripped.startswith("style "):
            style_statements.append(stripped)
            parts = stripped.split(None, 2)
            if len(parts) >= 3:
                node_id = parts[1]
                node = _ensure_node(nodes, node_id, groups, group_stack)
                overrides = node.metadata.setdefault("style_overrides", [])
                overrides.append(parts[2])
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

    metadata: Dict[str, Any] = {}
    if link_styles:
        metadata["link_styles"] = link_styles
    if style_statements:
        metadata["style_statements"] = style_statements
    if unprocessed:
        metadata["unprocessed"] = unprocessed

    return list(nodes.values()), edges, [group for group in groups.values() if group.nodes], metadata


def _ensure_sequence_node(nodes: Dict[str, IRNode], node_id: str, label: Optional[str] = None) -> IRNode:
    node = nodes.get(node_id)
    if node is None:
        node = IRNode(node_id=node_id, label=label or node_id, shape="rect", metadata={})
        nodes[node_id] = node
    else:
        if label and not node.label:
            node.label = label
    return node


def _parse_sequence(lines: List[str]) -> Tuple[List[IRNode], List[IREdge], Dict[str, Any]]:
    participants: Dict[str, IRNode] = {}
    edges: List[IREdge] = []
    notes: List[str] = []
    rect_sections: List[Dict[str, Any]] = []
    unprocessed: List[str] = []
    rect_stack: List[Dict[str, Any]] = []

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        if stripped == "sequenceDiagram":
            continue
        if stripped.startswith("rect "):
            section = {"header": stripped, "lines": []}
            rect_sections.append(section)
            rect_stack.append(section)
            continue
        if stripped == "end" and rect_stack:
            rect_stack.pop()
            continue
        if rect_stack:
            rect_stack[-1]["lines"].append(stripped)

        participant_match = PARTICIPANT_PATTERN.match(stripped)
        if participant_match:
            ident, alias = participant_match.groups()
            label = alias.strip() if alias else ident
            node = _ensure_sequence_node(participants, ident, label)
            if alias:
                node.metadata["alias"] = alias.strip()
            continue

        if stripped.startswith("note "):
            notes.append(stripped)
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
            target_node = _ensure_sequence_node(participants, dst_token)
            edge = IREdge(source=source_node.node_id, target=target_node.node_id, directed=True, label=label)

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
            edges.append(edge)
            continue

        if stripped.startswith(("loop ", "alt ", "opt ", "par ", "critical ", "box ")):
            unprocessed.append(stripped)
            continue

        unprocessed.append(stripped)

    metadata: Dict[str, Any] = {}
    if notes:
        metadata["notes"] = notes
    if rect_sections:
        metadata["rects"] = rect_sections
    if unprocessed:
        metadata["unprocessed"] = unprocessed

    return [node.to_dict() for node in participants.values()], [edge.to_dict() for edge in edges], metadata


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

    return [node.to_dict() for node in nodes.values()], [edge.to_dict() for edge in edges], metadata


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


def parse_mermaid_code(code: str, source_id: str) -> Dict[str, Any]:
    """Parse Mermaid code into IR-like structures with basic flowchart support."""

    lines = normalize_mermaid(code)
    classification = _classify_diagram(lines)
    metadata: Dict[str, Any] = {
        "source_id": source_id,
        "parser": "mermaid",
        "original_code": code,
        "diagram_type": classification["diagram_type"],
    }
    config_blocks = [line.strip() for line in lines if line.strip().startswith("%%{")]
    if config_blocks:
        metadata["config"] = config_blocks
    class_defs = [line.strip() for line in lines if line.strip().startswith("classDef ")]
    if class_defs:
        metadata["class_defs"] = class_defs

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    groups: List[Dict[str, Any]] = []

    diag_type = classification["diagram_type"]

    if diag_type in {"flowchart", "graph"}:
        parsed_nodes, parsed_edges, parsed_groups, extra_metadata = _parse_flowchart(lines)
        nodes = [node.to_dict() for node in parsed_nodes]
        edges = [edge.to_dict() for edge in parsed_edges]
        groups = [group.to_dict() for group in parsed_groups]
        if extra_metadata:
            metadata.update(extra_metadata)
    elif diag_type == "sequenceDiagram":
        parsed_nodes, parsed_edges, extra_metadata = _parse_sequence(lines)
        nodes = parsed_nodes
        edges = parsed_edges
        if extra_metadata:
            metadata.update(extra_metadata)
    elif diag_type == "mindmap":
        parsed_nodes, parsed_edges, extra_metadata = _parse_mindmap(lines)
        nodes = parsed_nodes
        edges = parsed_edges
        if extra_metadata:
            metadata.update(extra_metadata)

    directed = diag_type != "mindmap"

    return {
        "graph": {
            "title": source_id,
            "directed": directed,
            "orientation": classification["orientation"],
            "layout": "hierarchical",
            "metadata": metadata,
        },
        "nodes": nodes,
        "edges": edges,
        "groups": groups,
    }


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
