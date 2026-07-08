# Keel feature tracker

Living index of Keel capabilities — what is shipped, what was enhanced after the original work packages, and what is planned next.

## Status legend

| Status | Meaning |
|--------|---------|
| **Done** | Implemented, tested, and usable in `keel dev` |
| **Enhanced** | Original work package done; follow-up improvements landed |
| **Partial** | Backend or UI exists but human workflow is incomplete |
| **Planned** | Not started; spec drafted in this folder |
| **Backlog** | Idea captured; research or design needed before implementation |

## Shipped features (work packages)

| ID | Feature | Status | Detail |
|----|---------|--------|--------|
| WP-001 | [Schema & file I/O](wp-001-schema-and-file-io.md) | Done | Pydantic models, atomic `.keel/` read/write |
| WP-002 | [Claude Code bridge](wp-002-claude-bridge.md) | Enhanced | Non-interactive `claude -p` wrapper, JSON parsing |
| WP-003 | [Keel init](wp-003-keel-init.md) | Enhanced | `keel init` — AI C1/C2 bootstrap with retries |
| WP-004 | [Dev server & canvas](wp-004-dev-server-and-canvas.md) | Enhanced | FastAPI + React C4 canvas, git commit from UI |
| WP-005 | [AI sparring](wp-005-ai-sparring.md) | Enhanced | Architecture chat, sessions, Markdown replies |
| WP-006 | [Requirements, ADRs, characteristics](wp-006-requirements-adrs-characteristics.md) | Done | Left sidebar document panels + impact assessment |
| WP-007 | [Work package generation](wp-007-work-package-generation.md) | Done | AI-generated `WP-*.md` specs from nodes |
| WP-008 | [Drift detection](wp-008-drift-detection.md) | Done | Path-glob drift + GitHub Action on PRs |

## Planned features

| ID | Feature | Status | Detail |
|----|---------|--------|--------|
| FP-001 | [Resizable sidebars](planned-resizable-sidebars.md) | Done | Drag-to-resize left docs panel and right sparring panel |
| FP-002 | [Canvas manual editing](planned-canvas-manual-editing.md) | Done | Edit node fields, draw/edit/delete edges from the UI |
| FP-003 | [Selective drill-down](planned-selective-drill-down.md) | Done | Expand one branch in place; keep sibling nodes visible; multi-expand + collapse |
| FP-004 | [UML and multi-viewpoint diagrams](planned-uml-and-multi-viewpoint-diagrams.md) | Backlog | UML (class, sequence, …) and other notations beyond C4; research phase first |
| FP-005 | [UI theme and color palette refresh](planned-ui-theme-refresh.md) | Backlog | Visual refresh of colors, typography, and component styling after core UX features ship |
| FP-006 | [Fix add-node targeting and parent linking](planned-fix-add-node-targeting.md) | Done | Add node creates nodes at correct level/parent; toolbar shows focus |
| FP-007 | [Fix “View all C2” escape hatch](planned-fix-view-all-c2.md) | Done | Overview mode preserves expansions; clear banner and breadcrumbs |
| FP-008 | [Delete node from the UI](planned-fix-delete-node.md) | Done | Delete from node detail panel; empty nodes delete immediately, others confirm |
| FP-009 | [Fix drag-and-drop position persistence](planned-fix-position-persistence.md) | Done | Dragged positions survive reload, re-expand, and overview mode |
| FP-010 | [Docker image and GitHub Actions CI](planned-docker-and-ci.md) | Backlog | No Dockerfile or project CI; pytest/vitest not run on PRs |
| FP-011 | [Cross-platform support (beyond Ubuntu)](planned-cross-platform-support.md) | Backlog | macOS/Windows untested; bash-only build scripts; path/git edge cases |
| FP-012 | [Undo and redo](planned-undo-redo.md) | Backlog | Reverse canvas edits (delete, add, move, edit) in the current session |
| FP-013 | [Manual node linking (edges with text)](planned-manual-node-linking.md) | Backlog | Draw links between nodes; label relationships manually on the canvas |
| FP-014 | [Node detail panel stale error/success state](planned-fix-node-detail-stale-state.md) | Done | Work package error clears when selecting a different node |
| FP-015 | [Fixed viewport layout (chat growth)](planned-fix-viewport-layout-overflow.md) | Done | Long chat scrolls inside spar panel; detail panel stays reachable |
| FP-016 | [GitHub Pages documentation site](planned-github-pages-docs.md) | Backlog | User guide on GitHub Pages — install, UI tour, drift, how to use Keel |

## How to use this folder

- **Product / planning** — read this README for the roadmap at a glance.
- **Implementation** — open the linked markdown for acceptance criteria, key files, and known gaps.
- **New features** — add `planned-<slug>.md`, link it here, and move to a WP/FP row when work starts.

## Quick start (for context)

```bash
pip install -e ".[dev]"
./scripts/build_frontend.sh    # source installs only
cd /path/to/your-git-repo
keel init                      # brownfield: press Enter at prompt
keel dev
```

See the [project README](../README.md) for full installation and usage.
