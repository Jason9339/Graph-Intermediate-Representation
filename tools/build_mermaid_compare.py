#!/usr/bin/env python3
"""Generate a comparison HTML for Mermaid originals vs generated outputs."""

from __future__ import annotations

import html
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
IN_DIR = BASE_DIR / "in" / "mermaid"
OUT_DIR = BASE_DIR / "out" / "mermaid"
OUTPUT_FILE = OUT_DIR / "comparison.html"


def collect_indices() -> list[int]:
    indices = set()
    for path in IN_DIR.glob("*.txt"):
        try:
            indices.add(int(path.stem))
        except ValueError:
            continue
    for path in OUT_DIR.glob("*_mermaid.txt"):
        try:
            indices.add(int(path.stem.split("_", 1)[0]))
        except ValueError:
            continue
    return sorted(indices)


def build_section(index: int) -> str:
    in_path = IN_DIR / f"{index}.txt"
    out_path = OUT_DIR / f"{index}_mermaid.txt"
    if not in_path.exists() or not out_path.exists():
        return ""
    in_code = in_path.read_text(encoding="utf-8").strip()
    out_code = out_path.read_text(encoding="utf-8").strip()
    return f"""
    <section>
      <h2>Mermaid Sample {index}</h2>
      <div class=\"row\">
        <div class=\"panel\">
          <h3>Original (in/mermaid/{index}.txt)</h3>
          <div class=\"mermaid\">{html.escape(in_code)}</div>
          <pre>{html.escape(in_code)}</pre>
        </div>
        <div class=\"panel\">
          <h3>Generated (out/mermaid/{index}_mermaid.txt)</h3>
          <div class=\"mermaid\">{html.escape(out_code)}</div>
          <pre>{html.escape(out_code)}</pre>
        </div>
      </div>
    </section>
    """


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sections = [build_section(idx) for idx in collect_indices()]
    sections_html = "".join(filter(None, sections)) or "<p>No matching Mermaid samples found.</p>"

    html_doc = f"""
    <!DOCTYPE html>
    <html lang=\"en\">
    <head>
      <meta charset=\"UTF-8\">
      <title>Mermaid In vs Out Comparison</title>
      <script type=\"module\">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true }});
      </script>
      <style>
        body {{ font-family: Arial, sans-serif; margin: 1.5rem; }}
        section {{ margin-bottom: 3rem; }}
        .row {{ display: flex; gap: 2rem; flex-wrap: wrap; }}
        .panel {{ flex: 1 1 45%; min-width: 320px; }}
        pre {{ background: #f5f5f5; padding: 1rem; overflow: auto; }}
        h2 {{ border-bottom: 1px solid #ccc; padding-bottom: 0.5rem; }}
      </style>
    </head>
    <body>
      <h1>Mermaid Original vs Generated</h1>
      {sections_html}
    </body>
    </html>
    """

    OUTPUT_FILE.write_text(html_doc, encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
