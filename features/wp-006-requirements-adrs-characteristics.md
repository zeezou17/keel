# WP-006 — Requirements, ADRs & characteristics

**Status:** Done  
**Tests:** `tests/test_documents.py`

## Summary

Left sidebar document panels linking non-code artifacts to architecture nodes, plus AI impact assessment for requirements.

## What it does

### Requirements (`REQ-*.md`)

- Create, edit, link to architecture nodes
- Status: draft / approved / implemented
- **Assess impact** — Claude suggests which nodes are affected

### ADRs (`ADR-*.md`)

- Architecture decision records with status and links to nodes/characteristics

### Characteristics (`CHAR-*.yml`)

- Quality attributes (performance, security, etc.)
- Optional fitness functions (test file, lint rule, manual) used in drift checks

## Key files

| Path | Role |
|------|------|
| `keel/document_store.py` | CRUD for requirements, ADRs, characteristics |
| `keel/assess.py` | Requirement impact assessment via Claude |
| `frontend/src/components/Sidebar.tsx` | Tab container |
| `frontend/src/components/RequirementsPanel.tsx` | Requirements UI |
| `frontend/src/components/ADRsPanel.tsx` | ADRs UI |
| `frontend/src/components/CharacteristicsPanel.tsx` | Characteristics UI |

## Acceptance criteria (met)

- [x] CRUD for all three document types via API
- [x] Link requirements to nodes; highlight linked nodes on canvas
- [x] Impact assessment returns node ids + reasons
- [x] Selecting a requirement highlights affected nodes

## Known gaps

- Sidebar width is fixed at 320px (see [FP-001](planned-resizable-sidebars.md))
- No bulk import/export of documents
