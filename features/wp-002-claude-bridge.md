# WP-002 — Claude Code bridge

**Status:** Enhanced  
**Tests:** `tests/test_claude_bridge.py`

## Summary

Subprocess integration with the Claude Code CLI (`claude -p ... --output-format json`). All AI features in Keel go through this module — not direct HTTP to Anthropic.

## What it does

- **`verify_claude_cli()`** — pre-flight check that `claude` is on PATH and authenticated
- **`run_claude()`** — run a prompt, parse JSON envelope, optional Pydantic `output_schema`
- **Error mapping** — auth, rate limit, malformed JSON, schema validation failures
- **JSON extraction** — handles markdown fences and JSON embedded in prose (`_extract_json_object`)

## Key files

| Path | Role |
|------|------|
| `keel/claude_bridge.py` | CLI wrapper and parsing |

## Enhancements after WP-002

- `KeelClaudeOutputError` carries `validation_errors`, `raw_payload`, `raw_result_text`
- `format_validation_errors()` for human and retry prompts
- Detached subprocess (`CI=true`, no TTY) to avoid interactive CLI interference

## Acceptance criteria (met)

- [x] Missing `claude` binary → clear error
- [x] Auth / rate-limit messages mapped to typed exceptions
- [x] Schema-validated responses return Pydantic models
- [x] Markdown-fenced and embedded JSON payloads parse when possible

## Known gaps

- No streaming responses (batch `-p` only)
- Requires headless Claude auth (`claude -p` must work, not just interactive `claude`)
