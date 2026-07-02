# WP-005 — AI sparring

**Status:** Enhanced  
**Tests:** `tests/test_spar.py`

## Summary

Right-hand chat panel for architecture discussions. Claude answers in the context of the current C4 view and can suggest `add_node` actions applied with one click.

## What it does

- **POST `/api/spar`** — message + optional conversation history
- Gathers C1/C2 (and C3 when applicable) architecture JSON as context
- Returns `{ reply, actions[] }` where actions can add nodes to the diagram
- **Sessions** — multiple chats stored in browser `localStorage`
- **Markdown rendering** — assistant replies rendered via `react-markdown` + `remark-gfm`

## Key files

| Path | Role |
|------|------|
| `keel/spar.py` | Prompts, retries, semantic validation |
| `frontend/src/components/SparringPanel.tsx` | Chat UI + sessions |
| `frontend/src/spar/sessions.ts` | localStorage session CRUD |
| `frontend/src/components/SparMessageContent.tsx` | Markdown renderer |

## Enhancements after WP-005

- **4 automatic retries** with validation feedback (same pattern as `keel init`)
- Explicit JSON contract in prompts (`reply` + `actions`, invalid examples)
- Semantic rules: node types per C4 level, `node_*` id prefix, C3 parent/container
- Session normalization — auto-select latest chat when active id is missing
- `react-markdown` replaces fragile custom Markdown parser
- Prompt asks for GFM sections (headings, bullets, bold) for readable replies

## Acceptance criteria (met)

- [x] Sparring returns reply text and optional add-node actions
- [x] Claude failures surface as HTTP 502 in chat
- [x] Conversation history included in prompt
- [x] Actions applied via existing `createNode` API
- [x] Retries on invalid JSON / schema / semantic errors
- [x] Previous chats listed in session dropdown

## Known gaps

- Sessions are per-browser only (not synced to server or git)
- No edit/regenerate on individual messages
- Long error messages (after 4 failed retries) can be verbose in the chat bubble
