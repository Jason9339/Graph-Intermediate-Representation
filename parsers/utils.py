"""Shared utilities and lightweight data models for diagram parsers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_TRIPLE_QUOTE_PATTERN = re.compile(r"(?:[rubf]|rb|br|fr|rf)?(\"\"\"|''')(.*?)(\1)", re.DOTALL)
_TIKZ_ENV_PATTERN = re.compile(r"\\begin\{tikzpicture\}(.*?)\\end\{tikzpicture\}", re.DOTALL)


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
    return preamble.strip(), body.strip(), tikz_body


def normalize_mermaid(code: str) -> List[str]:
    """Normalize Mermaid text into a list of lines without trailing whitespace."""

    text = code.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("\ufeff"):
        text = text[1:]
    return [line.rstrip() for line in text.split("\n")]
