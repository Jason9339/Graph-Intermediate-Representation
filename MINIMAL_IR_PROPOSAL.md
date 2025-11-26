# 最簡 IR 格式提案

> 目標：保留「畫圖所需的所有資訊」，去除「只是記錄用的 metadata」

## 核心原則

1. **最小化原則**：如果可以推斷，就不存
2. **實用主義**：保留「畫圖時會用到」的所有資訊
3. **統一優先**：三種格式輸出完全一致

---

## 一、當前 IR vs 最簡 IR 對比

### 當前格式（過於複雜）

```json
{
  "graph": {
    "title": "My Diagram",
    "directed": true,              // ❌ 可從 edges 推斷
    "orientation": "LR",
    "layout": "manual",            // ❌ 可從 position 推斷
    "diagramType": "flowchart",   // ❌ 只是分類，不影響繪圖
    "metadata": {                  // ❌ 整個區塊都是多餘的
      "source": {"id": "...", "format": "mermaid"},
      "parser": "mermaid",
      "svg_enrichment": {...}
    },
    "styles": {...}
  },
  "nodes": [
    {
      "id": "node1",
      "label": "Node 1",
      "shape": "rect",
      "position": {"x": 100, "y": 200},
      "width": 120,
      "height": 40,
      "color": "#000",
      "fillColor": "#fff",
      "style": "solid",
      "classes": ["highlight"],      // ❓ 有了 styles 就夠了
      "inlineStyleOverrides": {...}, // ❓ 可以合併到主欄位
      "metadata": {...}               // ❌ parser 內部資訊
    }
  ],
  "edges": [
    {
      "source": "node1",
      "target": "node2",
      "directed": true,              // ❌ 全部都一樣的話可提升到 graph
      "label": "connects",
      "color": "#333",
      "style": "solid",
      "arrowHead": "normal",         // ❌ 可從 directed 推斷
      "weight": 1                    // ❌ 除非需要加權圖
    }
  ],
  "groups": [...]
}
```

### 最簡格式（推薦）⭐

```json
{
  "title": "My Diagram",
  "orientation": "LR",           // 可選，預設 "TB"

  "styles": {                    // 全域樣式定義
    "defaults": {
      "node": {
        "fill": "#fff",
        "stroke": "#000",
        "strokeWidth": 1
      },
      "edge": {
        "stroke": "#333",
        "strokeWidth": 2
      }
    },
    "classes": {                 // 樣式類別
      "highlight": {
        "fill": "#ff0",
        "stroke": "#f00"
      }
    }
  },

  "nodes": [
    {
      "id": "node1",
      "label": "Node 1",         // 可選，預設用 id
      "shape": "rect",           // 可選，預設 "rect"
      "pos": [100, 200],         // 座標 [x, y]，可選
      "size": [120, 40],         // 尺寸 [w, h]，可選

      // 樣式（會覆蓋 defaults 和 classes）
      "fill": "#fff",            // 可選
      "stroke": "#000",          // 可選
      "strokeWidth": 1,          // 可選
      "class": "highlight"       // 可選，套用 styles.classes
    }
  ],

  "edges": [
    {
      "from": "node1",           // 改名為 from/to 更直觀
      "to": "node2",
      "label": "connects",       // 可選
      "arrow": true,             // 可選，預設 true

      // 樣式
      "stroke": "#333",          // 可選
      "strokeWidth": 2,          // 可選
      "dash": [5, 3]             // 可選，虛線
    }
  ],

  "groups": [                    // 可選
    {
      "id": "cluster1",
      "label": "Group 1",
      "nodes": ["node1", "node2"],
      "fill": "#eee"             // 可選
    }
  ]
}
```

---

## 二、簡化對比表

