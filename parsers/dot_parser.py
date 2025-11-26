"""Graphviz parser with JSON layout extraction."""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .utils import IRNode, IREdge, IRGroup, build_minimal_ir, extract_triple_quoted_strings

DEFAULT_DOT_ORIENTATION = "TB"

_IMPORT_PATTERN = re.compile(r"^(?:from\s+\S+\s+import\s+\S+|import\s+\S+)")
_COMMENT_PATTERN = re.compile(r"comment\s*=\s*(['\"])(.+?)\1")
_RANKDIR_PATTERN = re.compile(r"rankdir\s*=\s*['\"]([A-Z]{2})['\"]")
_LAYOUT_PATTERN = re.compile(r"layout\s*=\s*['\"]([a-zA-Z0-9_]+)['\"]")

# Shape mapping from Graphviz to IR
SHAPE_MAPPING = {
    "box": "rect",
    "rectangle": "rect",
    "ellipse": "ellipse",
    "circle": "circle",
    "diamond": "diamond",
    "doublecircle": "double-circle",
    "Mdiamond": "diamond",
    "Msquare": "rect",
    "plaintext": "text",
}


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


def _generate_dot_source(python_code: str) -> Optional[str]:
    """Execute Python code to generate DOT source."""
    try:
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            temp_py = Path(f.name)
            # Modify code to return DOT source instead of viewing
            modified_code = python_code.replace('.view()', '')
            # Add code to print the source
            modified_code += '\n\nif __name__ == "__main__":\n'
            # Find the function name
            func_match = re.search(r'def\s+(example_\w+|create_\w+|build_\w+)\s*\(', modified_code)
            if func_match:
                func_name = func_match.group(1)
                modified_code += f'    g = {func_name}()\n'
            else:
                # Try to find variable assignment
                var_match = re.search(r'(\w+)\s*=\s*graphviz\.(Di)?[Gg]raph', modified_code)
                if var_match:
                    func_name = None
                else:
                    return None
            modified_code += '    print(g.source)\n'
            f.write(modified_code)

        # Execute Python to get DOT source
        result = subprocess.run(
            ['python3', str(temp_py)],
            capture_output=True,
            text=True,
            timeout=10
        )
        temp_py.unlink()

        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


