# FP-011 — Cross-platform support (beyond Ubuntu)

**Status:** Backlog  
**Priority:** Medium  
**Depends on:** WP-001, WP-004  
**Related:** [FP-010](planned-docker-and-ci.md) (CI matrix on multiple OS runners)

## Problem

Keel is developed and documented primarily on **Ubuntu/Linux**. Running on macOS, Windows, or other Linux distributions is untested and likely fragile:

| Area | Linux/Ubuntu bias today |
|------|-------------------------|
| **Build scripts** | `./scripts/build_frontend.sh` is bash-only; no PowerShell or cross-shell alternative |
| **Docs** | README uses `source .venv/bin/activate`; Windows path only mentioned in passing |
| **CI** | No automated runs on `macos-latest` or `windows-latest` (no CI at all yet — see FP-010) |
| **Paths** | `.keel/` file I/O uses `pathlib` (good) but edge cases (drive letters, symlinks, case sensitivity) are unverified |
| **Git integration** | GitPython + `keel dev` commit flow may behave differently on Windows (line endings, `core.autocrlf`, file locks) |
| **Browser open** | `keel dev` opens default browser — platform-specific behavior not documented |
| **Claude Code CLI** | External dependency; install/auth paths differ by OS; not validated in Keel’s test suite |

Users on MacBooks or Windows WSL/native should be able to install, build the frontend, run `keel dev`, and use `keel init` without undocumented workarounds.

## Expected behavior

- **macOS** (Intel and Apple Silicon) and **Windows** (native + WSL2) listed as supported or “best effort” with tested instructions.
- Platform-neutral install docs: `python -m venv`, `pip install`, frontend build command that works without bash.
- Path and git operations work on case-insensitive filesystems (macOS, Windows).
- CI matrix (once FP-010 lands) exercises at least one non-Ubuntu runner for Python tests; frontend build on all target OSes.

## Proposed solution

### Scripts

- Add `scripts/build_frontend.ps1` for Windows PowerShell.
- Or replace shell-specific scripts with `python -m keel.build_frontend` (invoke npm via `shutil.which` / `subprocess`) for one entry point on all platforms.
- Ensure `keel` console script works when installed via `pip` on Windows (`keel.exe`).

### Path and git hardening

- Audit `keel/architecture_store.py`, `keel/document_store.py`, and server static file paths for Windows-safe joins.
- Add tests using `pathlib` temp dirs on case-insensitive path simulation where feasible.
- Document git line-ending recommendations for `.keel/` JSON and Markdown.

### Claude CLI

- Document OS-specific Claude Code install links and known limitations (e.g. WSL vs native Windows).
- `keel init` should surface clear errors when `claude` is missing on PATH, regardless of OS.

### CI matrix (with FP-010)

| Runner | Jobs |
|--------|------|
| `ubuntu-latest` | Full: pytest, vitest, build, smoke |
| `macos-latest` | pytest, frontend build |
| `windows-latest` | pytest, frontend build (PowerShell) |

Start with Python-only on macOS/Windows if frontend npm on Windows runners is slow; expand over time.

### Documentation

- README “Supported platforms” table
- Troubleshooting: WSL2, antivirus locking `.keel/`, npm not on PATH

## Key files

| Area | File |
|------|------|
| Build | `scripts/build_frontend.sh`, new cross-platform wrapper |
| CLI | `keel/cli.py`, `keel/dev_server.py` (browser launch, paths) |
| File I/O | `keel/architecture_store.py`, `keel/file_io.py` (if present) |
| Docs | `README.md` |
| CI | `.github/workflows/ci.yml` (FP-010) |

## Acceptance criteria

- [ ] Fresh install + frontend build + `keel dev` documented and verified on macOS and Windows (or WSL2)
- [ ] Cross-platform build entry point (not bash-only)
- [ ] `pytest` passes on Ubuntu, macOS, and Windows in CI
- [ ] No hardcoded `/` paths that break on Windows
- [ ] README lists supported platforms and links to troubleshooting

## Out of scope (v1)

- Mobile or tablet UI
- ARM-specific optimizations beyond “works on Apple Silicon”
- Packaging as Homebrew formula or Windows MSI (can follow after pip/Docker work)
