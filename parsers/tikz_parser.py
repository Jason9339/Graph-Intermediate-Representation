"""TikZ parser with Phase 1 preprocessing and metadata capture."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import shutil
import subprocess
import tempfile

from .utils import (
    IRNode,
    IREdge,
    build_minimal_ir,
    extract_tikzpicture_options,
    strip_latex_preamble,
)

DEFAULT_TIKZ_ORIENTATION = "LR"

_LIB_PATTERN = re.compile(r"\\usetikzlibrary\{([^}]*)\}")
_NODE_PATTERN = re.compile(r"\\node[^;]*;", re.MULTILINE)
_DRAW_PATTERN = re.compile(r"\\draw[^;]*;", re.MULTILINE)
_PATH_PATTERN = re.compile(r"\\path[^;]*;", re.MULTILINE)
_EDGE_NODE_LABEL_PATTERN = re.compile(r"node\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")
_EDGE_KEYWORD_PATTERN = re.compile(
    r"\((?P<src>[^)]+)\)\s*edge(?:\[(?P<opts>[^\]]+)\])?\s*(?:node\s*(?:\[[^\]]*\])?\s*\{(?P<label>[^}]*)\})?\s*\((?P<dst>[^)]+)\)"
)
_TIKZSTYLE_PATTERN = re.compile(r"\\tikzstyle\{([^}]+)\}\s*=\s*([^\n]+)")
_TIKZSET_PATTERN = re.compile(r"\\tikzset\{")

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
    label = _clean_text(label_match.group(1)).strip()
    if not label:
        label = node_id

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
        shape=shape or "rect",
        color=color,
        fill_color=fill_color,
        style=style,
        metadata=metadata,
    )
    return node


def _split_style_entries(text: str) -> List[str]:
    entries: List[str] = []
    current: List[str] = []
    depth = 0
    for ch in text:
        if ch == "," and depth == 0:
            entry = "".join(current).strip()
            if entry:
                entries.append(entry)
            current = []
            continue
        current.append(ch)
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(depth - 1, 0)
    trailing = "".join(current).strip()
    if trailing:
        entries.append(trailing)
    return entries


def _extract_style_definitions(text: str) -> Dict[str, str]:
    styles: Dict[str, str] = {}
    for match in _TIKZSTYLE_PATTERN.finditer(text):
        name = match.group(1).strip()
        raw_body = match.group(2).strip().rstrip(";")
        if raw_body.startswith("{") and raw_body.endswith("}"):
            raw_body = raw_body[1:-1]
        elif raw_body.startswith("[") and raw_body.endswith("]"):
            raw_body = raw_body[1:-1]
        if name and raw_body:
            styles[name] = raw_body.strip()
    for block in _iter_tikzset_blocks(text):
        entries = _split_style_entries(block)
        for entry in entries:
            if "/.style" not in entry:
                continue
            name_part, body_part = entry.split("/.style", 1)
            name = name_part.strip()
            body_part = body_part.lstrip("=").strip()
            if body_part.startswith("{") and body_part.endswith("}"):
                body_part = body_part[1:-1]
            if name:
                styles[name] = body_part.strip()
    return styles


def _iter_tikzset_blocks(text: str) -> List[str]:
    blocks: List[str] = []
    position = 0
    while True:
        match = _TIKZSET_PATTERN.search(text, position)
        if not match:
            break
        brace_start = match.end()
        depth = 1
        index = brace_start
        block_chars: List[str] = []
        while index < len(text) and depth > 0:
            ch = text[index]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    index += 1
                    break
            block_chars.append(ch)
            index += 1
        blocks.append("".join(block_chars[:-1] if depth == 0 else block_chars))
        position = index
    return blocks


def _extract_inline_styles(option_text: Optional[str]) -> Dict[str, str]:
    if not option_text:
        return {}
    styles: Dict[str, str] = {}
    for entry in _split_style_entries(option_text):
        if "/.style" not in entry:
            continue
        name_part, body_part = entry.split("/.style", 1)
        name = name_part.strip()
        body_part = body_part.lstrip("=").strip()
        if body_part.startswith("{") and body_part.endswith("}"):
            body_part = body_part[1:-1]
        if name and body_part:
            styles[name] = body_part.strip()
    return styles


def _tokenize_style_body(body: str) -> List[str]:
    cleaned = body.strip()
    if cleaned.startswith("="):
        cleaned = cleaned[1:].strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        cleaned = cleaned[1:-1]
    return _split_style_entries(cleaned)


def _parse_style_definition(body: str) -> Dict[str, Any]:
    tokens = _tokenize_style_body(body)
    attributes: Dict[str, str] = {}
    flags: List[str] = []
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            attributes[key.strip()] = value.strip()
        else:
            flag = token.strip()
            if flag:
                flags.append(flag)
    result: Dict[str, Any] = {}
    if attributes:
        result["attributes"] = attributes
    if flags:
        result["flags"] = flags
    return result


def _normalize_style_definitions(style_defs: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}
    for name, body in style_defs.items():
        parsed = _parse_style_definition(body)
        if parsed:
            normalized[name] = parsed
    return normalized


def _build_style_catalog(
    normalized_styles: Dict[str, Dict[str, Any]],
    node_classes: Set[str],
) -> Dict[str, Any]:
    node_styles: Dict[str, Any] = {}
    edge_styles: Dict[str, Any] = {}
    for name, style in normalized_styles.items():
        target = node_styles if name in node_classes else edge_styles
        target[name] = style
    catalog: Dict[str, Any] = {}
    if node_styles:
        catalog["nodeClasses"] = node_styles
    if edge_styles:
        catalog["edgeClasses"] = edge_styles
    return catalog


def _apply_tikz_class_styles(nodes: List[Dict[str, Any]], style_defs: Dict[str, Dict[str, Any]]) -> None:
    for node in nodes:
        classes = node.get("classes") or []
        for class_name in classes:
            style_info = style_defs.get(class_name)
            if not style_info:
                continue
            attrs = style_info.get("attributes", {})
            fill_value = attrs.get("fill")
            draw_value = attrs.get("draw") or attrs.get("color")
            if fill_value and not node.get("fillColor"):
                node["fillColor"] = fill_value
            if draw_value and not node.get("color"):
                node["color"] = draw_value
            if not node.get("color"):
                flags = style_info.get("flags", [])
                if any(flag.strip().lower() == "draw" for flag in flags):
                    node["color"] = "#000000"


def _strip_pt(value: str) -> Optional[float]:
    value = value.strip()
    if value.endswith("pt"):
        value = value[:-2]
    try:
        return float(value)
    except ValueError:
        return None


def _capture_tikz_geometry(
    tikz_body: str,
    libraries: List[str],
    styles: Dict[str, str],
    node_ids: List[str],
    tikz_options: Optional[str],
    extra_preamble: str,
    svg_output_path: Optional[str] = None,
) -> Tuple[Dict[str, Dict[str, Tuple[float, float]]], Optional[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    if not node_ids:
        return {}, None, warnings
    if shutil.which("pdflatex") is None:
        warnings.append("tikz_enrichment_skipped:pdflatex_not_found")
        return {}, None, warnings

    libs_block = ""
    seen_libs: List[str] = []
    for lib in libraries:
        parts = [item.strip() for item in lib.split(",") if item.strip()]
        for part in parts:
            if part not in seen_libs:
                seen_libs.append(part)
    if seen_libs:
        libs_block = "\n".join(f"\\usetikzlibrary{{{lib}}}" for lib in seen_libs)

    style_entries: List[str] = []
    for name, definition in styles.items():
        clean_name = name.strip()
        clean_def = definition.strip()
        if clean_name and clean_def:
            style_entries.append(f"{clean_name}/.style={{ {clean_def} }}")
    styles_block = ""
    if style_entries:
        styles_block = f"\\tikzset{{{', '.join(style_entries)}}}"

    has_inline_options = tikz_body.lstrip().startswith("[")
    options_clause = ""
    if not has_inline_options and tikz_options:
        options_clause = f"[{tikz_options}]"
    node_list = ",".join(node_ids)

    instrumentation = f"""