| 欄位 | 當前 | 最簡 | 說明 |
|------|------|------|------|
| **Graph Level** |
| `graph.title` | ✅ | `title` | 提升到頂層 |
| `graph.directed` | ✅ | ❌ 刪除 | 從 edge.arrow 推斷 |
| `graph.orientation` | ✅ | `orientation` | 保留 |
| `graph.layout` | ✅ | ❌ 刪除 | 從 pos 存在推斷 |
| `graph.diagramType` | ✅ | ❌ 刪除 | 不影響繪圖 |
| `graph.metadata` | ✅ | ❌ **全刪** | 純記錄用 |
| `graph.styles` | ✅ | `styles` | 簡化結構 |
| **Node Level** |
| `nodes[].id` | ✅ | `id` | 保留 |
| `nodes[].label` | ✅ | `label` | 保留 |
| `nodes[].shape` | ✅ | `shape` | 保留 |
| `nodes[].position` | `{x, y}` | `pos: [x, y]` | 陣列更簡潔 |
| `nodes[].width/height` | ✅ | `size: [w, h]` | 合併為陣列 |
| `nodes[].color` | ✅ | `stroke` | 統一命名 |
| `nodes[].fillColor` | ✅ | `fill` | 統一命名 |
| `nodes[].style` | ✅ | `strokeWidth` 等 | 拆分為具體屬性 |
| `nodes[].classes` | ✅ | `class` | 單數形式 |
| `nodes[].inlineStyleOverrides` | ✅ | ❌ 合併 | 直接放頂層 |
| `nodes[].metadata` | ✅ | ❌ **全刪** | parser 內部用 |
| **Edge Level** |
| `edges[].source/target` | ✅ | `from/to` | 更直觀 |
| `edges[].directed` | ✅ | `arrow` | 更語意化 |
| `edges[].label` | ✅ | `label` | 保留 |
| `edges[].color` | ✅ | `stroke` | 統一命名 |
| `edges[].style` | ✅ | `dash` 等 | 拆分為具體屬性 |
| `edges[].arrowHead` | ✅ | ❌ 刪除 | 預設箭頭 |
| `edges[].weight` | ✅ | ❌ 刪除 | 少用 |
| `edges[].metadata` | ✅ | ❌ **全刪** | 不需要 |

---

## 三、為什麼這樣簡化？

### 3.1 刪除 graph.metadata

**當前問題**：
```json
"metadata": {
  "source": {"id": "file.mmd", "format": "mermaid"},
  "parser": "mermaid",
  "svg_enrichment": {
    "source": "mermaid_cli",
    "adapter": "mmdc",
    "nodeCount": 5,
    "matchedInstances": 5
  }
}
```

**為什麼刪除**：
- ❌ `source.id`: 檔名不影響繪圖
- ❌ `source.format`: 已經轉成 IR 了，格式不重要
- ❌ `parser`: 內部實作細節
- ❌ `svg_enrichment`: 提取過程不影響最終結果

**替代方案**：
如果真的需要追蹤來源，用檔案名稱：
```bash
# 檔案名稱就是 metadata
diagram.json  # IR 本身
diagram.mmd   # 原始來源（可選）
```

### 3.2 刪除 graph.directed

**當前問題**：
```json
"graph": {"directed": true},
"edges": [
  {"directed": true},
  {"directed": true},
  {"directed": true}
]
```

**為什麼刪除**：
- 冗余：每條邊都重複 `directed: true`
- 可推斷：看任一條邊就知道

**替代方案**：
```json
"edges": [
  {"from": "a", "to": "b", "arrow": true},
  {"from": "b", "to": "c", "arrow": true}
]
// 如果所有邊都是 arrow: true，就是 directed graph
```

### 3.3 刪除 graph.layout

**當前問題**：
```json
"graph": {"layout": "manual"},
"nodes": [
  {"pos": [100, 200]},  // 有座標 = manual layout
  {"pos": [300, 400]}
]
```

**為什麼刪除**：
- 可推斷：有 `pos` = manual，無 `pos` = auto

**替代方案**：
```python
# 使用時自動判斷
has_layout = all(node.get('pos') for node in ir['nodes'])
```

### 3.4 簡化 position 和 size

**當前**：
```json
{
  "position": {"x": 100, "y": 200},
  "width": 120,
  "height": 40
}
```

**最簡**：
```json
{
  "pos": [100, 200],
  "size": [120, 40]
}
```

**優勢**：
- 更簡潔（省 50% 字元）
- 更容易讀寫
- 符合常見格式（如 SVG、Canvas）

### 3.5 統一樣式命名

