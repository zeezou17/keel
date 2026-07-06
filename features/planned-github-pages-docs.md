# FP-016 — GitHub Pages documentation site

**Status:** Backlog  
**Priority:** Medium  
**Depends on:** WP-003, WP-004 (stable enough to document)  
**Related:** [FP-010](planned-docker-and-ci.md) (CI can deploy docs), [README](../README.md) (source material today)

## Problem

Keel’s usage guide lives almost entirely in the root [README](../README.md) and [features/](README.md) folder. That works for developers cloning the repo, but:

- New users landing on GitHub get a long README, not a structured guide
- No searchable, browsable docs site (e.g. `https://zeezou17.github.io/keel/`)
- UI workflows (canvas, sparring, requirements, drift) are not documented with screenshots or step-by-step tutorials
- Feature roadmap and `.keel/` layout are mixed with install instructions in one file

A dedicated **GitHub Pages** site would teach people how to use Keel without reading the source tree.

## Vision

Publish user-facing documentation at a stable URL, built from markdown in this repo and deployed automatically on merge to `main`.

Example URL pattern: `https://<org-or-user>.github.io/keel/`

### Audience

| Reader | Needs |
|--------|--------|
| **First-time user** | Install, `keel init`, open `keel dev`, basic canvas tour |
| **Day-to-day user** | Requirements, ADRs, sparring, commit workflow, delete node |
| **Team lead / DevOps** | Drift detection, GitHub Action setup, `CLAUDE_CODE_TOKEN` |
| **Contributor** | Dev setup, tests, feature tracker pointer |

## Proposed content outline

```
Getting started
  What is Keel?
  Prerequisites (Python, Git, Claude Code, Node for source builds)
  Install (PyPI / from source)
  Quick start: keel init → keel dev

Using the UI
  Architecture canvas (expand/collapse, add/delete nodes, commit)
  Requirements, ADRs, characteristics sidebar
  AI sparring
  Work package generation

Workspace reference
  .keel/ folder layout
  Architecture JSON (C1/C2/C3)
  Path globs and drift

CLI reference
  keel init
  keel dev

CI & drift
  GitHub Action after init
  required: true, secrets

Contributing
  Link to repo README dev section + features/
```

Content can start by splitting and polishing the existing README; avoid duplicating maintenance burden long-term (single source or sync check in CI).

## Tooling options (pick one in Phase 0)

| Option | Pros | Cons |
|--------|------|------|
| **MkDocs Material** + GitHub Actions | Great UX, search, nav; common for Python projects | Extra dev dependency; deploy workflow |
| **Jekyll** (GitHub Pages native `/docs`) | Zero build infra if using default theme | Weaker out-of-box search/nav |
| **VitePress / Docusaurus** | Modern static site | Heavier setup for a Python-first repo |

**Recommendation:** MkDocs Material in a `docs/` folder, deployed via GitHub Actions to `gh-pages` branch (pairs well with [FP-010](planned-docker-and-ci.md) CI work).

## Proposed phases

### Phase 0 — Decision

- [ ] Choose static site generator
- [ ] Pick canonical URL and add to README
- [ ] Define `docs/` directory layout and nav structure

### Phase 1 — MVP site

- [ ] Migrate Getting started + Using the UI from README (keep README as short entry + link)
- [ ] Add `.github/workflows/docs.yml` — build and deploy on push to `main`
- [ ] Enable GitHub Pages from Actions in repo settings
- [ ] Verify site loads at `*.github.io/keel`

### Phase 2 — Polish

- [ ] Screenshots or short GIFs for canvas and sparring
- [ ] Troubleshooting page (Claude auth, frontend build, git not dirty)
- [ ] Version badge or “main docs” label until releases exist

### Phase 3 — Maintain

- [ ] PR checklist: update docs when user-facing behavior changes
- [ ] Optional link checker in CI

## Acceptance criteria

- [ ] Public docs URL live on GitHub Pages
- [ ] Covers install, init, dev server, canvas basics, sidebar docs, sparring, drift Action
- [ ] README links to the docs site as the primary user guide
- [ ] Docs rebuild automatically when `main` updates (no manual deploy)

## Out of scope (v1)

- Hosted SaaS docs (Read the Docs, GitBook)
- Auto-generated API reference from OpenAPI (FastAPI could enable later)
- Translations / i18n
- Docs for unreleased features (viewpoints, theme) beyond “roadmap” pointer

## Notes

Keep the root README as a concise project overview and install pointer — not a duplicate of the full guide. The features folder remains the internal roadmap; the docs site is for **how to use** Keel, not sprint planning.
