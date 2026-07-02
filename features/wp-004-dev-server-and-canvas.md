# WP-004 — Dev server & C4 canvas

**Status:** Enhanced  
**Tests:** `tests/test_server.py`, `tests/test_cli.py`  
**CLI:** `keel dev`

## Summary

Local dev experience: FastAPI backend serving `.keel/` data and a React + React Flow canvas for C4 diagrams.

## What it does

- **`keel dev`** — serves API + built frontend on port 3141 (default)
- **Canvas** — render nodes/edges, drag to reposition (persists `position_x` / `position_y`)
- **C4 navigation** — breadcrumbs C1 → C2 → C3 drill-down
- **Toolbar** — add node, git dirty indicator, commit `.keel/` changes
- **API** — CRUD for architecture levels, nodes, git status, commit

## Key files

| Path | Role |
|------|------|
| `keel/server.py` | FastAPI routes |
| `keel/architecture_store.py` | Load/save architecture, add/update/delete node |
| `keel/cli.py` | `keel dev` + frontend bundle preflight |
| `frontend/src/App.tsx` | Main layout |
| `frontend/src/components/Canvas.tsx` | React Flow diagram |
| `scripts/build_frontend.sh` | Build UI into `keel/static/` |

## Enhancements after WP-004

- `keel dev` fails fast with instructions if `keel/static/` is missing
- `build_frontend.sh` checks for `npm` on PATH
- README documents Node.js/npm as prerequisite for source installs

## Acceptance criteria (met)

- [x] Load and display C1 architecture
- [x] Add nodes via toolbar
- [x] Persist node positions on drag
- [x] Commit uncommitted `.keel/` changes from UI
- [x] Drill down C1 system → C2, C2 container → C3

## Known gaps

- **Partial:** API supports `PUT`/`DELETE` node but UI does not expose full edit/delete (see [FP-002](planned-canvas-manual-editing.md))
- No UI to add, edit, or delete edges manually
- Sidebars are fixed width (see [FP-001](planned-resizable-sidebars.md))
- Node detail panel is read-only except work-package generation