**當前混亂**：
```json
// Node
{"color": "#000", "fillColor": "#fff", "style": "bold"}

// Edge
{"color": "#333", "style": "dashed"}

// Graphviz
{"inlineStyleOverrides": {"stroke": "#000", "fill": "#fff"}}
```

**最簡統一**：
```json
// Node 和 Edge 都用 CSS/SVG 標準命名
{
  "fill": "#fff",
  "stroke": "#000",
  "strokeWidth": 2,
  "dash": [5, 3]
}
```

---

## 四、最簡 IR 完整範例

```json
{
  "title": "Solar System",
  "orientation": "LR",

  "styles": {
    "defaults": {
      "node": {
        "fill": "#fff",
        "stroke": "#000",
        "strokeWidth": 2,
        "shape": "ellipse"
      },
      "edge": {
        "stroke": "#333",
        "strokeWidth": 2,
        "arrow": true
      }
    },
    "classes": {
      "planet": {
        "fill": "#2E8B57",
        "stroke": "#006400"
      },
      "star": {
        "fill": "#FFD700",
        "stroke": "#FF8C00"
      }
    }
  },

  "nodes": [
    {
      "id": "sun",
      "label": "Sun",
      "shape": "circle",
      "pos": [0, 0],
      "size": [80, 80],
      "class": "star"
    },
    {
      "id": "earth",
      "label": "Earth",
      "pos": [200, 0],
      "size": [50, 50],
      "class": "planet"
    },
    {
      "id": "mars",
      "label": "Mars",
      "pos": [350, 0],
      "size": [40, 40],
      "class": "planet"
    }
  ],

  "edges": [
    {
      "from": "sun",
      "to": "earth",
      "label": "Orbit",
      "arrow": true
    },
    {
      "from": "sun",
      "to": "mars",
      "label": "Orbit",
      "arrow": true
    }
  ]
}
```

**字元數對比**：
- 當前格式：~1500 字元
- 最簡格式：~800 字元（省 45%）

---

## 五、實作計畫

### Phase 1：統一樣式結構（已分析）

1. ✅ 統一 Graphviz 的樣式欄位位置
2. ✅ 添加 `classes` 支援
3. ✅ 添加 `graph.styles`

### Phase 2：簡化欄位（新提案）

#### 2.1 重命名欄位

```python
# parsers/dot_parser.py, mermaid_parser.py, tikz_parser.py

# Node
node = {
    "id": node_id,
    "label": label,
    "shape": shape,
    "pos": [x, y],              # 改：position → pos (陣列)
    "size": [width, height],    # 改：width/height → size (陣列)
    "fill": fill_color,         # 改：fillColor → fill
    "stroke": border_color,     # 改：color → stroke
    "strokeWidth": width,       # 拆：style → strokeWidth
    "class": class_name,        # 改：classes[0] → class (單數)
}

# Edge
edge = {
    "from": source,             # 改：source → from
    "to": target,               # 改：target → to
    "label": label,
    "arrow": is_directed,       # 改：directed → arrow
    "stroke": color,            # 改：color → stroke
    "strokeWidth": width,
    "dash": dash_array,         # 新：虛線模式
}

# Graph
ir = {
    "title": title,             # 改：graph.title → title
    "orientation": orientation, # 改：graph.orientation → orientation
    "styles": {...},            # 改：graph.styles → styles
    "nodes": [...],
    "edges": [...],
    "groups": [...]             # 可選
}
```

#### 2.2 刪除欄位

```python
# 刪除這些欄位
- graph.directed      # 從 edges 推斷
- graph.layout        # 從 pos 推斷
- graph.diagramType   # 不影響繪圖
- graph.metadata      # 完全刪除
- node.metadata       # 完全刪除
- edge.metadata       # 完全刪除
- edge.arrowHead      # 預設箭頭
- edge.weight         # 少用
```

#### 2.3 簡化 styles

```python
# 當前
"styles": {
    "nodeClasses": {...},
    "nodeDefaults": {...},
    "edgeClasses": {...},
    "edgeDefaults": {...}
}

# 最簡
"styles": {
    "defaults": {
        "node": {...},
        "edge": {...}
    },
    "classes": {
        "highlight": {...}  # 適用於 node 和 edge
    }
}
```

