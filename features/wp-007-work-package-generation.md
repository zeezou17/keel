# WP-007 — Work package generation

**Status:** Done  
**Tests:** `tests/test_work_packages.py`

## Summary

AI-generated implementation specs (`WP-*.md`) for a selected architecture node, grounded in linked requirements and relevant ADRs.

## What it does

- **POST `/api/generate-work-package`** — `node_id` + optional `requirement_ids`
- Claude drafts title, acceptance criteria, dependencies, and markdown body
- Writes `.keel/specs/WP-NNN.md` with YAML frontmatter
- Triggered from **node detail panel** on the canvas (requires linked requirements)

## Key files

| Path | Role |
|------|------|
| `keel/work_packages.py` | Generation prompt, storage, ID sequencing |
| `frontend/src/components/NodeDetailPanel.tsx` | "Generate work package" button |
| `frontend/src/api/client.ts` | `generateWorkPackage()` |

## Acceptance criteria (met)

- [x] Generates `WP-001`, `WP-002`, … sequentially
- [x] Requires at least one linked requirement on the node
- [x] Pulls in relevant ADRs for context
- [x] Acceptance criteria are concrete and testable (prompt-enforced)

## Known gaps

- No UI to list/edit work packages in sidebar (files exist on disk only)
- No automatic git commit after generation
