# 圖表 IR 工作流程說明（中文）

本專案實驗三種圖表語言（Mermaid / TikZ / Graphviz）與 JSON 中介表示（IR）的互轉。流程核心：

```
程式碼 (CSV) → 解析器 (parsers/) → IR(JSON) → 產生器 (generators/) → 目標程式碼
```

## 目錄概要

```
.
├── README.md              # 英文版使用說明
├── readme.md              # 本檔案，中文版說明
├── data/                  # 原始 CSV 與分拆後的 CSV
├── in/                    # 從 CSV 擷取的純文字樣本 (txt)
│   ├── mermaid/1.txt … 10.txt
│   ├── latex/1.txt … 5.txt
│   └── graphviz/1.txt … 5.txt
├── out/
│   ├── mermaid/           # IR JSON 與 IR→程式碼結果
│   │   ├── 1.json … 10.json
│   │   ├── 1_mermaid.txt … 10_mermaid.txt
│   │   └── comparison.html（原始/生成對照）
│   └── latex/
│       ├── 1.json … 5.json
│       ├── 1_tikz.txt … 5_tikz.txt
│       └── 1_dot.txt  … 5_dot.txt
├── parsers/               # 各語言的 code→IR 解析器
├── generators/            # IR→程式碼的生成器
├── cli/                   # 指令化工具 (code2ir.py / ir2code.py)
├── tools/                 # 輔助腳本 (樣本輸出、比較頁)
└── project.log            # 變更紀錄
```

> Graphviz CSV 目前僅提供 Python helper，缺少對應資料，IR 以 placeholder 為主。

## 建議使用流程

1. **安裝環境**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate              # Windows: .\.venv\Scripts\Activate.ps1
   pip install -U pip
   # 視需要安裝 networkx / lark / jsonschema 等依賴
   ```

2. **分拆原始 CSV**
   ```bash
   python split_cosyn_csv.py              # 產出 data/cosyn_id_code_<format>.csv
   ```

3. **擷取樣本 & 生成 IR**
   ```bash
   python tools/generate_ir_samples.py    # Mermaid 前 10 筆，TikZ 前 5 筆
   ```
   *會同時更新 `out/<format>/index.json` 以及 `in/<format>/index.txt`。*

4. **檢視 Mermaid 對照**
   ```bash
   python tools/build_mermaid_compare.py  # 產出 out/mermaid/comparison.html
   ```

5. **CLI 互轉範例**
   ```bash
   # code → IR
   python cli/code2ir.py --in in/mermaid/1.txt --fmt mermaid > out/mermaid/custom.ir.json
   python cli/code2ir.py --in in/latex/1.txt   --fmt tikz    > out/latex/custom.ir.json

   # IR → code（可使用 ir2code.py 或 cli/ir2code.py）
   python ir2code.py --in out/mermaid/1.json --fmt mermaid > out/mermaid/1_roundtrip.mmd
   python ir2code.py --in out/latex/1.json   --fmt tikz    > out/latex/1_roundtrip.tex
   python ir2code.py --in out/latex/1.json   --fmt dot     > out/latex/1_roundtrip.dot
   ```

## 產生器保留的樣式

- **Mermaid**：
  - Mindmap：保留 `%%{init}`、`::icon(...)` 並維持節點層級。
  - Flowchart：保留 `classDef`、`class`、`style`、`linkStyle`。
- **TikZ**：節點形狀、顏色、填色、邊樣式皆會寫回。
- **Graphviz (DOT)**：節點/邊樣式如 `shape`、`color`、`arrowhead` 等會重建。

## 常用輔助腳本

- `split_cosyn_csv.py`：將 `data/cosyn_id_code.csv` 依前綴拆成 Mermaid / TikZ / Graphviz CSV。
- `tools/generate_ir_samples.py`：刷新 `out/<format>/index.json` 與 `in/<format>/index.txt`。
- `tools/build_mermaid_compare.py`：匯出 Mermaid 原始與生成程式碼的比較頁。

## 注意事項

- 重新執行腳本會覆寫 `out/` 與 `in/` 內的檔案，請視需求備份或提交版本控制。
- Mermaid 對縮排敏感；若自訂產出格式，務必保持正確縮排與語法。
- Graphviz CSV 缺少實際節點/邊資料，只能輸出 placeholder IR，後續若有原始資料可再補強。

如需更多細節或英文說明，請參考專案根目錄的 `README.md`。
