# FP-014 — Node detail panel stale error/success state

**Status:** Backlog  
**Priority:** High (UX bug)  
**Depends on:** WP-004, WP-007 (work package generation)  
**Related:** [FP-002](planned-canvas-manual-editing.md) (detail panel edits)

## Problem

The node detail panel (`frontend/src/components/NodeDetailPanel.tsx`) keeps **local React state** for feedback messages:

- `error` — validation failures and API errors
- `message` — success text (e.g. work package created)
- `loading` / `deleting` — in-flight actions

When the user **selects a different node**, the panel content updates (name, id, linked requirements) but **error and success messages from the previous node persist**.

### Repro

1. Select node A (no linked requirements).
2. Click **Generate work package**.
3. Error appears: *“This node has no linked requirements…”*
4. Select node B (different name/id shown in panel header).
5. **Bug:** the same error banner still displays, even though node B may have requirements or was never submitted.

Same issue can affect success messages and potentially loading flags if the user switches nodes mid-action.

### Root cause

`NodeDetailPanel` receives a new `node` prop when selection changes, but `error`, `message`, `loading`, and `deleting` are `useState` hooks that **do not reset** when `node.id` changes. The component instance stays mounted; only props update.

```tsx
const [error, setError] = useState<string | null>(null);
const [message, setMessage] = useState<string | null>(null);
// No useEffect keyed on node.id to clear these
```

## Expected behavior

- Selecting a different node (or closing and reopening the panel) **clears** error, success message, and any stale action state for the previous node.
- Each node’s panel should show only feedback relevant to **that** node’s current session.
- If an async action (generate, delete) was in flight for node A and the user selects node B, cancel or ignore the result for A (do not show A’s error on B’s panel).

## Proposed fix

### Option A — Reset on node change (recommended)

```tsx
useEffect(() => {
  setError(null);
  setMessage(null);
  setLoading(false);
  setDeleting(false);
}, [node?.id]);
```

### Option B — Key the panel by node id

In `App.tsx`, force remount when selection changes:

```tsx
<NodeDetailPanel key={selectedNode?.id ?? "none"} ... />
```

Option A is explicit; Option B is simpler but resets expand/delete UI state too (usually desirable on node switch).

### Async safety

For in-flight `generateWorkPackage` / `onDelete`, track `node.id` at request start and ignore/setState only if it still matches the selected node when the promise resolves.

## Key files

| File | Change |
|------|--------|
| `frontend/src/components/NodeDetailPanel.tsx` | Reset state on `node.id` change; optional abort guard |
| `frontend/src/App.tsx` | Optional `key={selectedNode?.id}` on panel |

## Acceptance criteria

- [ ] Error from “Generate work package” on node A does not appear when node B is selected
- [ ] Success message from node A does not appear when node B is selected
- [ ] Closing the panel and selecting any node starts with a clean panel
- [ ] Vitest: switching `node` prop clears displayed error (component test)

## Out of scope

- Persisting per-node draft messages across sessions
- Toast notifications global to the app (separate enhancement)

## Notes

Small fix (~5–10 lines). Good candidate to ship alongside [FP-008](planned-fix-delete-node.md) since both touch `NodeDetailPanel.tsx`.
