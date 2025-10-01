"""Shared helpers for IR to code generators."""

from __future__ import annotations

from typing import Any, Dict, List


def hex_to_tikz_color(value: str) -> str:
    return value


def hex_to_dot_color(value: str) -> str:
    return value


def shape_map_to_dot(shape: str) -> str:
    mapping = {
        "rect": "box",
        "rectangle": "box",
        "box": "box",
        "circle": "circle",
        "ellipse": "ellipse",
        "oval": "ellipse",
        "diamond": "diamond",
        "parallelogram": "parallelogram",
        "trapezium": "trapezium",
        "stadium": "oval",
        "hexagon": "hexagon",
    }
    return mapping.get((shape or "rect").lower(), "box")


def shape_map_to_tikz(shape: str) -> str:
    key = (shape or "rect").lower()
    if key in {"rect", "rectangle", "box", "parallelogram", "trapezium", "hexagon"}:
        return "rectangle"
    if key in {"circle", "ellipse", "oval", "stadium"}:
        return "circle"
    if key in {"diamond", "rhombus"}:
        return "diamond"
    return "rectangle"


def style_map_to_tikz(style: str) -> List[str]:
    result: List[str] = []
    text = (style or "").lower()
    if "filled" in text:
        result.append("fill")
    if "dashed" in text:
        result.append("dashed")
    if "dotted" in text:
        result.append("dotted")
    if "thick" in text or "bold" in text:
        result.append("thick")
    return result


def style_map_to_dot(style: str) -> str:
    text = (style or "").lower()
    if "dashed" in text:
        return "dashed"
    if "dotted" in text:
        return "dotted"
    if "bold" in text or "thick" in text:
        return "bold"
    return "solid"


def arrow_map_to_dot(arrow: str) -> str:
    mapping = {
        "normal": "normal",
        "vee": "vee",
        "diamond": "diamond",
        "ediamond": "ediamond",
        "obox": "obox",
        "crow": "crow",
        "tee": "tee",
        "dot": "dot",
        "none": "none",
    }
    return mapping.get((arrow or "normal").lower(), "normal")


def orientation_to_rankdir(value: str) -> str:
    mapping = {"TB": "TB", "BT": "BT", "LR": "LR", "RL": "RL"}
    return mapping.get((value or "TB").upper(), "TB")


def orientation_to_mermaid(value: str) -> str:
    return orientation_to_rankdir(value)


def escape_label(text: str) -> str:
    return (text or "").replace("\n", "\\n")


def ensure_metadata(entry: Dict[str, Any]) -> Dict[str, Any]:
    metadata = entry.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    return metadata
