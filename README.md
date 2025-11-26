# Graph Intermediate Representation (IR) Converter

A unified tool to convert diagram source code (Mermaid, TikZ/LaTeX, Graphviz) into **one** format-consistent intermediate representation (IR) in JSON.

## Requirements & install

- Python 3.10+
- `graphviz` Python package (`pip install graphviz`)
- Optional renderers for layout extraction:
  - Mermaid: `@mermaid-js/mermaid-cli`
  - TikZ: `pdflatex`, `dvisvgm`
  - Graphviz: `dot`

Quick install (Debian/Ubuntu):
```bash
sudo apt-get install graphviz texlive texlive-latex-extra texlive-pictures dvisvgm
npm install -g @mermaid-js/mermaid-cli
```

## Convert your own diagram

The tool is meant to run on **your** files (Mermaid/TikZ/Graphviz).

### Single file
```bash
# Auto-detect format (Mermaid, TikZ/LaTeX, or Graphviz .py/.dot)
python convert.py path/to/diagram.mmd

# Force a format and custom output path
python convert.py --format tikz path/to/diagram.tex -o my_ir.json

# Skip SVG generation if you only need JSON
python convert.py --no-svg path/to/diagram.py
```

### Batch a directory
```bash
python convert.py --batch path/to/dir --format mermaid -o out_dir/
```

### Dependency check
- `dot --version` (Graphviz layout)
- `mmdc -V` (Mermaid CLI) — optional; without it you still get parsing but no coordinates
- `pdflatex --version` and `dvisvgm --version` (TikZ geometry) — optional

If a renderer is missing, the converter falls back to parsing only (IR will lack `pos/size`).

## What’s in this repo

- **output/** — sample conversion results from the bundled test set (JSON + SVG)
- **data/** — bundled diagrams used for validation
- **convert.py** — CLI for your files
- **convert_all.py / verify.py** — validation against the bundled data
- **parsers/** — format-specific parsers
- **schema/** — minimal IR schema example

## Validation (internal dataset)

Use these only to re-run the built-in tests, not for end users:
```bash
python convert_all.py   # regenerates output/ from data/
python verify.py        # shows success/coverage stats
```

## Features

- **Three formats**: Mermaid, TikZ/LaTeX, Graphviz
- **Layout extraction** via rendering engines when available
- **Unified minimal IR** across formats
- **Optional SVG** alongside JSON
- **Batch processing** for folders

## Directory Structure

```
.
├── convert.py           # Single file converter (CLI)
├── convert_all.py       # Batch converter for all formats
├── verify.py            # Verification and statistics
├── data/                # Input diagrams
│   ├── mermaid/         # Mermaid .txt files + PNG references
│   ├── latex/           # TikZ .txt files + PDF references
│   └── graphviz/        # Graphviz .py files + PNG references
├── output/              # Unified output directory
│   ├── mermaid/         # Converted Mermaid → JSON + SVG
│   ├── tikz/            # Converted TikZ → JSON + SVG
│   └── graphviz/        # Converted Graphviz → JSON + SVG
├── parsers/             # Format-specific parsers
│   ├── mermaid_parser.py
│   ├── tikz_parser.py
│   └── dot_parser.py (graphviz)
└── schema/              # IR schema documentation

```

## Minimal IR Schema

All parsers now emit the minimal, drawing-focused IR:

```json
{
  "title": "diagram_name",
  "orientation": "LR",
  "nodes": [
    {"id": "n1", "label": "Node 1", "shape": "rect", "pos": [100, 200], "size": [120, 40], "fill": "#fff", "stroke": "#000"}
  ],
  "edges": [
    {"from": "n1", "to": "n2", "label": "connects", "arrow": true, "stroke": "#000", "dash": [6, 4]}
  ],
  "groups": [
    {"id": "cluster_0", "label": "Group", "nodes": ["n1", "n2"], "fill": "#eee"}
  ]
}
```

Defaults: `orientation` → `"TB"` when missing, `arrow` → `true`, `shape` → `"rect"`, `label` falls back to `id`. Layout is inferred from presence of `pos/size`; no parser metadata is stored.

## Design Philosophy

1. **Human-Readable IR**: The JSON output should be clear enough that someone could manually redraw the diagram
2. **Layout-Aware**: When possible, extract actual rendered positions and dimensions
3. **Clean Metadata**: Only essential diagram info, no redundant source code
