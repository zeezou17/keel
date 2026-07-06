# FP-010 — Docker image and GitHub Actions CI

**Status:** Backlog  
**Priority:** Medium  
**Depends on:** WP-001, WP-004  
**Related:** [WP-008](wp-008-drift-detection.md) (drift Action for **consumer** repos)

## Problem

The Keel **project repository** has no first-party container or continuous integration:

| Gap | Today |
|-----|--------|
| **Docker** | No `Dockerfile` or documented way to run `keel dev` in a container |
| **GitHub Actions (this repo)** | No `.github/workflows/` — PRs are not automatically tested |
| **Frontend in CI** | `pytest` is documented; `frontend` vitest suite (`npm test`) is not run in any pipeline |
| **Release hygiene** | No automated wheel build, frontend bundle check, or publish workflow |

WP-008 ships a drift-check Action that `keel init` installs into **user** repositories. That is separate from CI that validates Keel itself on every push/PR.

Local development assumes a manual sequence: `pip install -e ".[dev]"`, `./scripts/build_frontend.sh`, `pytest` — easy to skip steps or break main unnoticed.

## Expected behavior

### Docker

- Published or documented `Dockerfile` that runs Keel against a mounted git repo.
- Image includes Python 3.11+, built frontend static assets, and the `keel` CLI.
- `docker run` example: mount target repo, expose port `3141`, run `keel dev --no-browser`.
- Optional: multi-stage build (Node build stage → slim Python runtime).

### GitHub Actions (Keel repo)

Workflow(s) on pull request and `main` push:

1. **Python** — `pip install -e ".[dev]"`, `pytest`
2. **Frontend** — `npm ci` + `npm test` + `npm run build` in `frontend/`
3. **Integration smoke** — build frontend into `keel/static/`, import `keel` package, optional FastAPI test client hit

Optional follow-ups:

- Lint / type-check job (ruff, mypy) when adopted
- Build wheel artifact on tag; PyPI publish workflow (manual approval)
- Cache npm and pip for faster CI

### Documentation

- README section: “Run with Docker” and “CI status” badge
- Clarify difference between **Keel project CI** and **drift workflow** installed by `keel init`

## Proposed solution

### Files to add

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage: build UI, install keel, entrypoint `keel dev` |
| `.dockerignore` | Exclude `.venv`, `node_modules`, `.git` |
| `.github/workflows/ci.yml` | PR + push: pytest, vitest, frontend build |
| `.github/workflows/docker.yml` | Optional: build/push image on release tag |
| `docker-compose.yml` | Optional: local one-command dev with volume mount |

### CI matrix (v1)

- `ubuntu-latest` only for first iteration (see [FP-011](planned-cross-platform-support.md) for macOS/Windows runners)

### Acceptance criteria

- [ ] `docker build` succeeds and container serves UI at port 3141 against a mounted repo
- [ ] PR workflow runs `pytest` and frontend `npm test` + build
- [ ] CI fails when Python or frontend tests fail
- [ ] README documents Docker and CI usage
- [ ] Drift Action for consumer repos remains unchanged unless shared test helpers are extracted

## Out of scope (v1)

- Hosting a public Keel SaaS
- Claude Code CLI inside the Docker image (users mount credentials or use API token separately)
- Full E2E browser tests in CI