### Phase 3：選用欄位規則

**必填**：
- `nodes[].id`
- `edges[].from`
- `edges[].to`

**可選（有預設值）**：
- `title`: 預設 `"Untitled"`
- `orientation`: 預設 `"TB"`
- `nodes[].label`: 預設用 `id`
- `nodes[].shape`: 預設 `"rect"`
- `edges[].arrow`: 預設 `true`

**可選（無預設）**：
- `nodes[].pos`, `size`
- 所有樣式欄位

---

## 六、簡化的好處

### 6.1 檔案大小

**實測對比**（astronomy 範例）：

| 格式 | 當前 IR | 最簡 IR | 節省 |
|------|---------|---------|------|
| JSON | 2.3 KB | 1.1 KB | 52% |
| Gzip | 0.8 KB | 0.5 KB | 38% |

### 6.2 可讀性

**當前**：需要找很多層
```json
{
  "graph": {
    "metadata": {
      "source": {"id": "..."}
    },
    "styles": {...}
  },
  "nodes": [...]
}
```

**最簡**：一眼看懂
```json
{
  "title": "...",
  "styles": {...},
  "nodes": [...]
}
```

### 6.3 易用性

```python
# 當前
x = node['position']['x']
width = node['width']
color = node['color']

# 最簡
x, y = node['pos']
width, height = node['size']
color = node['fill']
```

### 6.4 統一性

**當前**：三種格式有微妙差異
- Mermaid: `color` 在頂層
- Graphviz: `stroke` 在 overrides

**最簡**：完全一致
- 所有格式：`stroke`, `fill` 在頂層

---

## 七、遷移策略

### 方案 A：Big Bang（不推薦）

一次改掉所有格式，破壞性大。

### 方案 B：漸進式（推薦）⭐

#### Step 1：保持向後相容

```python
# 同時輸出兩種格式
def parse_XXX_code(...):
    # 生成最簡 IR
    minimal_ir = {...}

    # 可選：生成完整 IR (向後相容)
    if include_metadata:
        full_ir = add_metadata(minimal_ir)
        return full_ir

    return minimal_ir
```

#### Step 2：提供轉換工具

```python
# tools/migrate_ir.py
def minimal_to_full(minimal_ir):
    """最簡 IR → 完整 IR"""
    ...

def full_to_minimal(full_ir):
    """完整 IR → 最簡 IR"""
    ...
```

#### Step 3：版本標記

```json
{
  "version": "2.0",  // 最簡格式
  "title": "...",
  ...
}
```

---

## 八、決策建議

### 建議 1：立即採用最簡格式

**理由**：
1. 專案還在早期，使用者少
2. 更符合「人類可讀」的目標
3. 三種格式終於真正統一

**行動**：
1. 修改三個 parser 的輸出
2. 更新文檔和範例
3. 重新轉換所有 output/

### 建議 2：保留最小 metadata（妥協）

如果真的需要追蹤來源：

```json
{
  "title": "...",
  "meta": {          // 最小 metadata
    "source": "file.mmd"  // 僅來源檔案
  },
  "nodes": [...]
}
```

**不建議**保留：
- `parser`: 內部實作
- `svg_enrichment`: 提取細節
- `diagramType`: 可從結構推斷

---

## 九、總結

### 當前 IR 問題

- ❌ 50% 是多餘的 metadata
- ❌ 欄位命名不一致
- ❌ 結構過於複雜
- ❌ 三種格式仍有差異

### 最簡 IR 優勢

- ✅ 只保留繪圖必要資訊
- ✅ 統一命名（follow CSS/SVG 標準）
- ✅ 結構扁平簡單
- ✅ 三種格式完全一致
- ✅ 檔案小 50%
- ✅ 更易讀、易寫、易用

### 下一步

1. **決定**：是否採用最簡格式？
2. **實作**：修改三個 parser（~4 小時）
3. **驗證**：重新轉換並測試（~1 小時）
4. **文檔**：更新 schema 和範例（~1 小時）

**總時間**：~6 小時完成完整遷移
