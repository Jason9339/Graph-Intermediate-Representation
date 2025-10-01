# Graph Intermediate Representation Playground

This repository experiments with a unified JSON-based IR that can shuttle between
Mermaid, TikZ, and (partially) Graphviz diagram code. The current workflow is:

```
source code (CSV rows) → parser → IR JSON → generator → rendered code
```

The repo is organised to keep raw inputs, intermediate IR, and generated outputs
separate so round-trip checks are straightforward.

## Directory Layout

```
.
├── cli/                   # Command-line entry points for conversion
│   ├── code2ir.py         # code → IR (requires --fmt)
│   └── ir2code.py         # IR  → code (requires --fmt)
├── data/                  # Source CSV files (after running split_cosyn_csv.py)
│   ├── cosyn_id_code.csv
│   ├── cosyn_id_code_mermaid.csv
│   └── ...
├── generators/            # IR → code generators, reused by CLI and tools
├── in/                    # Raw sample snippets (txt) extracted from CSVs
│   ├── mermaid/1.txt … 10.txt
│   ├── latex/1.txt … 5.txt
│   └── graphviz/1.txt … 5.txt
├── out/                   # IR JSON and generated code grouped by format
│   ├── mermaid/{1..10}.json, {1..10}_mermaid.txt, comparison.html
│   └── latex/{1..5}.json, {1..5}_tikz.txt, {1..5}_dot.txt
├── parsers/               # code → IR parsers
├── tools/                 # Utility scripts (sample generation, comparisons)
├── schema/                # IR schema, field mappings
├── ir2code.py             # Standalone CLI wrapper around generators/
└── project.log            # Chronological notes of major changes
```

## Setup

1. **Python environment** (3.10+ recommended)

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
   pip install -U pip
   # Optional: add requirements such as networkx, lark, jsonschema
   ```

2. **(Optional) Rendering toolchain**
   * Graphviz for DOT preview (`brew install graphviz` or `apt-get install graphviz`).
   * Mermaid CLI (`npm i -g @mermaid-js/mermaid-cli`) for PNG export.
   * TeX Live / latexmk if you want TikZ PDFs.

Rendering is not required for the conversion pipeline; the IR round-trip checks
operate purely on text files.

## Working with the CSV Data

*Split & organise source files*

```bash
python split_cosyn_csv.py  # Reads data/cosyn_id_code.csv and writes per-format CSVs
```

*Generate IR samples and decoded snippets*

```bash
# Produce IR JSON for the first 10 Mermaid rows and first 5 TikZ rows.
python tools/generate_ir_samples.py

# Extract plain-text snippets (first N rows) into in/<format>/index.txt.
# This is run automatically by the notebook scripts; rerun manually if needed.
python3 - <<'PY'
import csv
from pathlib import Path
DATA = Path('data/cosyn_id_code_mermaid.csv')
OUT = Path('in/mermaid'); OUT.mkdir(exist_ok=True)
with DATA.open('r', encoding='utf-8', newline='') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader, start=1):
        (OUT / f"{i}.txt").write_text(row['code'], encoding='utf-8')
        if i >= 10:
            break
PY
```

Run `tools/build_mermaid_compare.py` at any time to rebuild the HTML viewer that
renders originals vs generated Mermaid output:

```bash
python tools/build_mermaid_compare.py
# => out/mermaid/comparison.html
```

## Converting Between Code and IR

### code → IR

Use the CLI, choosing the format explicitly:

```bash
python cli/code2ir.py --in in/mermaid/1.txt --fmt mermaid > out/mermaid_custom.ir.json
python cli/code2ir.py --in in/latex/1.txt   --fmt tikz    > out/tikz_custom.ir.json
```

### IR → code

Both the top-level `ir2code.py` and `cli/ir2code.py` accept the same options.
Example using the standalone script:

```bash
python ir2code.py --in out/mermaid/1.json --fmt mermaid > out/mermaid/1_roundtrip.mmd
python ir2code.py --in out/latex/1.json   --fmt tikz    > out/latex/1_roundtrip.tex
python ir2code.py --in out/latex/1.json   --fmt dot     > out/latex/1_roundtrip.dot
```

If you prefer the CLI variant:

```bash
python cli/ir2code.py --in out/mermaid/3.json --fmt mermaid
```

Generators automatically preserve style metadata where possible (e.g. Mermaid
mindmap icons, class definitions, link styles; TikZ node/edge styling; DOT node
attributes).

## Useful Scripts

* `split_cosyn_csv.py` – create per-format CSV files under `data/`.
* `tools/generate_ir_samples.py` – build IR JSON samples (`out/<format>/index.json`).
* `tools/build_mermaid_compare.py` – render HTML comparison for all Mermaid samples.
* `project.log` – running changelog of major operations (kept manually).

## Tips

* The repo keeps *raw inputs* in `in/` and generated artifacts in `out/`. When you
  re-run the tools, they overwrite the corresponding files—commit or back up before
  experimenting.
* Mermaid mindmaps can be picky about syntax. The generator makes sure `%%{init}`
  blocks and `::icon(...)` lines stay nested beneath the owning node.
* Graphviz samples are currently placeholder IR because the CSV only stores Python
  helpers that require runtime data. Mermaid and TikZ have full fidelity.
* Update `tools/generate_ir_samples.py` if you want more (or fewer) rows extracted.

Feel free to adapt the workflow—scripts are small and meant to be hacked on during
exploration.
