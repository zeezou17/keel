# Keel feature tracker

Living index of Keel capabilities — what is shipped, what was enhanced after the original work packages, and what is planned next.

## Status legend

| Status | Meaning |
|--------|---------|
| **Done** | Implemented, tested, and usable in `keel dev` |
| **Enhanced** | Original work package done; follow-up improvements landed |
| **Partial** | Backend or UI exists but human workflow is incomplete |
| **Planned** | Not started; spec drafted in this folder |

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
| FP-001 | [Resizable sidebars](planned-resizable-sidebars.md) | Planned | Drag-to-resize left docs panel and right sparring panel |
| FP-002 | [Canvas manual editing](planned-canvas-manual-editing.md) | Planned | Edit/delete nodes and add edges manually on the diagram |

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
