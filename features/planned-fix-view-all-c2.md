# FP-007 — Fix “View all C2” escape hatch

**Status:** Backlog  
**Priority:** Medium (UX bug)  
**Depends on:** WP-004, FP-003 (selective drill-down)  
**Related:** [FP-003](planned-selective-drill-down.md)

## Problem

The toolbar **View all C2** button is meant to be an escape hatch to the classic C4 “one diagram per level” view (see FP-003). In practice it feels useless because:

- Clicking it replaces the composed expand-in-place canvas with the flat C2 architecture file, so all expanded groups disappear — users perceive this as “closing every node” rather than opening a useful overview.
- The switch does not clearly communicate that they entered a different view mode vs. having collapsed their work.
- Returning to selective expansion is unclear (only via **C1 Context** breadcrumb, which also calls `collapseAll` and wipes expansion state).
- The loaded C2 diagram may not match user expectations (all containers on one canvas without system grouping, or an empty/confusing layout).

Relevant code: `handleViewFullLevel` and `fullLevelView` / `fullLevelArchitecture` in `frontend/src/App.tsx`; display switches via `displayArchitecture = fullLevelArchitecture ?? c1Architecture`.

## Expected behavior

Per FP-003 acceptance criteria:

- **View all C2** opt-in shows a **classic full-level C2 diagram** for scanning every container at once (screenshots, printing, overview).
- User understands they left expand-in-place mode (clear label, distinct layout, or modal/full-screen treatment).
- Returning to C1 **restores selective expansion mode** without necessarily destroying saved expansion state (today `collapseAll` runs on “C1 Context”).

## Proposed solution

### View mode clarity

- Rename or supplement label: **“Overview: all C2 containers”** with tooltip explaining the mode switch.
- Visual indicator while in full-level view (banner or breadcrumb trail: `C1 Context / All C2 containers`).
- Do **not** reuse the same canvas transition as collapse — e.g. fade or explicit “Switching to overview” so it does not feel like nodes were closed.

### Preserve expansion state

- Entering full-level view should **snapshot** `expansionState` and restore it when exiting overview (unless user explicitly chooses **Collapse all**).
- **C1 Context** breadcrumb: return to composed C1 view; only **Collapse all** clears expansions.

### Diagram usefulness

- Render the full C2 file with sensible layout: all containers visible, system `parent_id` grouping or labels if multiple systems exist.
- If C2 file is empty or only meaningful inside expanded systems, show empty state with guidance (“Expand a system to add containers, or add from overview”).

### Optional follow-ups

- **View all C3** for a selected container (breadcrumb when drilled into a container).
- Keyboard shortcut to toggle overview vs. composed view.

## Key files

| Area | File |
|------|------|
| View state | `frontend/src/App.tsx` — `fullLevelView`, `handleViewFullLevel`, breadcrumbs |
| Collapse | `frontend/src/canvas/expansion.ts` — `collapseAll` |
| Canvas | `frontend/src/components/Canvas.tsx` — full-level vs. composed rendering |

## Acceptance criteria

- [ ] **View all C2** shows a readable overview of all C2 containers, not a blank or broken canvas
- [ ] Users can tell they are in overview mode vs. expand-in-place mode
- [ ] Exiting overview restores previous expansion state (unless user collapsed explicitly)
- [ ] **View all C2** is distinct from **Collapse all** in behavior and labeling
- [ ] Documented in README / toolbar tooltips

## Out of scope

- Replacing separate per-level `.keel` architecture files with one merged file
- Print/export pipeline (can build on overview view later)