\\makeatletter
\\newwrite\\positionfile
\\immediate\\openout\\positionfile=\\jobname.pos
\\def\\WriteAnchor#1#2{{%
  \\expandafter\\ifx\\csname pgf@sh@ns@#1\\endcsname\\relax
  \\else
    \\pgfpointanchor{{#1}}{{#2}}%
    \\begingroup
      \\edef\\x{{\\strip@pt\\pgf@x}}%
      \\edef\\y{{\\strip@pt\\pgf@y}}%
      \\immediate\\write\\positionfile{{#1|#2|\\x|\\y}}%
    \\endgroup
  \\fi
}}
\\foreach \\nodeName in {{{node_list}}}{{%
  \\WriteAnchor{{\\nodeName}}{{center}}%
  \\WriteAnchor{{\\nodeName}}{{east}}%
  \\WriteAnchor{{\\nodeName}}{{west}}%
  \\WriteAnchor{{\\nodeName}}{{north}}%
  \\WriteAnchor{{\\nodeName}}{{south}}%
}}
\\immediate\\closeout\\positionfile
\\makeatother
"""

    filtered_preamble_lines: List[str] = []
    for line in extra_preamble.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("%") or stripped.startswith("\documentclass"):
            continue
        filtered_preamble_lines.append(line)
    extra_preamble_block = "\n".join(filtered_preamble_lines)

    doc_lines: List[str] = [
        "\\documentclass[tikz,border=2pt]{standalone}",
        "\\usepackage{tikz}",
    ]
    if libs_block:
        doc_lines.extend(libs_block.splitlines())
    if styles_block:
        doc_lines.append(styles_block)
    if extra_preamble_block:
        doc_lines.extend(extra_preamble_block.splitlines())
    doc_lines.append("\\begin{document}")
    doc_lines.append(f"\\begin{{tikzpicture}}{options_clause}")
    doc_lines.append(tikz_body)
    doc_lines.append(instrumentation)
    doc_lines.append("\\end{tikzpicture}")
    doc_lines.append("\\end{document}")
    document = "\n".join(doc_lines)

    svg_meta: Optional[Dict[str, Any]] = None
    try:
        with tempfile.TemporaryDirectory(prefix="tikz-pos-") as tmpdir:
            tmp_path = Path(tmpdir)
            tex_path = tmp_path / "diagram.tex"
            tex_path.write_text(document, encoding="utf-8")
            compile_cmd = [
                "pdflatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                tex_path.name,
            ]
            result = subprocess.run(
                compile_cmd,
                cwd=tmp_path,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                warnings.append("tikz_enrichment_failed:pdflatex_error")
                return {}, None, warnings
            pos_path = tmp_path / "diagram.pos"
            if not pos_path.exists():
                warnings.append("tikz_enrichment_failed:missing_pos_file")
                return {}, None, warnings
            pdf_path = tmp_path / "diagram.pdf"
            if pdf_path.exists():
                svg_meta = {
                    "source": "tikz_pdflatex",
                    "nodeCount": len(node_ids),
                }
            geometry: Dict[str, Dict[str, Tuple[float, float]]] = {}
            for line in pos_path.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split("|")
                if len(parts) != 4:
                    continue
                node_id, anchor, x_raw, y_raw = parts
                x_val = _strip_pt(x_raw)
                y_val = _strip_pt(y_raw)
                if x_val is None or y_val is None:
                    continue
                anchors = geometry.setdefault(node_id, {})
                anchors[anchor] = (x_val, y_val)
            if svg_meta is not None:
                svg_meta["matchedInstances"] = len(geometry)
            if svg_meta is not None and svg_output_path:
                svg_dest = Path(svg_output_path)
                svg_dest.parent.mkdir(parents=True, exist_ok=True)
                if shutil.which("dvisvgm") is None:
                    warnings.append("tikz_svg_failed:dvisvgm_not_found")
                else:
                    svg_meta["adapter"] = "dvisvgm"
                    svg_tmp = tmp_path / "diagram.svg"
                    svg_cmd = [
                        "dvisvgm",
                        "--pdf",
                        "--page=1",
                        f"--output={svg_tmp.name}",
                        pdf_path.name,
                    ]
                    svg_result = subprocess.run(
                        svg_cmd,
                        cwd=tmp_path,
                        capture_output=True,
                        text=True,
                    )
                    if svg_result.returncode == 0 and svg_tmp.exists():
                        shutil.copyfile(svg_tmp, svg_dest)
                        svg_meta["svgBytes"] = svg_dest.stat().st_size
                    else:
                        warnings.append("tikz_svg_failed:dvisvgm_error")
            return geometry, svg_meta, warnings
    except Exception:
        warnings.append("tikz_enrichment_failed:exception")
        return {}, svg_meta, warnings


def _promote_tikz_node_metadata(nodes: List[Dict[str, Any]]) -> Set[str]:
    used_classes: Set[str] = set()
    for node in nodes:
        metadata = node.get("metadata")
        if not isinstance(metadata, dict):
            continue
        flags = metadata.pop("flags", [])
        if flags:
            classes = node.setdefault("classes", [])
            for flag in flags:
                clean = flag.strip()
                if clean and clean not in classes:
                    classes.append(clean)
                    used_classes.add(clean)
        options = metadata.pop("options", None)
        if options:
            node.setdefault("layoutHints", {}).update(options)
        if not metadata:
            node.pop("metadata", None)
    return used_classes


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


def _standardize_tikz_node(node: Dict[str, Any]) -> None:
    """Standardize TikZ node fields to unified format."""

    # Rename fillColor → fill
    if "fillColor" in node:
        node["fill"] = node.pop("fillColor")

    # Rename color → stroke
    if "color" in node:
        node["stroke"] = node.pop("color")

    # Convert position object to pos array
    if "position" in node:
        pos_obj = node.pop("position")
        if isinstance(pos_obj, dict):
            node["pos"] = [pos_obj.get("x", 0), pos_obj.get("y", 0)]

    # Convert width, height to size array
    if "width" in node and "height" in node:
        width = node.pop("width")
        height = node.pop("height")
        if width is not None and height is not None:
            node["size"] = [width, height]

    # Clean up None values (including unused style fields)
    keys_to_remove = [key for key, value in list(node.items()) if value is None]
    for key in keys_to_remove:
        node.pop(key)

    # Remove metadata if empty
    if "metadata" in node and not node["metadata"]:
        node.pop("metadata")


def _standardize_tikz_edge(edge: Dict[str, Any]) -> None:
    """Standardize TikZ edge fields to unified format."""

    # Rename color → stroke
    if "color" in edge:
        edge["stroke"] = edge.pop("color")

    # Remove metadata if empty
    if "metadata" in edge and not edge["metadata"]:
        edge.pop("metadata")


def parse_tikz_code(code: str, source_id: str, svg_output_path: Optional[str] = None) -> Dict[str, Any]:
    """Return an IR skeleton enriched with LaTeX metadata."""

    preamble, body, tikz_body = strip_latex_preamble(code)
    style_definitions = _extract_style_definitions(preamble + "\n" + body)
    metadata: Dict[str, Any] = {
        "source": {
            "id": source_id,
            "format": "tikz",
        },
        "parser": "tikz",
    }
    libraries = _extract_libraries(preamble)
    tikz_options: Optional[str] = extract_tikzpicture_options(body)
    inline_styles = _extract_inline_styles(tikz_options)
    for key, value in inline_styles.items():
        style_definitions.setdefault(key, value)
    directed = any(token in tikz_body for token in ("->", "-->", "<->", "rightarrow"))

    nodes, edges = _extract_graph_elements(tikz_body, directed)
    geometry_map, svg_meta, geometry_warnings = _capture_tikz_geometry(
        tikz_body,
        libraries,
        style_definitions,
        [node["id"] for node in nodes],
        tikz_options,
        preamble,
        svg_output_path=svg_output_path,
    )
    if svg_meta:
        metadata["svg_enrichment"] = svg_meta
    if geometry_warnings:
        metadata.setdefault("warnings", []).extend(geometry_warnings)
    for node in nodes:
        node_id = node.get("id")
        if not node_id:
            continue
        anchor_data = geometry_map.get(node_id)
        if not anchor_data:
            continue
        center = anchor_data.get("center")
        if center:
            node["position"] = {"x": center[0], "y": center[1]}
        east = anchor_data.get("east")
        west = anchor_data.get("west")
        if east and west:
            node["width"] = abs(east[0] - west[0])
        north = anchor_data.get("north")
        south = anchor_data.get("south")
        if north and south:
            node["height"] = abs(north[1] - south[1])

    node_class_usage = _promote_tikz_node_metadata(nodes)
    normalized_styles = _normalize_style_definitions(style_definitions)
    if normalized_styles:
        _apply_tikz_class_styles(nodes, normalized_styles)

    # Apply unified format (Phase 2 & 3)
    for node in nodes:
        _standardize_tikz_node(node)
    for edge in edges:
        _standardize_tikz_edge(edge)

    warnings = metadata.get("warnings", [])

    graph_entry: Dict[str, Any] = {
        "title": source_id,
        "directed": directed,
        "orientation": DEFAULT_TIKZ_ORIENTATION,
    }

    # Only preserve warnings if any exist
    if warnings:
        graph_entry["warnings"] = warnings
    # Remove leftover metadata to keep IR minimal
    for node in nodes:
        node.pop("metadata", None)
    for edge in edges:
        edge.pop("metadata", None)

    return build_minimal_ir(
        title=source_id,
        orientation=DEFAULT_TIKZ_ORIENTATION,
        nodes=nodes,
        edges=edges,
        groups=[],
        extras={"warnings": warnings} if warnings else None,
    )


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
