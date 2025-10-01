import csv
from pathlib import Path

# Split cosyn_id_code.csv into separate files based on the id prefix pipeline type.
DATA_DIR = Path("data")
SOURCE = DATA_DIR / "cosyn_id_code.csv"
PREFIX_TO_NAME = {
    "MermaidDiagramPipeline_": DATA_DIR / "cosyn_id_code_mermaid.csv",
    "LaTeXDiagramPipeline_": DATA_DIR / "cosyn_id_code_latex.csv",
    "GraphvizDiagramPipeline_": DATA_DIR / "cosyn_id_code_graphviz.csv",
}

def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Cannot find {SOURCE!s}")

    outputs = {}
    try:
        for prefix, filename in PREFIX_TO_NAME.items():
            f = filename
            handle = f.open("w", newline="", encoding="utf-8")
            writer = csv.writer(handle)
            writer.writerow(["id", "code"])
            outputs[prefix] = (handle, writer)

        with SOURCE.open("r", newline="", encoding="utf-8") as src:
            reader = csv.DictReader(src)
            for row in reader:
                id_value = row.get("id", "")
                for prefix, (handle, writer) in outputs.items():
                    if id_value.startswith(prefix):
                        writer.writerow([row.get("id", ""), row.get("code", "")])
                        break
                else:
                    raise ValueError(f"Unexpected id prefix in row: {id_value}")
    finally:
        for handle, _ in outputs.values():
            handle.close()

if __name__ == "__main__":
    main()
