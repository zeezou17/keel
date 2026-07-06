# FP-006 — Fix add-node targeting and parent linking

**Status:** Backlog  
**Priority:** High (UX bug)  
**Depends on:** WP-004, FP-003 (selective drill-down)  
**Related:** [FP-002](planned-canvas-manual-editing.md), [FP-003](planned-selective-drill-down.md)

## Problem

**Add node** does not reliably create nodes where the user expects. Reported behavior:

- New nodes appear at the wrong C4 level or under the wrong parent container.
- C2 containers are created without a `parent_id`, so `composeCanvas` may attach them to the wrong system (or to every system when legacy `parent_id` data is missing).
- When multiple branches are expanded, `getAddNodeContext` can pick an arbitrary expanded container instead of the one the user is focused on.
- Generic names (`New container 3`) and grid positions make the result feel “random” rather than intentional.

Today’s add flow in `frontend/src/App.tsx` (`handleAddNode`) sets `parent_id` only for C3 nodes. C2 nodes are appended to the global C2 architecture file with no link to the expanded system.

## Expected behavior

| User focus | New node lands at |
|------------|-------------------|
| Nothing expanded, nothing selected | C1 (root) |
| One system expanded | C2 container with `parent_id` = that system |
| Container selected or expanded inside a system | C3 component with `parent_id` = that container |
| Node selected (not expanded) | Same level as selected node; correct parent chain |

The new node should appear visually inside the focused group on the composed canvas, not floating with edges to unrelated containers.

## Proposed solution

### Context resolution

- Tighten `getAddNodeContext` in `frontend/src/canvas/expansion.ts` to prefer **selected node** over “first expanded container in set iteration order”.
- When multiple systems are expanded, use selection or last-focused expansion — document the rule in UI (toolbar hint: `Add node (C2 · System Name)`).

### Parent linking

- For C2 adds inside an expanded system: set `node.parent_id` to the system id before `createNode`.
- Validate on save that C2 `parent_id` references a C1 system and C3 `parent_id` references a C2 container.

### Placement

- Default position near the focused group’s bounding box (or offset from selected node), not a global grid index across all nodes in the file.

### UX

- Toolbar label shows target: `Add node (C2 · Payments)` not just `(C2)`.
- Optional: brief toast confirming where the node was created.

## Key files

| Area | File |
|------|------|
| Add handler | `frontend/src/App.tsx` — `handleAddNode`, `addNodeContext` |
| Context logic | `frontend/src/canvas/expansion.ts` — `getAddNodeContext`, `getSystemContainers` |
| API | `frontend/src/api/client.ts` — `createNode` |
| Backend | `keel/architecture_store.py` — `add_node` |

## Acceptance criteria

- [ ] Adding a node with one system expanded creates a C2 container with correct `parent_id`; it renders only under that system
- [ ] Adding with a container selected creates a C3 component in that container’s architecture file
- [ ] With multiple expansions, add targets the selected node’s context (or shows a chooser if ambiguous)
- [ ] No spurious edges or visual attachment to unrelated containers
- [ ] Regression tests for `getAddNodeContext` and C2 `parent_id` composition

## Out of scope

- Full node property editor (see FP-002)
- AI sparring `add_node` actions (separate path in `SparringPanel.tsx`; align after toolbar fix)
