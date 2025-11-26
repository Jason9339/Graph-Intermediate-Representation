# IR Field Mapping Overview

This document tracks the current correspondence between the unified diagram IR and the three supported code formats (TikZ, Graphviz DOT, Mermaid). It will expand as parsers and generators mature.

## Graph-Level Fields

| IR Field | TikZ | Graphviz DOT | Mermaid |
| --- | --- | --- | --- |
| `graph.title` | `\\title{}` (metadata) | `graph [label="..."]` or comment | `title` directive (comment fallback) |
| `graph.directed` | `\\begin{tikzpicture}[->]` | `digraph` vs `graph` | `graph LR` vs `graph TD` |
| `graph.orientation` | `tikzpicture` options (`node distance` etc.) | `rankdir=LR/TB/...` | `graph LR/TB/...` |
| `graph.layout` | stored in metadata | DOT `layout=hierarchical` (if supported) | metadata only |
| `graph.metadata.styles` | TikZ class/預設樣式 (`node.default`, `node.classes`, `edge.default`) | DOT 預設屬性 / subgraph style | Mermaid `classDef` / `linkStyle` 彙整 |
| `graph.metadata.sequence_timeline` | 驗證序列圖訊息與區塊順序 | metadata note | `sequenceDiagram` 解析產生的事件順序 |
| `graph.metadata` 其他欄位 | `metadata` map | `graph [metadata=...]` 或註解 | `%%` 註解 |

## Node Fields

| IR Field | TikZ | Graphviz DOT | Mermaid |
| --- | --- | --- | --- |
| `nodes[*].id` | `\node (id)` | node identifier | node id before brackets |
| `nodes[*].label` | `\node[label]` | `label="..."` | text inside brackets `(label)`/`[label]`/`{label}` |
| `nodes[*].shape` | `shape=rectangle/circle/...` options | `shape=box/circle/...` | bracket type (`[]`, `()`, `{}`) or `:::class` |
| `nodes[*].color` | `draw=<color>` | `color=<hex>` | `style`/`classDef` color |
| `nodes[*].fillColor` | `fill=<color>` | `style="filled", fillcolor=<hex>` | `classDef` background |
| `nodes[*].style` | `dashed`, `thick` etc. via TikZ options | `style="dashed"` or `penwidth` | `style` / `classDef` attributes |
| `nodes[*].width` & `height` | `minimum width/height` | `width/height` | metadata |
| `nodes[*].position` | explicit `at (x,y)` | `pos="x,y"!` or metadata | metadata |
| `nodes[*].metadata.type` | `participant`/`note` 對應自訂樣式 | 協助選擇 shape/class | Mermaid 解析器輸出節點角色 |
| `nodes[*].metadata.styleOverrides` | 以 `{屬性: 值}` 保存 inline CSS | 自訂屬性 | `style X font-weight:bold` → `{ "font-weight": "bold" }` |
| `nodes[*].metadata` 其他欄位 | custom key/value | custom attributes | custom attributes |

## Edge Fields

| IR Field | TikZ | Graphviz DOT | Mermaid |
| --- | --- | --- | --- |
| `edges[*].source` / `target` | `(source) edge (target)` | `source -> target` | `source --> target` |
| `edges[*].directed` | `edge` vs `<->` | `->` vs `--` | `-->` vs `---` |
| `edges[*].label` | `node[above] {label}` | `label="..."` | `: label` suffix |
| `edges[*].style` | `bend left`, `dashed` options | `style="dashed"` | `:::` class or `-.->` etc. |
| `edges[*].color` | `draw=<color>` | `color=<hex>` | `style`/`classDef` |
| `edges[*].arrowHead` | TikZ arrow style option | `arrowhead` attribute | limited arrow types, metadata if unsupported |
| `edges[*].weight` | `line width` or metadata | `weight=<value>` | metadata |
| `edges[*].metadata.type` | `sequence_message` 驅動樣式 | 自訂屬性 | Mermaid 解析器輸出訊息資訊 |
| `edges[*].metadata.arrow_token` | 可用於自訂箭頭樣式 | `arrowhead` | `-->`, `->>`, `--x` 等原始符號 |
| `edges[*].metadata.styleOverrides` | inline CSS (`stroke-dasharray`, `stroke-width` 等) | 自訂屬性 | `linkStyle` 非 default 覆寫 |
| `edges[*].metadata` 其他欄位 | `edge` style comments | custom attributes | custom attributes |

## Group Fields

| IR Field | TikZ | Graphviz DOT | Mermaid |
| --- | --- | --- | --- |
| `groups[*].id` | `\begin{scope}[label=...]` or metadata | `subgraph cluster_id` | `subgraph id` |
| `groups[*].label` | node label in scope comment | `label="..."` | `subgraph label` header |
| `groups[*].nodes` | nodes listed inside scope | nodes inside `subgraph { }` | nodes between `subgraph` and `end` |
| `groups[*].groups` | nested `scope` | nested `subgraph` | nested `subgraph` |
| `groups[*].style` | scope style options | `style="filled"` etc. | `classDef` applied to subgraph |
| `groups[*].color` | `draw`/`fill` options | `color`/`fillcolor` | `style`/`classDef` |
| `groups[*].metadata.type` | `sequence_block` → 可包成 `scope` | `subgraph` 屬性 | `rect ... end` 區塊 |
| `groups[*].metadata` 其他欄位 | comments or custom keys | attributes | attributes |

## Diagram-specific Notes

- **Sequence diagrams**：Mermaid 解析器會輸出 `sequence_timeline` 描述 participant 宣告、訊息、note、rect 區塊的順序；TikZ/DOT 產生器可利用 `metadata.type` 與 `arrow_token` 重現樣式。
- **Mindmap**：節點、邊代表父子層級；第一層節點仍可附帶 `metadata.icons` 供 Mermaid 重建。

## Coverage Notes

- TikZ support for precise positioning and curvature currently lands in `metadata` until full geometry handling is defined.
- Mermaid lacks native width/height controls; store these values under `metadata` for now.
- Shared style definitions (e.g., Mermaid `classDef`, DOT `node/edge` defaults) will map to future `graph.metadata.styles` entries.

Update this document whenever new attributes are added or formats diverge from the baseline behavior.
