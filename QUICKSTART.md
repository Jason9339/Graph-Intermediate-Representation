# Quick Start Guide

## Installation

```bash
# Clone repository
git clone <repo-url>
cd Graph-Intermediate-Representation

# Install Python dependencies
pip install graphviz

# Optional: Install rendering tools for layout extraction
# Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Graphviz (Ubuntu/Debian)
sudo apt-get install graphviz

# TeX Live for TikZ (Ubuntu/Debian)
sudo apt-get install texlive texlive-latex-extra dvisvgm
```

## Three Simple Commands

### 1. Convert Everything

```bash
python convert_all.py
```

Converts all diagrams from `data/` to `output/`:
- **Mermaid**: 40 files → `output/mermaid/`
- **TikZ**: 17 files → `output/tikz/`
- **Graphviz**: 15 files → `output/graphviz/`

Each format gets its own subdirectory with:
- `*.json` - IR files
- `*.svg` - Visual references
- `conversion_summary.json` - Statistics

### 2. Verify Conversion

```bash
python verify.py
```

Shows:
- Success rate per format
- Total nodes/edges processed
- Coverage statistics
- Top results

Expected output:
```
✓ Overall success rate: 95.8%
Total files:  72
Success:      69
Total nodes:  869
Total edges:  820
```

### 3. Convert Single File

```bash
# Auto-detect format from extension
python convert.py data/graphviz/hello.py

# Specify format explicitly
python convert.py --format mermaid input.txt -o output.json

# Batch convert directory
python convert.py --batch data/mermaid --format mermaid -o custom_output/
```

## Understanding the Output

Each JSON file contains:

```json
{
  "graph": {
    "title": "...",
    "layout": "manual",  // "manual" = has positions, "auto" = no positions
    "orientation": "LR",
    "metadata": {
      "json_enrichment": {  // Only present if layout extraction succeeded
        "nodeCount": 10,
        "nodesWithPosition": 10,
        "nodesWithSize": 10
      }
    }
  },
  "nodes": [
    {
      "id": "node1",
      "label": "Label",
      "position": {"x": 100, "y": 200},  // Present if layout extracted
      "width": 120,
      "height": 40
    }
  ],
  "edges": [...],
  "groups": [...]  // Subgraphs/clusters
}
```

## Project Structure

```
.
├── convert.py          # Single file converter
├── convert_all.py      # Batch converter (all formats)
├── verify.py           # Verification tool
├── data/               # Input diagrams
│   ├── mermaid/        # *.txt files
│   ├── latex/          # *.txt (TikZ)
│   └── graphviz/       # *.py files
├── output/             # Generated IR
│   ├── mermaid/
│   ├── tikz/
│   └── graphviz/
└── parsers/            # Format parsers
    ├── mermaid_parser.py
    ├── tikz_parser.py
    └── dot_parser.py
```

## Common Tasks

### Add New Diagram

1. Place file in appropriate `data/` subdirectory
2. Run `python convert_all.py`
3. Check `output/<format>/` for result

### Convert Custom File

```bash
python convert.py my_diagram.mmd -o my_output.json
```

### Debug Failed Conversion

```bash
python verify.py  # See which files failed
cat output/<format>/conversion_summary.json  # See detailed errors
```

## What Gets Extracted

### All Formats
- Node IDs, labels, shapes
- Edge connections, labels, directions
- Groups/subgraphs
- Style information

### With Layout Extraction
- Node positions (x, y coordinates)
- Node dimensions (width, height)
- Bounding boxes for groups

### When Layout Extraction Fails
- Graph structure is still preserved
- `layout` field = "auto" (instead of "manual")
- No `position`, `width`, `height` fields
- Warning in metadata

## Tips

1. **Check tool availability**: The converters work without rendering tools but won't extract positions
2. **Batch operations**: Use `convert_all.py` instead of running `convert.py` in a loop
3. **Large files**: SVG files can be large (up to 400KB for complex diagrams)
4. **Verification**: Always run `verify.py` after batch conversion
5. **Git**: Add `output/` to `.gitignore` (generated files)

## Troubleshooting

### "mmdc not found"
Install Mermaid CLI: `npm install -g @mermaid-js/mermaid-cli`

### "dot not found"
Install Graphviz: `sudo apt-get install graphviz`

### "pdflatex not found"
Install TeX Live: `sudo apt-get install texlive`

### No positions in output
- Check if rendering tool is installed
- Look for warnings in metadata
- Converter still works, just no layout info

### Empty or failed conversion
- Check `conversion_summary.json` for details
- Verify input file format matches specified format
- Look for syntax errors in source diagram

## Next Steps

- See [README.md](README.md) for full documentation
- See [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) for architecture details
- Check [schema/mapping.md](schema/mapping.md) for IR field definitions
