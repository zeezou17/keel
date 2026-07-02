# WP-008 — Drift detection

**Status:** Done  
**Tests:** `tests/test_drift.py`, drift action tests in same file

## Summary

Keeps architecture `paths` globs aligned with the codebase. Runs on pull requests via GitHub Actions; optionally uses Claude to classify unmapped files.

## What it does

1. Diff PR changed files against all node path globs
2. Detect renames and auto-update high-confidence path mappings
3. Classify unmapped files with Claude (when configured)
4. Evaluate characteristic fitness functions for affected nodes
5. Post PR comment + advisory check status
6. Optional auto-commit of architecture path updates

## Key files

| Path | Role |
|------|------|
| `keel/drift.py` | Glob matching, drift detection, classification prompt |
| `keel/action/drift_check.py` | GitHub Action entry point |
| `keel/templates/keel-drift.yml` | Workflow installed by `keel init` |
| `keel/templates/github-action/action.yml` | Composite action |

## Setup (in target repos)

- `keel init` installs workflow under `.github/workflows/keel-drift.yml`
- Set `CLAUDE_CODE_TOKEN` secret for AI classification in CI
- Optional: `required: true` on composite action to fail PR on unmapped files

## Acceptance criteria (met)

- [x] Changed files matched against node `paths` globs
- [x] Git rename detection updates node paths
- [x] PR comment with drift summary
- [x] Characteristic fitness checks on relevant changes

## Known gaps

- Advisory by default (does not block merges unless configured)
- Classification quality depends on Claude + glob accuracy at init time
