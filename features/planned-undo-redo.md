# FP-012 — Undo and redo for canvas edits

**Status:** Backlog  
**Priority:** Medium  
**Depends on:** FP-008 (delete node), FP-002 (manual editing)  
**Related:** FP-009 (position persistence)

## Problem

Canvas edits (add node, delete node, move node, edit fields, add/delete edges) are applied immediately and written to `.keel/` on save or drag end. There is no way to reverse a mistake without git revert or manual JSON editing.

FP-008 delete uses immediate deletion with confirmation for non-empty nodes, but still no undo stack.

## Expected behavior

- **Undo** (`Ctrl+Z` / `Cmd+Z`) reverses the last canvas mutation in the current session
- **Redo** (`Ctrl+Shift+Z` / `Cmd+Shift+Z`) reapplies an undone change
- Stack covers: delete node, add node, node field edits, edge add/delete, position changes
- Undo restores in-memory canvas state and persists the reverted architecture to disk (or defers persist until redo stack clears — TBD in design)
- Toolbar buttons or menu items for Undo / Redo with disabled state when stack is empty
- Deleting a node that was just added should be undoable as a single “add” reversal

## Proposed solution

### History stack

- Session-local stack in `App.tsx` or dedicated `useCanvasHistory` hook
- Each entry stores: action type, snapshot of affected `ArchitectureFile`(s), expansion state delta, selection
- Cap stack depth (e.g. 50 entries) to bound memory

### Integration points

| Action | History entry |
|--------|----------------|
| Delete node | Previous architecture file(s) before delete |
| Add node | Remove added node on undo |
| Move node | Previous positions |
| Edit node fields | Previous node payload |
| Add/delete edge | Previous edges array |

### UX

- Show brief toast: “Deleted node X — Undo” (optional v1)
- Confirm dialogs remain for non-empty delete; undo is the recovery path after confirm

## Acceptance criteria

- [ ] User can undo delete node and see it restored on canvas and in `.keel/`
- [ ] User can undo add node
- [ ] User can undo drag position change
- [ ] Keyboard shortcuts work on canvas focus
- [ ] Git dirty indicator reflects undone state correctly

## Out of scope (v1)

- Cross-session undo (survive page reload)
- Undo for sparring-applied bulk changes (separate stack or v2)
- Undo for git commit (use git only)

## Notes

Implement after FP-008 ships so delete has a clear recovery story. Pairs with FP-002 manual editing — one history model for all canvas mutations.
