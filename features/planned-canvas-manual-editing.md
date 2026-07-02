# FP-002 — Canvas manual editing

**Status:** Planned  
**Priority:** Next  
**Depends on:** WP-004

## Problem

When Claude or `keel init` produces incorrect architecture, humans have limited ways to fix the diagram:

| Capability | API today | UI today |
|------------|-----------|----------|
| Add node | Yes | Yes (toolbar) |
| Move node | Yes | Yes (drag) |
| Edit node fields | `PUT /api/architecture/node/{id}` | **No** — detail panel is read-only |
| Delete node | `DELETE /api/architecture/node/{id}` | **No** |
| Add edge | Via full architecture save | **No** |
| Edit/delete edge | Via full architecture save | **No** |

Users need to correct AI mistakes without editing JSON by hand.

## Proposed solution

### Node editing (node detail panel)

- Editable fields: `name`, `description`, `technology`, `paths` (globs), `type` (where valid for level)
- **Save** → `updateNode(nodeId, node)`
- **Delete** → confirm dialog → `DELETE` node API (removes connected edges server-side)

### Edge editing (canvas)

- **Add edge** — connect two nodes via React Flow connection line (`onConnect`)
  - Prompt for edge `type` / `label` (or sensible defaults)
  - Generate stable `edge_*` id
- **Select edge** — small panel or context menu: edit label, delete
- Persist via `saveArchitecture` or dedicated edge endpoints

### Backend (may already suffice)

Existing routes in `keel/server.py`:

- `PUT /api/architecture/node/{node_id}`
- `DELETE /api/architecture/node/{node_id}`
- `PUT /api/architecture/{level}` — full file including `edges[]`

Verify `architecture_store.delete_node` removes edges referencing deleted node.

### Frontend work

| File | Changes |
|------|---------|
| `frontend/src/components/NodeDetailPanel.tsx` | Form fields, save, delete |
| `frontend/src/components/Canvas.tsx` | `onConnect`, edge selection, `edgesUpdatable` / `edgesDeletable` |
| `frontend/src/api/client.ts` | `deleteNode()`, optional edge helpers |
| `frontend/src/App.tsx` | Wire delete refresh, edge persistence |

### UX principles

- Prefer explicit **Save** for node fields (avoid accidental edits)
- **Delete node** requires confirmation; show count of edges that will be removed
- New edges validate `source_id` / `target_id` exist on current diagram level
- Git dirty indicator updates after every change (existing behavior)

### Acceptance criteria

- [ ] User can edit node name, description, paths, technology and save
- [ ] User can delete a node from the detail panel
- [ ] User can draw a new arrow between two nodes
- [ ] User can delete an edge from the canvas
- [ ] Changes persist to `.keel/architecture/*.json` and show in git status
- [ ] Invalid edge (same node, missing target) shows clear error

### Out of scope (v1)

- Multi-select bulk delete
- Undo/redo stack
- Import/export diagram as image only (JSON remains source of truth)
