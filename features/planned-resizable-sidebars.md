# FP-001 — Resizable sidebars

**Status:** Planned  
**Priority:** Next  
**Depends on:** WP-004, WP-005, WP-006

## Problem

The left **docs sidebar** (requirements / ADRs / characteristics) and right **AI sparring panel** use fixed CSS widths:

- `.sidebar` — `320px`
- `.spar-panel` — `400px`

On smaller screens or long documents, content feels cramped; on large monitors, users cannot give more space to chat vs. docs vs. canvas.

## Proposed solution

### Interaction

- Drag handle on the inner edge of each sidebar (left panel: right edge; spar panel: left edge)
- Double-click handle resets to default width
- Minimum width ~240px, maximum ~50% of viewport
- Persist widths in `localStorage` (e.g. `keel:layout-widths`)

### Layout

```
┌──────────┬─╂────────────────────╂─┬──────────┐
│ Sidebar  │ ║      Canvas        ║ │ Sparring │
│ (resize) │ ║                    ║ │ (resize) │
└──────────┴─╂────────────────────╂─┴──────────┘
```

### Implementation notes

| Area | Work |
|------|------|
| `frontend/src/App.tsx` | Flex/grid layout with resizable columns |
| `frontend/src/styles.css` | Remove fixed `width` on `.sidebar` / `.spar-panel` |
| New `ResizeHandle.tsx` | Pointer drag logic, clamp min/max |
| `frontend/src/layout/storage.ts` | Save/restore widths |

### Acceptance criteria

- [ ] User can drag to resize left sidebar; canvas reflows
- [ ] User can drag to resize spar panel; canvas reflows
- [ ] Widths persist across page reloads
- [ ] Collapsed sidebar/spar modes still work
- [ ] No horizontal scroll on typical 1280px+ viewports

### Out of scope (v1)

- Resizing canvas height separately
- Docking spar panel to bottom
