# FP-015 — Fixed viewport layout (chat growth pushes UI off-screen)

**Status:** Backlog  
**Priority:** High (UX bug)  
**Depends on:** WP-004, WP-005 (sparring panel)  
**Related:** [FP-001](planned-resizable-sidebars.md) (layout), [FP-005](planned-ui-theme-refresh.md) (theme pass)

## Problem

As the AI sparring chat grows (more messages, longer replies), the **entire page height increases** instead of the chat scrolling inside a fixed panel. Side effects:

- The main workspace grows taller than the viewport
- The user must **scroll the whole page** to reach controls at the bottom
- The **node detail panel** (delete, expand, work package) sits at `bottom: 1rem` inside `.canvas-panel` — it gets pushed **below the visible area**
- Popovers, session menus, and chat input can end up **under** other content or off-screen
- Will get worse as chat history grows, more panels open, and more diagram types are added

### Expected layout

The app should behave like a desktop IDE: **toolbar + three columns fill exactly one viewport height**. Only **internal regions** scroll (chat messages, sidebar lists, canvas pan/zoom) — not the outer page.

```
┌──────────────────────────────────────────── toolbar (fixed height)
│ sidebar │      canvas (+ node panel)      │  spar chat  │
│ scroll  │      (fixed height)               │  messages   │
│         │                                   │  scroll     │
│         │                                   │  [input]    │
└──────────────────────────────────────────── viewport bottom
```

### Actual behavior (bug)

Chat content expands `.spar-panel` / `.app-shell` height → page scrollbar appears → canvas overlays and detail panel shift down → user scrolls document to find delete panel or chat input.

## Likely root cause

`.app-shell` uses `min-height: 100vh` but does not **cap** height or hide overflow on the root flex column. If any child in the flex chain lacks a bounded height (`height: 100%`, `flex: 1`, `min-height: 0`, `overflow: hidden`), children with `overflow-y: auto` (e.g. `.spar-messages`) never receive a max height and instead grow the parent.

Suspect areas:

| Selector | Issue |
|----------|--------|
| `.app-shell` | `min-height: 100vh` only — may need `height: 100vh` / `100dvh` + `overflow: hidden` |
| `body`, `#root` | May not propagate full viewport height to React root |
| `.workspace` | Has `min-height: 0` but parent may not constrain |
| `.spar-panel` | Column flex; `.spar-messages` has `overflow-y: auto` but parent height unbounded |
| `.node-detail-panel` | Absolute within `.canvas-panel`; useless if canvas column grows off-screen |

## Proposed fix

### Phase 1 — Viewport shell (v1)

- Set `html, body, #root, .app-shell` to full viewport height with `overflow: hidden` on the shell
- Ensure `.workspace { flex: 1; min-height: 0; overflow: hidden; }`
- Verify `.spar-messages` and `.sidebar-list` / `.sidebar-detail` scroll internally
- Verify `.canvas-panel` stays viewport-sized; React Flow fills `height: 100%`

### Phase 2 — Overlay safety (v1)

- Node detail panel: consider `max-height` + internal scroll, or anchor so it stays visible when canvas column is correct height
- Spar session dropdown: ensure `position: absolute` menus are not clipped incorrectly after shell fix

### Phase 3 — Follow-ups

- [FP-001](planned-resizable-sidebars.md) should respect the same viewport bounds
- Mobile / narrow viewports: stack or collapse panels instead of horizontal overflow

## Key files

| File | Role |
|------|------|
| `frontend/src/styles.css` | `.app-shell`, `.workspace`, `.spar-panel`, `.spar-messages`, `.canvas-panel` |
| `frontend/src/App.tsx` | Root layout structure |
| `frontend/index.html` | `#root` sizing |

## Acceptance criteria

- [ ] Long sparring conversation (20+ messages) does **not** increase document/body scroll height
- [ ] Chat messages scroll inside the spar panel only; input stays visible at bottom of panel
- [ ] Node detail panel remains reachable without scrolling the whole page (when a node is selected)
- [ ] Sidebar requirement lists still scroll independently
- [ ] Canvas still fills center column; pan/zoom unchanged
- [ ] No double scrollbars on typical 1080p viewport

## Out of scope (v1)

- Redesigning panel positions (bottom drawer vs side)
- Resizable panel heights ([FP-001](planned-resizable-sidebars.md))

## Notes

Reported after FP-008 delete panel shipped — delete/detail popover at bottom of canvas is especially affected. Fix before adding more panels (viewpoints, edge editor, undo toast) or the problem compounds.