def _render_dot_to_json(dot_source: str) -> Optional[Dict[str, Any]]:
    """Render DOT source to JSON layout using Graphviz."""
    if not shutil.which('dot'):
        return None

    try:
        result = subprocess.run(
            ['dot', '-Tjson'],
            input=dot_source,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
        return None
    except Exception:
        return None


def _parse_position(pos_str: str) -> Optional[Tuple[float, float]]:
    """Parse Graphviz position string 'x,y' to tuple."""
    if not pos_str:
        return None
    try:
        parts = pos_str.split(',')
        if len(parts) >= 2:
            return (float(parts[0]), float(parts[1]))
    except (ValueError, AttributeError):
        pass
    return None


def _points_to_inches(value: float, dpi: float = 72.0) -> float:
    """Convert Graphviz points to inches."""
    return value / dpi


def _extract_nodes_from_json(json_layout: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Extract node information from Graphviz JSON layout."""
    nodes_by_gvid = {}
    nodes_by_name = {}

    objects = json_layout.get('objects', [])
    for obj in objects:
        # Skip subgraphs
        if 'nodes' in obj:
            continue

        gvid = obj.get('_gvid')
        name = obj.get('name', '')

        # Parse position
        pos = None
        pos_str = obj.get('pos', '')
        if pos_str:
            parsed = _parse_position(pos_str)
            if parsed:
                pos = {'x': parsed[0], 'y': parsed[1]}

        # Parse dimensions (convert from inches to points, approximately)
        width = obj.get('width')
        height = obj.get('height')
        if width:
            width = float(width) * 72  # Convert inches to points
        if height:
            height = float(height) * 72

        # Extract shape
        shape = obj.get('shape', 'ellipse')
        shape = SHAPE_MAPPING.get(shape, shape)

        # Extract style attributes
        color = obj.get('color')
        fillcolor = obj.get('fillcolor')
        style = obj.get('style', '')

        # Build node info
        node_info = {
            'name': name,
            'label': obj.get('label', name),
            'shape': shape,
            'position': pos,
            'width': width,
            'height': height,
        }

        # Add style info if present
        if color:
            node_info['color'] = color
        if fillcolor:
            node_info['fillColor'] = fillcolor
        if style:
            node_info['style'] = style

        nodes_by_gvid[gvid] = node_info
        nodes_by_name[name] = node_info

    return nodes_by_name


def _extract_edges_from_json(json_layout: Dict[str, Any], nodes_by_gvid: Dict[int, str]) -> List[Dict[str, Any]]:
    """Extract edge information from Graphviz JSON layout."""
    edges = []

    # First pass: build gvid to name mapping
    gvid_to_name = {}
    for obj in json_layout.get('objects', []):
        if 'nodes' not in obj:  # Regular node
            gvid = obj.get('_gvid')
            name = obj.get('name')
            if gvid is not None and name:
                gvid_to_name[gvid] = name

    # Extract edges
    for edge in json_layout.get('edges', []):
        tail_gvid = edge.get('tail')
        head_gvid = edge.get('head')

        if tail_gvid is None or head_gvid is None:
            continue

        source = gvid_to_name.get(tail_gvid)
        target = gvid_to_name.get(head_gvid)

        if not source or not target:
            continue

        edge_info = {
            'source': source,
            'target': target,
            'label': edge.get('label', ''),
        }

        # Extract style
        style = edge.get('style')
        color = edge.get('color')
        if style:
            edge_info['style'] = style
        if color:
            edge_info['color'] = color

        edges.append(edge_info)

    return edges


def _extract_groups_from_json(json_layout: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract subgraph/cluster information from Graphviz JSON layout."""
    groups = []

    # Build gvid to name mapping for nodes
    gvid_to_name = {}
    for obj in json_layout.get('objects', []):
        if 'nodes' not in obj:
            gvid = obj.get('_gvid')
            name = obj.get('name')
            if gvid is not None and name:
                gvid_to_name[gvid] = name

    # Extract subgraphs
    for obj in json_layout.get('objects', []):
        if 'nodes' in obj:  # This is a subgraph
            group_name = obj.get('name', '')
            label = obj.get('label', group_name)

            # Convert node gvids to names
            node_gvids = obj.get('nodes', [])
            node_names = [gvid_to_name[gvid] for gvid in node_gvids if gvid in gvid_to_name]

            # Parse bounding box
            bb_str = obj.get('bb', '')
            bb = None
            if bb_str:
                try:
                    coords = [float(x) for x in bb_str.split(',')]
                    if len(coords) == 4:
                        bb = {
                            'x': coords[0],
                            'y': coords[1],
                            'width': coords[2] - coords[0],
                            'height': coords[3] - coords[1],
                        }
                except (ValueError, AttributeError):
                    pass

            group_info = {
                'id': group_name,
                'label': label,
                'nodes': node_names,
            }

            # Add style info
            color = obj.get('color')
            style = obj.get('style')
            if color:
                group_info['color'] = color
            if style:
                group_info['style'] = style
            if bb:
                group_info['boundingBox'] = bb

            groups.append(group_info)

    return groups


def parse_dot_code(code: str, source_id: str, svg_output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse Python Graphviz code to IR with JSON layout enrichment.

    Args:
        code: Python code using graphviz library
        source_id: Identifier for the source
        svg_output_path: Optional path to save SVG output

    Returns:
        IR document with nodes, edges, and groups
    """
    warnings = []
    metadata: Dict[str, Any] = {
        "source": {
            "id": source_id,
            "format": "graphviz",
        },
        "parser": "graphviz",
    }

    # Step 1: Generate DOT source from Python code
    dot_source = _generate_dot_source(code)
    if not dot_source:
        warnings.append("Failed to generate DOT source from Python code")
        # Fallback to basic parsing
        parsed_nodes, parsed_edges = _collect_dot_calls(code)
        nodes = [node.to_dict() for node in parsed_nodes]
        edges = [edge.to_dict() for edge in parsed_edges]

        metadata["warnings"] = warnings
        return build_minimal_ir(
            title=source_id,
            orientation=DEFAULT_DOT_ORIENTATION,
            nodes=nodes,
            edges=edges,
            groups=[],
            extras={"warnings": warnings} if warnings else None,
        )

    # Step 2: Render DOT to JSON layout
    json_layout = _render_dot_to_json(dot_source)
    if not json_layout:
        warnings.append("Graphviz JSON rendering failed")

    # Step 3: Extract metadata from DOT source
    directed = json_layout.get('directed', True) if json_layout else ('digraph' in dot_source)
    title = json_layout.get('name', source_id) if json_layout else source_id

    orientation = DEFAULT_DOT_ORIENTATION
    rankdir_match = _RANKDIR_PATTERN.search(code)
    if rankdir_match:
        orientation = rankdir_match.group(1)
    elif json_layout and 'rankdir' in json_layout:
        orientation = json_layout['rankdir']

    # Step 4: Extract nodes, edges, and groups
    if json_layout:
        nodes_map = _extract_nodes_from_json(json_layout)
        nodes = []
        for node_name, node_info in nodes_map.items():
            node = {
                "id": node_name,
                "label": node_info.get('label', node_name),
                "shape": node_info.get('shape', 'ellipse'),
            }

            # Add position as pos array (unified format)
            if node_info.get('position'):
                pos = node_info['position']
                node['pos'] = [pos['x'], pos['y']]

            # Add size as array (unified format)
            if node_info.get('width') and node_info.get('height'):
                node['size'] = [node_info['width'], node_info['height']]

            # Add styles directly to node (unified format - no inlineStyleOverrides)
            if node_info.get('color'):
                node['stroke'] = node_info['color']
            if node_info.get('fillColor'):
                node['fill'] = node_info['fillColor']
            if node_info.get('style'):
                node['style'] = node_info['style']

            nodes.append(node)

        edges = []
        edge_list = _extract_edges_from_json(json_layout, {})
        for edge_info in edge_list:
            edge = {
                "source": edge_info['source'],
                "target": edge_info['target'],
                "directed": directed,
            }

            if edge_info.get('label'):
                edge['label'] = edge_info['label']

            # Add styles directly to edge (unified format - no inlineStyleOverrides)
            if edge_info.get('style'):
                edge['style'] = edge_info['style']
            if edge_info.get('color'):
                edge['stroke'] = edge_info['color']

            edges.append(edge)

        groups = _extract_groups_from_json(json_layout)
    else:
        # Fallback to basic parsing
        parsed_nodes, parsed_edges = _collect_dot_calls(code)
        nodes = [node.to_dict() for node in parsed_nodes]
        edges = [edge.to_dict() for edge in parsed_edges]
        groups = []

    # Step 5: Optionally generate SVG
    if svg_output_path and dot_source:
        try:
            svg_result = subprocess.run(
                ['dot', '-Tsvg'],
                input=dot_source,
                capture_output=True,
                text=True,
                timeout=30
            )
            if svg_result.returncode == 0:
                Path(svg_output_path).write_text(svg_result.stdout, encoding='utf-8')
        except Exception as e:
            warnings.append(f"SVG generation failed: {e}")

    # Unified format: minimal graph structure
    # Remove leftover metadata for minimal output
    for node in nodes:
        node.pop("metadata", None)
    for edge in edges:
        edge.pop("metadata", None)
    for group in groups:
        group.pop("metadata", None)

    extras = {"warnings": warnings} if warnings else None

    return build_minimal_ir(
        title=title,
        orientation=orientation,
        nodes=nodes,
        edges=edges,
        groups=groups,
        extras=extras,
    )
