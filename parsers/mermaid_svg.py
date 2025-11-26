"""Utilities for rendering Mermaid diagrams to SVG and extracting geometry."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set, Tuple
from xml.etree import ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
XHTML_NS = "http://www.w3.org/1999/xhtml"
NS_MAP = {"svg": SVG_NS, "html": XHTML_NS}


class MermaidRenderError(RuntimeError):
    """Raised when Mermaid CLI rendering fails."""


@dataclass
class SvgNodeGeometry:
    """Geometric metadata recovered from a rendered Mermaid SVG node."""

    label: str
    center_x: float
    center_y: float
    width: Optional[float]
    height: Optional[float]
    raw_class: str

    def to_position(self) -> Dict[str, float]:
        return {"x": self.center_x, "y": self.center_y}


def render_mermaid_to_svg(code: str, save_svg_path: Optional[str] = None) -> str:
    """Render Mermaid code to SVG via the mermaid CLI.

    Args:
        code: Mermaid diagram code
        save_svg_path: Optional path to save the generated SVG file

    Returns:
        SVG content as string
    """

    with tempfile.TemporaryDirectory(prefix="mermaid-") as tmpdir:
        workdir = Path(tmpdir)
        input_path = workdir / "diagram.mmd"
        output_path = workdir / "diagram.svg"
        input_path.write_text(code, encoding="utf-8")
        puppeteer_config = workdir / "puppeteer-config.json"
        puppeteer_config.write_text(
            json.dumps({"args": ["--no-sandbox", "--disable-setuid-sandbox"]}),
            encoding="utf-8",
        )
        command = [
            "mmdc",
            "-i",
            str(input_path),
            "-o",
            str(output_path),
            "--puppeteerConfigFile",
            str(puppeteer_config),
        ]
        try:
            process = subprocess.run(command, capture_output=True, text=True, check=False)
        except FileNotFoundError as exc:
            raise MermaidRenderError("Mermaid CLI 'mmdc' is not available in PATH") from exc
        if process.returncode != 0:
            raise MermaidRenderError(process.stderr.strip() or "Mermaid CLI failed")
        try:
            svg_content = output_path.read_text(encoding="utf-8")
            # Save SVG if path provided
            if save_svg_path:
                save_path = Path(save_svg_path)
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_text(svg_content, encoding="utf-8")
            return svg_content
        except FileNotFoundError as exc:
            raise MermaidRenderError("Mermaid CLI did not produce SVG output") from exc


def _parse_translate(transform: str) -> Tuple[float, float]:
    """Return translate offsets (x, y) parsed from an SVG transform string."""

    match = re.search(r"translate\(([^,\s]+)[,\s]+([^)]+)\)", transform)
    if not match:
        return 0.0, 0.0
    try:
        return float(match.group(1)), float(match.group(2))
    except ValueError:
        return 0.0, 0.0


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        match = re.search(r"[-+]?[0-9]*\.?[0-9]+", value)
        if not match:
            return None
        try:
            return float(match.group(0))
        except ValueError:
            return None


def _collect_text(node: ET.Element) -> List[str]:
    """Recursively collect textual fragments from an XML subtree."""

    fragments: List[str] = []
    text = (node.text or "").strip()
    if text:
        fragments.append(text)
    for child in list(node):
        fragments.extend(_collect_text(child))
        tail = (child.tail or "").strip()
        if tail:
            fragments.append(tail)
    return fragments


def _iter_svg_nodes(root: ET.Element) -> Iterator[ET.Element]:
    """Yield <g> elements from the SVG tree."""

    yield from root.findall(".//svg:g", NS_MAP)


def _extract_shape_geometry(group: ET.Element) -> Tuple[Optional[float], Optional[float], float, float]:
    """Return (width, height, offset_x, offset_y) for the primary shape in a node."""

    for child in list(group):
        local_name = child.tag.split("}")[-1]
        if local_name == "rect":
            width = _to_float(child.get("width"))
            height = _to_float(child.get("height"))
            x = _to_float(child.get("x")) or 0.0
            y = _to_float(child.get("y")) or 0.0
            offset_x = x + (width or 0) / 2 if width is not None else 0.0
            offset_y = y + (height or 0) / 2 if height is not None else 0.0
            return width, height, offset_x, offset_y
        if local_name == "circle":
            radius = _to_float(child.get("r"))
            cx = _to_float(child.get("cx")) or 0.0
            cy = _to_float(child.get("cy")) or 0.0
            width = height = 2 * radius if radius is not None else None
            offset_x = cx
            offset_y = cy
            return width, height, offset_x, offset_y
        if local_name == "ellipse":
            rx = _to_float(child.get("rx"))
            ry = _to_float(child.get("ry"))
            cx = _to_float(child.get("cx")) or 0.0
            cy = _to_float(child.get("cy")) or 0.0
            width = 2 * rx if rx is not None else None
            height = 2 * ry if ry is not None else None
            offset_x = cx
            offset_y = cy
            return width, height, offset_x, offset_y
    return None, None, 0.0, 0.0


def _is_relevant_group(group: ET.Element, diagram_type: Optional[str]) -> bool:
    class_tokens: Set[str] = set((group.get("class") or "").split())
    if diagram_type in {"flowchart", "graph"}:
        return "node" in class_tokens
    if diagram_type == "sequenceDiagram":
        if class_tokens & {"actor", "note"}:
            return True
    if diagram_type == "mindmap":
        if "node" in class_tokens or "nodeLabel" in class_tokens:
            return True
    if "node" in class_tokens:
        return True
    # Fallback to checking for visible shape-content combinations
    has_shape = False
    for tag in ("rect", "circle", "ellipse", "polygon", "path"):
        if group.find(f"svg:{tag}", NS_MAP) is not None:
            has_shape = True
            break
    if not has_shape:
        return False
    text_node = group.find(".//svg:text", NS_MAP)
    foreign_object = group.find(".//svg:foreignObject", NS_MAP)
    return text_node is not None or foreign_object is not None


def extract_node_geometries(svg_text: str, diagram_type: Optional[str] = None) -> List[SvgNodeGeometry]:
    """Extract node label and geometry information from a Mermaid SVG."""

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise MermaidRenderError(f"Failed to parse Mermaid SVG: {exc}") from exc

    geometries: List[SvgNodeGeometry] = []
    for group in _iter_svg_nodes(root):
        if not _is_relevant_group(group, diagram_type):
            continue
        transform = group.get("transform") or ""
        translate_x, translate_y = _parse_translate(transform)
        width, height, offset_x, offset_y = _extract_shape_geometry(group)
        center_x = translate_x + offset_x
        center_y = translate_y + offset_y
        label_fragments: List[str] = []
        foreign_object = group.find(".//svg:foreignObject", NS_MAP)
        if foreign_object is not None:
            label_fragments = _collect_text(foreign_object)
        if not label_fragments:
            text_node = group.find(".//svg:text", NS_MAP)
            if text_node is not None:
                label_fragments = _collect_text(text_node)
        label = " ".join(fragment for fragment in label_fragments if fragment)
        geometries.append(
            SvgNodeGeometry(
                label=label.strip(),
                center_x=center_x,
                center_y=center_y,
                width=width,
                height=height,
                raw_class=group.get("class") or "",
            )
        )
    return geometries
