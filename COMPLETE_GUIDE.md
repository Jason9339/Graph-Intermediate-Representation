# Complete Architecture Guide

> 本文檔說明專案的完整架構、設計決策和實作細節

## 專案目標

將三種圖表格式（Mermaid、TikZ、Graphviz）轉換為統一、人類可讀的中間表示（IR）JSON 格式。

**核心理念**：
1. IR 要足夠清楚，讓人看 JSON 就能手繪圖表
2. 不做反向轉換（IR → code），IR 是終點
3. 盡可能提取實際渲染後的座標和尺寸
4. 保持 metadata 簡潔，只保留必要資訊

## 架構概覽

```
Input Diagrams (3 formats)
    ↓
Format-Specific Parsers (3 parsers)
    ↓
Optional: Rendering Engines (mmdc, dot, pdflatex)
    ↓
Layout Extraction (positions, dimensions)
    ↓
Unified IR Schema (JSON)
    ↓
Output (JSON + SVG)
```

## 目錄結構

```
.
├── convert.py              # 統一 CLI 工具（單檔轉換）
├── convert_all.py          # 批次轉換所有格式
├── verify.py               # 驗證轉換結果
├── data/                   # 輸入圖表
│   ├── mermaid/            # Mermaid 圖表 (.txt)
│   ├── latex/              # TikZ 圖表 (.txt)
│   └── graphviz/           # Graphviz Python 程式 (.py)
├── output/                 # 統一輸出目錄
│   ├── mermaid/            # Mermaid → IR
│   ├── tikz/               # TikZ → IR
│   └── graphviz/           # Graphviz → IR
├── parsers/                # 格式解析器
│   ├── __init__.py
│   ├── mermaid_parser.py   # Mermaid 解析器 + SVG 提取
│   ├── mermaid_svg.py      # Mermaid SVG 處理
│   ├── tikz_parser.py      # TikZ 解析器 + PDF/SVG 轉換
│   ├── dot_parser.py       # Graphviz 解析器 + JSON layout
│   └── utils.py            # 共用工具類別
└── schema/                 # IR schema 文檔
    └── mapping.md          # 欄位對應說明
```

## 三種 Parser 實作

### 1. Mermaid Parser (`mermaid_parser.py`)

**工作流程**：
```
Mermaid code (.txt)
    ↓
語法正規化（去除註解、空行）
    ↓
識別圖表類型（flowchart/sequence/mindmap）
    ↓
解析 nodes、edges、styles
    ↓
呼叫 mmdc 產生 SVG
    ↓
從 SVG 提取節點座標和尺寸
    ↓
生成 IR JSON
```

**關鍵功能**：
- CSS/classDef 樣式正規化
- SVG geometry 提取（`mermaid_svg.py`）
- 支援多種圖表類型
- 處理 participant、note、rect 等特殊結構

### 2. TikZ Parser (`tikz_parser.py`)

**工作流程**：
```
TikZ code (.txt)
    ↓
提取 preamble 和 tikzpicture 環境
    ↓
解析 \node、\draw、\path 命令
    ↓
呼叫 pdflatex + dvisvgm 產生 SVG
    ↓
從 SVG 提取座標
    ↓
生成 IR JSON
```

**關鍵功能**：
- LaTeX 環境處理
- TikZ 命令解析
- Coordinate 系統轉換
- PDF → SVG 轉換管線

### 3. Graphviz Parser (`dot_parser.py`)

**工作流程**：
```
Python Graphviz code (.py)
    ↓
執行 Python 生成 DOT source
    ↓
呼叫 dot -Tjson 獲取 layout
    ↓
從 JSON 提取節點、邊、subgraph
    ↓
對應到 IR schema
    ↓
生成 IR JSON + SVG
```

**關鍵功能**：
- Python AST 解析（備用方案）
- DOT JSON layout 提取
- Subgraph → groups 對應
- Shape 名稱對應

## IR Schema（最小版）

頂層只有與繪圖直接相關的欄位：

```json
{
  "title": "圖表標題",
  "orientation": "LR | TB | RL | BT",
  "nodes": [
    {
      "id": "node1",
      "label": "Node 1",
      "shape": "rect",
      "pos": [100, 200],
      "size": [120, 40],
      "fill": "#fff",
      "stroke": "#000",
      "strokeWidth": 2,
      "class": "highlight"
    }
  ],
  "edges": [
    {
      "from": "node1",
      "to": "node2",
      "label": "connects",
      "arrow": true,
      "stroke": "#000",
      "strokeWidth": 2,
      "dash": [6, 4]
    }
  ],
  "groups": [
    {
      "id": "cluster_0",
      "label": "群組",
      "nodes": ["node1", "node2"],
      "fill": "#eee"
    }
  ]
}
```

預設值：`orientation` 預設 `"TB"`、`arrow` 預設 `true`、`shape` 預設 `"rect"`、`label` 預設使用 `id`。沒有 parser/來源 metadata，layout 是否手動以 `pos/size` 是否存在推斷。

## Layout 提取機制

### Mermaid: SVG Parsing

