# IR Field Mapping Overview

This document tracks the current correspondence between the unified diagram IR and the three supported code formats (TikZ, Graphviz DOT, Mermaid). It will expand as parsers and generators mature.

## Graph-Level Fields

| IR Field | TikZ | Graphviz DOT | Mermaid |
| --- | --- | --- | --- |
| `graph.title` | `\\title{}` (metadata) | `graph [label="..."]` or comment | `title` directive (comment fallback) |
| `graph.directed` | `\\begin{tikzpicture}[->]` | `digraph` vs `graph` | `graph LR` vs `graph TD` |
| `graph.orientation` | `tikzpicture` options (`node distance` etc.) | `rankdir=LR/TB/...` | `graph LR/TB/...` |
| `graph.layout` | stored in metadata | DOT `layout=hierarchical` (if supported) | metadata only |
| `graph.metadata` | `metadata` block or comments | `graph [metadata=...]` or `#` comments | `%% metadata` comment |

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
| `nodes[*].metadata` | custom key/value | custom attributes | custom attributes |

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
| `edges[*].metadata` | `edge` style comments | custom attributes | custom attributes |

## Group Fields

| IR Field | TikZ | Graphviz DOT | Mermaid |
| --- | --- | --- | --- |
| `groups[*].id` | `\begin{scope}[label=...]` or metadata | `subgraph cluster_id` | `subgraph id` |
| `groups[*].label` | node label in scope comment | `label="..."` | `subgraph label` header |
| `groups[*].nodes` | nodes listed inside scope | nodes inside `subgraph { }` | nodes between `subgraph` and `end` |
| `groups[*].groups` | nested `scope` | nested `subgraph` | nested `subgraph` |
| `groups[*].style` | scope style options | `style="filled"` etc. | `classDef` applied to subgraph |
| `groups[*].color` | `draw`/`fill` options | `color`/`fillcolor` | `style`/`classDef` |
| `groups[*].metadata` | comments or custom keys | attributes | attributes |

## Coverage Notes

- TikZ support for precise positioning and curvature currently lands in `metadata` until full geometry handling is defined.
- Mermaid lacks native width/height controls; store these values under `metadata` for now.
- Shared style definitions (e.g., Mermaid `classDef`, DOT `node/edge` defaults) will map to future `graph.metadata.styles` entries.

Update this document whenever new attributes are added or formats diverge from the baseline behavior.
