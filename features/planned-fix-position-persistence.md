# FP-009 — Fix drag-and-drop position persistence

**Status:** Backlog  
**Priority:** High (UX bug)  
**Depends on:** WP-004, FP-003 (selective drill-down)  
**Related:** [FP-003](planned-selective-drill-down.md), [FP-007](planned-fix-view-all-c2.md)

## Problem

Users can drag nodes on the canvas, but **positions do not reliably stick**. After drag, boxes snap back or reset when:

- The page is refreshed or `keel dev` is restarted
- A branch is collapsed and re-expanded
- Architecture is reloaded (commit, sparring action, requirement highlight refresh)
- Switching to **View all C2** and back (position persist is disabled in full-level view: `onPersistPositions={fullLevelView ? undefined : …}` in `App.tsx`)

WP-004 documents position persistence as shipped, but the composed expand-in-place canvas (FP-003) introduced gaps:

| Scenario | What happens today |
|----------|-------------------|
| Drag C1 node | `buildPositionPersistRequests` → `persistArchitecture` on drag end; usually works |
| Drag C2/C3 child inside expanded group | May save to arch file, but `layoutChildrenInGroup` **recomputes grid positions on every expand** and ignores saved coords (“Saved C2 positions are for the full-level view…”) |
| Drag then collapse / re-expand | Children re-laid out under parent; user placement lost |
| Drag in overview mode | `onPersistPositions` is `undefined`; positions never saved |
| Overlap push on expand | `pushOverlappingNodes` moves siblings; pushed positions may not be persisted before collapse restores originals |

Net effect: dragging feels interactive but **layout is ephemeral** — users cannot curate diagram placement over a session.

## Expected behavior

- Every draggable node (C1, C2, C3) persists `position_x` / `position_y` to the correct `.keel/architecture/*.json` when the user finishes a drag.
- Reloading the page or re-expanding a branch **restores the last saved positions**, not a fresh auto-layout grid.
- Auto-layout runs only for nodes that have **no saved position** (first expand or newly added nodes).
- Positions saved in composed view and in **View all C2** overview use the same source of truth.
- Git dirty indicator updates after position changes (existing behavior).

## Proposed solution

### Persist on drag end (all modes)

- Wire position persist in full-level / overview view, not only composed mode.
- Await or debounce `persistArchitecture` so a quick reload does not race ahead of the write.

### Respect saved positions on expand

- Update `layoutChildrenInGroup` in `frontend/src/canvas/layout.ts` to use `position_x` / `position_y` when present; only auto-layout children missing coordinates.
- Store C2/C3 positions in a coordinate space that survives expand/collapse (document whether absolute canvas coords or parent-relative; today arch files use absolute — ensure reload + merge logic agrees).

### Collapse / re-expand lifecycle

- On collapse: persist any in-flight drag positions before removing children from the React Flow graph.
- On re-expand: `mergeWithLivePositions` / `mergeFromCanvas` should prefer saved arch coords over grid layout.

### Child vs. parent moves

- When a user drags an expanded group’s children, persist to the correct file (C2 global or C3 per-container) — `buildPositionPersistRequests` already routes by level; add tests for composed-child drag round-trip.

### UX

- Optional: subtle “Layout saved” feedback or rely on existing git dirty dot.
- Do not call `fitView` after every persist (only on first load / explicit reset) so the canvas does not jump after drag.

## Key files

| Area | File |
|------|------|
| Drag handler | `frontend/src/components/Canvas.tsx` — `onNodesChange`, `persistPositions` |
| Persist routing | `frontend/src/canvas/persistPositions.ts` — `buildPositionPersistRequests` |
| Expand layout | `frontend/src/canvas/layout.ts` — `layoutChildrenInGroup`, `applyInitialLayout` |
| App wiring | `frontend/src/App.tsx` — `handlePersistPositions`, full-level gating |
| Merge / frames | `frontend/src/canvas/groupFrames.ts` — `mergeWithLivePositions` |
| Backend | `keel/architecture_store.py` — `PUT` architecture (positions on nodes) |
| Tests | `frontend/src/canvas/persistPositions.test.ts`, `layout.test.ts`, `groupFrames.test.ts` |

## Acceptance criteria

- [ ] Drag a C1 node → refresh page → node appears at the same coordinates
- [ ] Drag C2 containers inside an expanded system → collapse → re-expand → containers stay where the user placed them
- [ ] Drag C3 components inside an expanded container → reload → positions restored
- [ ] Drag in **View all C2** overview → positions persist to C2 architecture file
- [ ] New nodes without positions still get sensible auto-layout on first placement
- [ ] Integration or unit tests cover drag → persist → reload / re-expand round-trip

## Out of scope

- Full auto-layout algorithms (dagre, elk) for “tidy up” button
- Persisting viewport pan/zoom (React Flow `fitView` state)
- Undo/redo for layout changes