```python
# 1. 使用 mmdc 產生 SVG
mmdc -i input.mmd -o output.svg

# 2. 解析 SVG，尋找節點 <g> 標籤
<g class="node" id="node-xxx" transform="translate(x, y)">
  <rect width="w" height="h"/>
</g>

# 3. 提取 transform、width、height
position = parse_transform(transform_attr)
width = rect.get('width')
height = rect.get('height')
```

### TikZ: Instrumented LaTeX

```latex
% 在 tikzpicture 環境中插入 instrumentation
\begin{tikzpicture}
  \node (a) at (1, 2) {A};
  % 自動輸出: \typeout{NODE a AT \pgfpoint@x, \pgfpoint@y}
\end{tikzpicture}
```

從 LaTeX log 提取座標。

### Graphviz: JSON Output

```bash
# Graphviz 原生支援 JSON 輸出
dot -Tjson input.dot

# JSON 包含完整 layout 資訊
{
  "objects": [
    {
      "name": "node1",
      "pos": "100,200",
      "width": "1.2",
      "height": "0.5"
    }
  ]
}
```

## 統一 CLI 設計

### `convert.py` - 單檔轉換

```python
def convert_file(input_path, output_path, format_type, save_svg):
    # 1. 讀取輸入
    code = read_file(input_path)

    # 2. 自動偵測或使用指定格式
    format_type = format_type or detect_format(code, input_path)

    # 3. 呼叫對應 parser
    if format_type == 'mermaid':
        ir = parse_mermaid_code(code, source_id, svg_path)
    elif format_type == 'tikz':
        ir = parse_tikz_code(code, source_id, svg_path)
    elif format_type == 'graphviz':
        ir = parse_dot_code(code, source_id, svg_path)

    # 4. 儲存 JSON
    save_json(output_path, ir)

    return ir
```

### `convert_all.py` - 批次轉換

```python
def main():
    formats = [
        ("mermaid", "data/mermaid", "output/mermaid"),
        ("tikz", "data/latex", "output/tikz"),
        ("graphviz", "data/graphviz", "output/graphviz"),
    ]

    for format_name, input_dir, output_dir in formats:
        batch_convert(input_dir, output_dir, format_name)
```

## 錯誤處理策略

1. **Parser 失敗**：回退到基本解析（不提取 layout）
2. **Rendering 失敗**：記錄 warning，繼續生成 IR
3. **SVG 提取失敗**：`layout = "auto"`，不包含 position/size
4. **空檔案**：跳過，記錄為 "empty"
5. **部分節點無座標**：保留有座標的，標記 coverage

## 效能考量

1. **批次處理**：一次處理所有檔案，避免重複 import
2. **並行處理**：未來可加入 multiprocessing
3. **快取**：SVG 檔案可快取避免重複渲染
4. **記憶體**：使用 streaming JSON 處理大檔案

## 測試與驗證

### `verify.py` - 驗證工具

```python
def main():
    # 1. 讀取各格式的 conversion_summary.json
    # 2. 統計成功率、節點/邊數量
    # 3. 計算 position coverage
    # 4. 列出 top 5 結果
    # 5. 顯示整體統計
```

**重要指標**：
- 成功率: 95.8% (69/72 檔案)
- 總節點數: 869
- 總邊數: 820
- Position coverage: ~100% (when rendering tools available)

## 擴展性

### 新增格式

1. 在 `parsers/` 建立新 parser
2. 實作 `parse_XXX_code(code, source_id, svg_path)` 函數
3. 更新 `convert.py` 的格式偵測和路由
4. 在 `data/` 建立對應目錄
5. 更新 `convert_all.py` 的格式清單

### IR Schema 擴展

在 `metadata` 中新增欄位，避免破壞現有結構：

```json
"metadata": {
  "custom_field": "value",
  "format_specific": {...}
}
```

## 設計決策紀錄

### 為何使用渲染引擎？

- 手工解析 layout 演算法非常複雜
- 各格式有自己的 layout engine（dot, mmdc, tikz）
- 直接使用官方工具保證正確性

### 為何統一輸出目錄？

- 避免 `output/`、`output_tikz/`、`output_graphviz/` 散落
- 更清楚的專案結構
- 便於批次處理和驗證

### 為何不做 IR → Code？

- 專案目標是提取 IR，不是轉換器
- IR → Code 會損失資訊（如特定語法特性）
- 保持專案範圍聚焦

## 已知限制

1. **Mermaid**：某些複雜圖表（如嵌套 subgraph）可能解析不完整
2. **TikZ**：依賴 pdflatex，自訂 macro 可能不支援
3. **Graphviz**：Python code 需要遵循特定模式（使用 `example_*()` 函數）
4. **SVG 提取**：依賴特定 SVG 結構，格式變化可能導致失敗

## 未來改進

- [ ] 加入 Plantuml 支援
- [ ] 並行批次處理
- [ ] JSON Schema 驗證
- [ ] 更好的錯誤訊息
- [ ] IR viewer (HTML)
- [ ] 效能 profiling

## 參考資源

- Mermaid: https://mermaid.js.org/
- TikZ: https://tikz.dev/
- Graphviz: https://graphviz.org/
- IR Schema: [schema/mapping.md](schema/mapping.md)
