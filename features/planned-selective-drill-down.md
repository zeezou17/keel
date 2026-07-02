# FP-003 — Selective drill-down (expand in place)

**Status:** Planned  
**Priority:** Next  
**Depends on:** WP-004  
**Related:** [FP-002](planned-canvas-manual-editing.md) (editing inside expanded groups)

## Problem

Today, double-clicking a node **replaces the entire canvas** with the next C-level diagram:

- C1 → click system → **all** C2 containers appear; other C1 systems disappear
- C2 → click container → **only** that container’s C3 components appear

That matches classic C4 “one diagram per level,” but it is disorienting when you want to:

- Compare two systems side by side at C1 while inspecting one system’s containers
- Keep external actors and sibling systems visible while drilling into one branch
- Expand multiple branches (e.g. two systems) without losing the parent context
- Collapse a branch when the canvas gets crowded at C3/C4

Adding a node at C1 and then opening it currently feels like a “zoom into a different world” rather than “open this box.”

## Proposed solution

Replace **global level switching** (for in-canvas navigation) with **per-node expand/collapse** while keeping the parent level visible.

### Core behavior

| Action | Result |
|--------|--------|
| **Single click** | Select node → detail panel (unchanged) |
| **Expand** (chevron, double-click, or detail “Expand”) | Load that node’s children **inline** under a visual group; parent stays on canvas |
| **Expand again** on a child | Nest the next level (C2→C3→C4) inside that branch only |
| **Collapse** (chevron toggle or second expand on same node) | Hide that node’s subtree; siblings and parent context remain |
| **Multi-expand** | Several nodes at the same level can be expanded at once |

### Example (C1 → C2)

```
Before (C1 only):
  [Person] ──► [System A]     [System B] ──► [External API]

After expanding System A only:
  [Person] ──► ┌─ System A ─────────────────┐     [System B] ──► [External API]
               │  [Web App]  [API]  [DB]     │
               └─────────────────────────────┘
```

`System B` stays a C1 box. C1-level edges (person → system, system → external) remain visible. C2 edges appear **inside** System A’s group.

### Interaction model

**Separate select from expand** — accidental drill-down is a major source of confusion today. Keep these distinct:

| Gesture | Purpose |
|---------|---------|
| **Single click** | Select node only → opens detail panel; does **not** change canvas depth |
| **Chevron (▶ / ▼)** on node | Primary expand/collapse control; visible on any node that has children |
| **“Expand” / “Collapse” in detail panel** | Same as chevron; accessible when the node is selected |
| **Double-click** | Shortcut to toggle expand/collapse on that node (replaces today’s full level switch) |
| **Breadcrumb “C1 Context”** | Collapse all expansions; return to root-only view |

Without this split, users who only want to read a node’s description will keep “falling into” the next level.

### Visual grouping

Nested children must not look like unrelated peers on the canvas:

- Render expanded children inside a **group frame** — dashed border, light background tint, parent name in a small header bar
- Apply a **depth tint** per nesting level (e.g. C2 inside C1 is slightly greener/bluer than pure C1 boxes) so depth is obvious at a glance
- Show a **mini depth indicator** on expanded parents (e.g. `C2 · 3` = expanded to C2 with 3 visible children)
- Parent node keeps its C1 styling; the frame wraps children, not the parent label itself
- **Fit view** after expand/collapse should include **all** expanded groups and remaining C1 siblings, not zoom only into the last opened branch

### Collapse all

When several C3/C4 groups are open the canvas gets crowded quickly. Provide fast escape hatches:

- Toolbar button: **“Collapse all”** — closes every expanded branch in one action
- Breadcrumb **“C1 Context”** — same effect (reset to root-only)
- Per-node collapse still works via chevron toggle on each expanded ancestor

Optional v2: soft warning when 3+ C3 groups are expanded at once (“Canvas is busy — collapse some branches?”).

### View full level (escape hatch)

Some users still want the classic C4 “one diagram per level” view — e.g. for screenshots, printing, or scanning every container at once. Keep the old behavior as an explicit opt-in, not the default:

- Breadcrumb item: **“View all C2 containers”** (and similarly C3/C4 when applicable)
- Switches to today’s global level view temporarily; returning to C1 restores selective expansion mode
- Label clearly so users understand they are leaving “expand in place” mode

### Sparring context

The sparring panel should follow **where the user is looking**, not always the root C1 diagram:

- Default context = **selected node** if one is active
- If the user is inside an expanded branch with no selection, use the **deepest expanded node** on that branch
- When sparring suggests new nodes, apply them at the correct child level for that context (e.g. containers inside the expanded system)

Wire `SparringPanel` `level` / `containerId` from expansion state rather than global `view.level` alone.

### Add node targeting

**“Add node”** should create at the **focused context**, not blindly at the root:

| User focus | New node lands at |
|------------|-------------------|
| Nothing expanded, nothing selected | Current root level (C1) |
| System expanded, nothing selected inside | C2 inside that system’s group |
| Container selected inside an expanded system | C3 for that container (or prompt to expand first) |
| Node selected but not expanded | Same level as selected node |

Avoid the today-feeling flow: add at C1 → click → whole canvas jumps to full C2.

### Requirement-driven auto-expand

When the requirements sidebar highlights nodes linked to a requirement, those nodes may live at different depths. Auto-expand ancestor branches so **every linked node is visible** without manual drill-down:

1. User selects a requirement → Keel resolves `linked_node_ids`
2. For each linked node, walk `parent_id` / container chain and expand ancestors as needed
3. Pan/zoom to fit all highlighted nodes
4. Collapse auto-expanded branches when the requirement is deselected (or leave expanded — user preference in v2)

Pairs naturally with the existing requirement → node highlight flow in `Sidebar` / `Canvas`.

### Data & API

Keel already stores levels in separate files (`c1-context.json`, `c2-containers.json`, `c3-{slug}.json`). The canvas becomes a **composed view**:

| Concern | Approach |
|---------|----------|
| Load children | `fetchArchitecture(childLevel, parentId)` when a node expands (lazy load) |
| Cache | In-memory map `expandedNodeId → ArchitectureFile` to avoid re-fetch on collapse/expand |
| Edges across levels | C1 edges stay global; child edges scoped inside group; document rules for edges that cross group boundaries |
| Positions | Parent group position from C1 file; child positions from C2/C3 files (existing `position_x/y`) |
| Persistence | Expansion **state** is UI-only (`localStorage` or session); architecture JSON unchanged |

### React Flow implementation notes

| Area | Work |
|------|------|
| `frontend/src/components/Canvas.tsx` | Parent/child nodes (`parentId`), group nodes, nested edges |
| `frontend/src/canvas/expansion.ts` | Expansion state, compose flat React Flow nodes from multiple architecture files |
| `frontend/src/App.tsx` | Replace `loadView` drill-down with expansion state; breadcrumbs → collapse all |
| `frontend/src/components/NodeDetailPanel.tsx` | Expand / Collapse actions, show current depth |
| `frontend/src/components/SparringPanel.tsx` | Sparring context = deepest expanded node or selected node |

Consider React Flow **sub flows** / **group nodes** for bounded child layouts; run **auto-layout** inside a group on first expand if children have no positions.

### Edge cases

- **External systems** at C2 inside a C1 system — show inside group; C1 `external` nodes may also appear outside if linked at context level
- **No children** — chevron hidden or disabled; detail panel shows “No containers yet” with action to add first child at the correct level
- **Many expanded branches** — “Collapse all” + optional clutter warning at 3+ expanded C3 groups
- **Cross-group edges** — document and test edges that connect a node inside an expanded group to a C1 sibling or external

### Keyboard shortcuts (v1)

| Key | Action |
|-----|--------|
| `Enter` | Expand selected node (if it has children) |
| `Backspace` | Collapse selected node’s subtree |
| `Esc` | Clear selection; does not collapse expansions |
| `Shift + Esc` | Collapse all (optional) |

### UX enhancements (v2 — optional follow-ups)

| Feature | Description |
|---------|-------------|
| **Focus mode** | When one expanded group is selected, dim non-expanded branches (opacity ~40%). Keeps full context on canvas but draws the eye to the active branch. Toggle in toolbar or hold `F`. |
| **Pin expanded** | Pin icon on a group header locks that branch open while “Collapse all” or collapsing siblings affects only unpinned branches. Useful when comparing two systems but cleaning up a third. |
| **Animated expand/collapse** | Short height/opacity transition when opening a group (polish, not required for v1). |
| **Sync with node detail** | Detail panel shows breadcrumb trail inside the tree: `C1 › System A › API Container`. |
| **Requirement deselect behavior** | User preference: collapse auto-expanded branches on deselect vs leave them open. |

### Acceptance criteria

- [ ] Expanding a C1 system shows only that system’s C2 children in a group frame; other C1 nodes remain visible
- [ ] User can expand two or more C1 systems simultaneously
- [ ] Chevron or detail-panel control collapses an expanded node’s subtree
- [ ] Single click selects without expanding; double-click toggles expand (no full canvas level replace)
- [ ] C3/C4 expansion works the same way inside an expanded C2 container
- [ ] C1-level edges remain visible when one system is expanded
- [ ] “Collapse all” and breadcrumb “C1 Context” reset every expansion
- [ ] “View all C2 containers” (escape hatch) shows classic full-level diagram
- [ ] Expansion state survives page reload (`localStorage`, keyed by repo)
- [ ] Sparring panel uses selected or deepest-expanded node as context
- [ ] “Add node” creates at the focused context level (see table above)
- [ ] Selecting a requirement auto-expands ancestors so all linked nodes are visible
- [ ] Group frames, depth tint, and mini depth indicator (`C2 · N`) render correctly

### Out of scope (v1)

- Replacing separate `.keel` architecture files with a single merged file
- Animated transitions between expand/collapse (see v2)
- Syncing expansion state across machines via git
- Focus mode and pin-expanded (see v2)

### Priority note

This feature likely has **higher day-to-day impact than FP-001** (resizable sidebars) for architecture exploration. It pairs strongly with **FP-002** (manual edit/delete) — users will want to edit nodes inside expanded groups, not only view them. Suggested implementation order: **FP-003 → FP-002 → FP-001**, unless layout pain on small screens is blocking you first.

### Technical note

Keel already stores C1/C2/C3 in separate JSON files under `.keel/architecture/`. Selective drill-down is a **composed canvas view** — lazy-fetch children per expanded node — not a schema or storage change. React Flow parent/group nodes and sub-flows are the intended layout mechanism.
