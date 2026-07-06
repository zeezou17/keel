# FP-013 — Manual linking between nodes (edges with text)

**Status:** Backlog  
**Priority:** Medium  
**Depends on:** WP-004, FP-003 (composed canvas)  
**Related:** [FP-002](planned-canvas-manual-editing.md) (broader manual editing), [FP-012](planned-undo-redo.md) (undo edge add/delete)

## Problem

Architecture diagrams express **relationships** between nodes — “uses”, “calls”, “reads from”, “sends events to”, and so on. Today:

| Capability | API today | UI today |
|------------|-----------|----------|
| View edges | Yes (rendered on canvas) | Yes |
| Add edge manually | Via full architecture `PUT` | **No** |
| Edit edge label / type | Via full architecture `PUT` | **No** |
| Delete edge | Via full architecture `PUT` | **No** |

Edges are created by `keel init`, AI sparring, or hand-editing `.keel/architecture/*.json`. Users cannot draw a link between two nodes and describe it in plain text from the UI.

This matters when:

- Init or sparring misses a dependency between systems or containers
- The user wants to document an integration (“HTTPS”, “gRPC”, “async events”) on the arrow itself
- Two nodes are visible on the composed canvas (including inside expanded groups) and should be connected without JSON editing

## Expected behavior

### Add link

- User draws a connection from one node to another (React Flow connect handles or equivalent)
- Keel prompts for **relationship text** (edge `label`) — e.g. “Uses”, “Publishes to”, “Reads/writes”
- Optional: pick or type edge `type` (defaults to a sensible C4 relationship type for the level)
- Edge persists to the correct architecture file (C1, C2, or C3 scope)
- Git dirty indicator updates

### Edit link

- User selects an edge on the canvas
- Small panel or inline editor shows current label and type
- **Save** updates the edge; **Delete** removes only the edge (not the nodes)

### Validation

- No self-loops (source === target)
- Both nodes must exist on the **same diagram level** for v1 (cross-group / cross-level edges deferred — see edge cases)
- Duplicate edge (same source, target, label) — warn or block

### Composed canvas (FP-003)

- Linking works for nodes visible at the same level in the current view (e.g. two C1 systems, two containers inside the same expanded system)
- Edge is stored in the architecture file for that level, not only in React Flow local state

## Proposed solution

### Data model (existing)

`KeelEdge` in `keel/schema.py` already supports:

- `id`, `type`, `source_id`, `target_id`, `label` (human-readable text on the arrow)

No schema change required for v1.

### Backend

Existing route likely sufficient:

- `PUT /api/architecture/{level}` — save full file including updated `edges[]`

Optional v2: dedicated `POST/PUT/DELETE /api/architecture/edge/{id}` for smaller patches.

### Frontend

| File | Work |
|------|------|
| `frontend/src/components/Canvas.tsx` | Enable `onConnect`, edge selection, `edgesUpdatable` / deletable |
| New `EdgeDetailPanel.tsx` or inline popover | Label/type edit, delete edge |
| `frontend/src/App.tsx` | Persist new/edited edges via `saveArchitecture` / `persistArchitecture` |
| `frontend/src/canvas/expansion.ts` | Resolve which architecture file owns an edge when nodes are composed |

### UX flow

```
1. Drag from node A handle → node B
2. Dialog: "Describe this relationship" [Uses API        ]
3. [Add link] → arrow appears with label on canvas
4. Click arrow → edit label or delete
```

## Edge cases

- **Cross-group edges** (node inside expanded system → C1 sibling): document rules; may defer to v2
- **Edges in full-level “View all C2” mode**: same persist path as composed mode (see [FP-009](planned-fix-position-persistence.md))
- **Expanded vs collapsed**: edge endpoints must use stable node IDs from architecture JSON
- **Sparring-generated edges**: manual edits must not be overwritten on next spar apply without warning (future)

## Acceptance criteria

- [ ] User can draw a link between two nodes on the canvas
- [ ] User is prompted for relationship text (label) when creating a link
- [ ] Label is visible on the arrow in the diagram
- [ ] User can select an edge and edit its label
- [ ] User can delete an edge without deleting its nodes
- [ ] Changes persist to `.keel/architecture/*.json` and show in git status
- [ ] Invalid link (self-loop, missing target) shows a clear error

## Out of scope (v1)

- Curved edge routing customization
- Multi-edges with different labels between same pair (allow or block — decide at implementation)
- Automatic edge suggestions from code / drift
- Cross-level edges spanning C1 and C2 in one arrow

## Note on FP-002

[FP-002](planned-canvas-manual-editing.md) covers full manual editing (node fields + edges). **FP-013** is the focused backlog item for **relationship linking with text** — implement as part of FP-002 or as a standalone ship if node editing is deferred.

Pairs with [FP-012](planned-undo-redo.md) once undo covers edge mutations.
