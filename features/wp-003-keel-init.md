# WP-003 — Keel init

**Status:** Enhanced  
**Tests:** `tests/test_init.py`  
**CLI:** `keel init`

## Summary

Bootstraps a Keel workspace inside an existing git repository: C1/C2 architecture skeleton, agent context files, and GitHub drift-check workflow.

## What it does

1. Verifies git repo + Claude CLI auth
2. **Greenfield** — user describes the system in one sentence; Claude infers architecture
3. **Brownfield** — user presses Enter; Claude explores the repo and infers from real files
4. Writes `.keel/architecture/c1-context.json` and `c2-containers.json`
5. Merges marked section into `CLAUDE.md` and `.cursorrules`
6. Copies `keel-drift.yml` workflow and composite action
7. Creates git commit (unless `--skip-commit`)

## Key files

| Path | Role |
|------|------|
| `keel/init_cmd.py` | Init logic, prompts, retries |
| `keel/cli.py` | `keel init` command |
| `keel/templates/` | Jinja templates for agent files and GitHub Action |

## Enhancements after WP-003

- Explicit Keel node/edge JSON contract in prompts (`source_id` / `target_id`, not `source` / `target`)
- **4 attempts** with automatic correction prompts on validation failure
- Detailed failure output: analysis, validation errors, returned JSON, attempt history
- Brownfield vs greenfield path-glob rules in prompt

## Acceptance criteria (met)

- [x] `keel init` writes architecture + agent files + workflow
- [x] Re-running init does not duplicate marked sections in `CLAUDE.md`
- [x] Malformed Claude JSON does not write partial files
- [x] Retries with feedback before giving up

## Known gaps

- C3 component diagrams are not generated at init (created on drill-down in UI)
- Init still depends on Claude returning valid JSON (retries help but do not guarantee success)
