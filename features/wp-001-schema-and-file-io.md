# WP-001 — Schema & file I/O

**Status:** Done  
**Tests:** `tests/test_schema_and_file_io.py`, `tests/test_markdown_io.py`

## Summary

Foundational data layer for everything stored under `.keel/`. Defines Pydantic models for architecture JSON, requirements, ADRs, characteristics, and work packages, plus atomic read/write helpers.

## What it does

- **Architecture** — `ArchitectureFile`, `KeelNode`, `KeelEdge` in `.keel/architecture/*.json`
- **Requirements** — `REQ-*.md` with YAML frontmatter
- **ADRs** — `ADR-*.md` with YAML frontmatter
- **Characteristics** — `CHAR-*.yml` quality attributes + optional fitness functions
- **Work packages** — `WP-*.md` with YAML frontmatter
- **File I/O** — atomic writes, schema validation before persist

## Key files

| Path | Role |
|------|------|
| `keel/schema.py` | All Pydantic models and enums |
| `keel/file_io.py` | JSON/YAML/Markdown read/write |

## Acceptance criteria (met)

- [x] Invalid models fail validation before touching disk
- [x] Architecture files round-trip through read/write
- [x] Markdown frontmatter documents parse and serialize correctly

## Known gaps

- None blocking later work packages
