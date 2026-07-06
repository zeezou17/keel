# FP-008 — Delete node from the UI

**Status:** In Progress  
**Priority:** High (UX gap)  
**Depends on:** WP-004  
**Related:** [FP-002](planned-canvas-manual-editing.md) (broader manual editing), [FP-012](planned-undo-redo.md) (undo after delete)

## Problem

Once a node is created (via **Add node**, AI sparring, or `keel init`), there is **no way to remove it from the diagram in the UI**. Users must edit `.keel/architecture/*.json` by hand or revert via git.

This is especially painful when:

- **Add node** creates unwanted or misplaced nodes (see [FP-006](planned-fix-add-node-targeting.md)).
- Sparring or init suggests nodes the user does not want.
- The user is iterating on the architecture and needs to clean up mistakes.

The backend already supports deletion:

- `DELETE /api/architecture/node/{node_id}` in `keel/server.py`
- `delete_node()` in `keel/architecture_store.py` (removes node and connected edges)

The node detail panel (`frontend/src/components/NodeDetailPanel.tsx`) is read-only and has no delete action.

## Expected behavior

- User selects a node → detail panel shows **Delete** (appears on click/selection).
- **Empty node** (no edges, children, linked requirements/ADRs, or path globs) → deletes immediately.
- **Non-empty node** → confirmation dialog listing what is attached; user must confirm.
- Confirming removes the node and its edges from the correct architecture file (C1, C2, or C3 container scope).
- Canvas and expansion cache refresh; git dirty indicator updates.
- If the node has children (e.g. deleting a system with containers), treat as non-empty and require confirmation.

## Proposed solution

### Node detail panel

- Add **Delete** button (destructive styling).
- Confirmation dialog: node name, level, and count of edges that will be removed.
- Call `deleteNode(nodeId)` from `frontend/src/api/client.ts` (add client helper if missing).

### State refresh

After delete, update the correct slice of app state:

| Node level | Update |
|------------|--------|
| C1 | `setC1Architecture` |
| C2 | `setC2Architecture` |
| C3 | `cacheChildArchitecture` for parent container |

Clear selection if the deleted node was selected. Collapse expansion subtree if the deleted node was an expanded ancestor.

### Edge cases

- Deleting a container with cached C3 architecture: remove or orphan child file (document; prefer deleting `.keel/architecture/c3-{id}.json` or leaving file with warning).
- Deleting last node in a diagram: allow (empty architecture is valid).
- Requirement / ADR links referencing the node: surface warning if `req_ids` or doc links exist.

## Key files

| Area | File |
|------|------|
| UI | `frontend/src/components/NodeDetailPanel.tsx` |
| API client | `frontend/src/api/client.ts` — add `deleteNode` |
| App wiring | `frontend/src/App.tsx` — refresh state after delete |
| Backend | `keel/architecture_store.py` — `delete_node` (verify edge cleanup) |

## Acceptance criteria

- [ ] User can delete a selected C1, C2, or C3 node from the detail panel
- [ ] Confirmation dialog prevents accidental deletion
- [ ] Connected edges are removed server-side; canvas reflects change immediately
- [ ] Git dirty indicator updates after delete
- [ ] Deleting expanded node cleans up expansion state appropriately

## Out of scope (v1)

- Bulk multi-select delete
- Undo/redo (see [FP-012](planned-undo-redo.md))
- Full inline edit of node fields (see FP-002)

## Note on FP-002

This item is the **minimum viable fix** for delete-only. [FP-002](planned-canvas-manual-editing.md) covers full manual editing (edit fields, add/delete edges). Implementing FP-008 unblocks users immediately; fold remaining FP-002 scope in when prioritizing canvas editing.
