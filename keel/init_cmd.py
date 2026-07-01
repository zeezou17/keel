"""`keel init` implementation."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import typer
from jinja2 import Template
from pydantic import BaseModel, ValidationError
from rich.console import Console

from keel.claude_bridge import (
    KeelClaudeError,
    KeelClaudeNotFoundError,
    KeelClaudeOutputError,
    format_validation_errors,
    verify_claude_cli,
    run_claude,
)
from keel.file_io import write_keel_file
from keel.git_utils import KeelGitError, commit_paths, open_repo, repo_root
from keel.schema import ArchitectureFile, NodeLevel

TEMPLATES_DIR = Path(__file__).parent / "templates"
KEEL_COMMIT_MESSAGE = "chore: initialise keel architecture workspace"
KEEL_SECTION_START = "<!-- keel:architecture-context -->"
KEEL_SECTION_END = "<!-- /keel:architecture-context -->"
ARCHITECTURE_MAX_ATTEMPTS = 4  # initial attempt plus up to 3 automatic retries

console = Console()


class InitArchitectureBundle(BaseModel):
    c1: ArchitectureFile
    c2: ArchitectureFile


class ArchitectureGenerationError(KeelClaudeOutputError):
    """Raised when architecture generation fails after all retry attempts."""

    def __init__(
        self,
        message: str,
        *,
        attempts: int,
        analysis: str,
        validation_errors: list[dict[str, object]] | None = None,
        raw_payload: Any = None,
        raw_result_text: str | None = None,
        attempt_history: list[dict[str, object]] | None = None,
    ) -> None:
        super().__init__(
            message,
            validation_errors=validation_errors,
            raw_payload=raw_payload,
            raw_result_text=raw_result_text,
        )
        self.attempts = attempts
        self.analysis = analysis
        self.attempt_history = attempt_history or []


@dataclass
class ArchitectureAttemptFailure:
    attempt: int
    message: str
    validation_errors: list[dict[str, object]] = field(default_factory=list)
    semantic_errors: list[str] = field(default_factory=list)
    raw_payload: Any = None
    raw_result_text: str | None = None


def run_init(
    path: Path | None = None,
    description: str | None = None,
    skip_commit: bool = False,
) -> list[Path]:
    """
    Initialise a Keel workspace in a git repository.

    Returns the list of files written or updated.
    """
    cwd = (path or Path.cwd()).resolve()

    try:
        repo = open_repo(cwd)
    except KeelGitError as exc:
        raise typer.Exit(str(exc)) from exc

    root = repo_root(repo)

    try:
        verify_claude_cli(cwd=root)
    except KeelClaudeNotFoundError as exc:
        raise typer.Exit(
            f"{exc}\n\nInstall Claude Code: https://code.claude.com/docs/en/setup"
        ) from exc
    except KeelClaudeError as exc:
        raise typer.Exit(
            f"{exc}\n\nAuthenticate by running `claude` and signing in, "
            "or use `claude setup-token` for CI."
        ) from exc

    if description is None:
        description = typer.prompt(
            "Describe your system in one sentence, or press Enter to analyze the existing codebase",
            default="",
            show_default=False,
        ).strip()

    try:
        bundle = _generate_architecture(root, description)
    except ArchitectureGenerationError as exc:
        raise typer.Exit(_format_architecture_generation_failure(exc)) from exc
    except KeelClaudeOutputError as exc:
        raise typer.Exit(
            "Claude Code returned malformed or invalid architecture JSON. "
            f"No files were written.\n\nDetails: {exc}"
        ) from exc
    except KeelClaudeError as exc:
        raise typer.Exit(f"Claude Code call failed: {exc}") from exc

    written: list[Path] = []
    try:
        written.extend(_write_architecture(root, bundle))
        written.extend(_write_agent_files(root))
        written.append(_write_workflow(root))
        written.append(_write_github_action(root))
    except (ValidationError, OSError) as exc:
        raise typer.Exit(f"Failed to write Keel files: {exc}") from exc

    if not skip_commit:
        try:
            commit_paths(repo, written, KEEL_COMMIT_MESSAGE)
        except KeelGitError as exc:
            raise typer.Exit(str(exc)) from exc

    return written


def _generate_architecture(root: Path, description: str) -> InitArchitectureBundle:
    mode = "brownfield" if not description else "greenfield"
    base_prompt = _build_architecture_prompt(description=description, mode=mode)
    failures: list[ArchitectureAttemptFailure] = []

    for attempt in range(1, ARCHITECTURE_MAX_ATTEMPTS + 1):
        prompt = (
            base_prompt
            if attempt == 1
            else _build_architecture_correction_prompt(base_prompt, failures[-1], attempt)
        )
        status = (
            "[bold green]Generating C1/C2 architecture with Claude Code..."
            if attempt == 1
            else f"[bold yellow]Retrying architecture generation ({attempt}/{ARCHITECTURE_MAX_ATTEMPTS})..."
        )
        with console.status(status, spinner="dots"):
            try:
                result = run_claude(prompt, output_schema=InitArchitectureBundle, cwd=root)
            except KeelClaudeOutputError as exc:
                if not _is_retriable_output_error(exc):
                    raise
                failures.append(
                    ArchitectureAttemptFailure(
                        attempt=attempt,
                        message=str(exc),
                        validation_errors=list(exc.validation_errors),
                        raw_payload=exc.raw_payload,
                        raw_result_text=exc.raw_result_text,
                    )
                )
                continue

        if not isinstance(result, InitArchitectureBundle):
            failures.append(
                ArchitectureAttemptFailure(
                    attempt=attempt,
                    message="Expected validated InitArchitectureBundle from Claude Code.",
                )
            )
            continue

        semantic_errors = _semantic_validate_bundle(result)
        if semantic_errors:
            failures.append(
                ArchitectureAttemptFailure(
                    attempt=attempt,
                    message="Architecture JSON parsed but violated Keel semantic rules.",
                    semantic_errors=semantic_errors,
                    raw_payload=result.model_dump(mode="json"),
                )
            )
            continue

        return result

    last = failures[-1] if failures else ArchitectureAttemptFailure(
        attempt=ARCHITECTURE_MAX_ATTEMPTS,
        message="Architecture generation failed for an unknown reason.",
    )
    analysis = _analyze_architecture_failures(failures)
    raise ArchitectureGenerationError(
        "Claude Code could not produce valid Keel architecture JSON "
        f"after {ARCHITECTURE_MAX_ATTEMPTS} attempts.",
        attempts=ARCHITECTURE_MAX_ATTEMPTS,
        analysis=analysis,
        validation_errors=last.validation_errors,
        raw_payload=last.raw_payload,
        raw_result_text=last.raw_result_text,
        attempt_history=[_failure_to_dict(item) for item in failures],
    )


def _is_retriable_output_error(exc: KeelClaudeOutputError) -> bool:
    message = str(exc).lower()
    non_retriable_markers = (
        "not authenticated",
        "not logged in",
        "rate limit",
        "not found on path",
    )
    return not any(marker in message for marker in non_retriable_markers)


def _semantic_validate_bundle(bundle: InitArchitectureBundle) -> list[str]:
    errors: list[str] = []
    if bundle.c1.level != NodeLevel.c1:
        errors.append("c1.level must be 1 (C1 context diagram).")
    if bundle.c2.level != NodeLevel.c2:
        errors.append("c2.level must be 2 (C2 container diagram).")
    if bundle.c2.container_id is not None:
        errors.append("c2.container_id must be null (no C3 breakdown during init).")

    for index, node in enumerate(bundle.c2.nodes):
        if node.type.value not in {"container", "external"}:
            errors.append(
                f"c2.nodes[{index}] ({node.id}) has type '{node.type.value}' "
                "but C2 must use container or external nodes only."
            )
        if node.level != NodeLevel.c2:
            errors.append(f"c2.nodes[{index}] ({node.id}) must have level 2.")

    for index, node in enumerate(bundle.c1.nodes):
        if node.level != NodeLevel.c1:
            errors.append(f"c1.nodes[{index}] ({node.id}) must have level 1.")

    return errors


def _failure_to_dict(failure: ArchitectureAttemptFailure) -> dict[str, object]:
    return {
        "attempt": failure.attempt,
        "message": failure.message,
        "validation_errors": failure.validation_errors,
        "semantic_errors": failure.semantic_errors,
        "raw_payload": failure.raw_payload,
        "raw_result_text": failure.raw_result_text,
    }


def _analyze_architecture_failures(failures: list[ArchitectureAttemptFailure]) -> str:
    lines = [
        "Keel attempted to generate architecture JSON multiple times. Common issues:",
        "- Edges must use source_id and target_id (not source/target).",
        "- Every edge needs id, type, source_id, and target_id.",
        "- Node type must be one of: person, system, container, component, external.",
        "- C1 nodes use level 1; C2 container/external nodes use level 2.",
        "- C2 should not include person nodes.",
        "- Non-external nodes should include paths globs bound to real repository files.",
        "",
        "Attempt summary:",
    ]
    for failure in failures:
        lines.append(f"- Attempt {failure.attempt}: {failure.message}")
        if failure.validation_errors:
            lines.append(format_validation_errors(failure.validation_errors))
        if failure.semantic_errors:
            lines.extend(f"  - {item}" for item in failure.semantic_errors)
    return "\n".join(lines)


def _format_architecture_generation_failure(exc: ArchitectureGenerationError) -> str:
    sections = [
        "Claude Code could not produce valid Keel architecture JSON. No files were written.",
        "",
        f"Attempts: {exc.attempts}",
        "",
        "Analysis:",
        exc.analysis,
    ]

    if exc.validation_errors:
        sections.extend(["", "Validation errors (last attempt):", format_validation_errors(exc.validation_errors)])

    if exc.raw_payload is not None:
        sections.extend(
            [
                "",
                "Returned JSON (last attempt):",
                json.dumps(exc.raw_payload, indent=2),
            ]
        )
    elif exc.raw_result_text:
        sections.extend(["", "Raw Claude result (last attempt):", exc.raw_result_text])

    if exc.attempt_history:
        sections.extend(["", "All attempts:", json.dumps(exc.attempt_history, indent=2)])

    return "\n".join(sections)


def _architecture_schema_example() -> str:
    return """{
  "c1": {
    "schema_version": 1,
    "level": 1,
    "container_id": null,
    "nodes": [
      {
        "id": "node_main-system",
        "type": "system",
        "level": 1,
        "name": "Main System",
        "description": "Primary software system.",
        "paths": ["src/**"]
      },
      {
        "id": "node_end-user",
        "type": "person",
        "level": 1,
        "name": "End User",
        "description": "Uses the system.",
        "paths": []
      },
      {
        "id": "node_external-api",
        "type": "external",
        "level": 1,
        "name": "External API",
        "description": "Third-party dependency.",
        "paths": []
      }
    ],
    "edges": [
      {
        "id": "edge_user_uses_system",
        "type": "uses",
        "source_id": "node_end-user",
        "target_id": "node_main-system",
        "label": "Uses the application"
      }
    ]
  },
  "c2": {
    "schema_version": 1,
    "level": 2,
    "container_id": null,
    "nodes": [
      {
        "id": "node_api",
        "type": "container",
        "level": 2,
        "name": "API",
        "description": "HTTP API layer.",
        "paths": ["src/api/**"]
      }
    ],
    "edges": [
      {
        "id": "edge_api_to_external",
        "type": "calls",
        "source_id": "node_api",
        "target_id": "node_external-api",
        "label": "Calls external service"
      }
    ]
  }
}"""


def _build_architecture_prompt(description: str, mode: str) -> str:
    if mode == "greenfield":
        context = (
            f"The user described the system as: {description}\n"
            "Infer a reasonable C1 context and C2 container skeleton from this description."
        )
        path_rule = (
            "For non-external nodes, use plausible `paths` globs even when the codebase "
            "is not available (e.g. `app/**`, `src/**`)."
        )
    else:
        context = (
            "Analyze the existing codebase in the current working directory. "
            "Explore the repository structure agentically and infer architecture from real files."
        )
        path_rule = (
            "For non-external nodes, `paths` must be real directory globs from the repository "
            "(e.g. `app/src/main/java/**`, `src/api/**`)."
        )

    return f"""You are generating initial Keel architecture files for a software project.

{context}

Return a single JSON object with exactly two keys: "c1" and "c2".

INVALID edge shape (do not use):
{{"id": "e1", "source": "node_a", "target": "node_b", "description": "..."}}

REQUIRED edge shape:
{{
  "id": "edge_a_to_b",
  "type": "uses",
  "source_id": "node_a",
  "target_id": "node_b",
  "label": "optional human-readable label"
}}

REQUIRED node shape:
{{
  "id": "node_example",
  "type": "system",
  "level": 1,
  "name": "Readable name",
  "description": "What this element does.",
  "paths": ["optional/globs/**"]
}}

Allowed node types: person, system, container, component, external

Rules:
- c1: level 1; nodes are person, system, and external as appropriate
- c2: level 2; nodes are container and external only (no person nodes at C2)
- c2.container_id must be null
- Every node needs id, type, level, name, description
- Node level must match the diagram (1 in c1, 2 in c2)
- Node ids should be stable strings prefixed with "node_"
- {path_rule}
- Every edge needs id, type, source_id, target_id (never source/target)
- Set schema_version to 1 on both c1 and c2
- Include meaningful edges between nodes at each level
- Return JSON only, no markdown fences, no commentary

Example output shape:
{_architecture_schema_example()}
"""


def _build_architecture_correction_prompt(
    base_prompt: str,
    failure: ArchitectureAttemptFailure,
    attempt: int,
) -> str:
    details: list[str] = [
        f"Attempt {failure.attempt} failed: {failure.message}",
    ]
    if failure.validation_errors:
        details.append("Schema validation errors:")
        details.append(format_validation_errors(failure.validation_errors))
    if failure.semantic_errors:
        details.append("Semantic rule violations:")
        details.extend(f"- {item}" for item in failure.semantic_errors)

    if failure.raw_payload is not None:
        details.extend(
            [
                "Your previous JSON:",
                json.dumps(failure.raw_payload, indent=2),
            ]
        )
    elif failure.raw_result_text:
        details.extend(["Your previous raw output:", failure.raw_result_text])

    correction = "\n".join(details)
    return f"""{base_prompt}

Your previous response was invalid. This is retry {attempt - 1} of {ARCHITECTURE_MAX_ATTEMPTS - 1}.

{correction}

Fix every validation and semantic issue above.
Return corrected JSON only — no markdown fences, no commentary.
"""


def _write_architecture(root: Path, bundle: InitArchitectureBundle) -> list[Path]:
    arch_dir = root / ".keel" / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)

    c1_path = arch_dir / "c1-context.json"
    c2_path = arch_dir / "c2-containers.json"

    write_keel_file(c1_path, bundle.c1)
    write_keel_file(c2_path, bundle.c2)
    return [c1_path, c2_path]


def _write_agent_files(root: Path) -> list[Path]:
    written: list[Path] = []

    claude_path = root / "CLAUDE.md"
    claude_template = _load_template("CLAUDE.md.jinja")
    written.append(
        _merge_marked_file(claude_path, claude_template.render())
    )

    cursorrules_path = root / ".cursorrules"
    cursor_template = _load_template("cursorrules.jinja")
    written.append(
        _merge_marked_file(cursorrules_path, cursor_template.render())
    )

    return written


def _write_workflow(root: Path) -> Path:
    workflow_src = TEMPLATES_DIR / "keel-drift.yml"
    workflow_dest = root / ".github" / "workflows" / "keel-drift.yml"
    workflow_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(workflow_src, workflow_dest)
    return workflow_dest


def _write_github_action(root: Path) -> Path:
    action_src = TEMPLATES_DIR / "github-action" / "action.yml"
    action_dest = root / ".github" / "actions" / "keel-drift" / "action.yml"
    action_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(action_src, action_dest)
    return action_dest


def _load_template(name: str) -> Template:
    return Template((TEMPLATES_DIR / name).read_text(encoding="utf-8"))


def _merge_marked_file(path: Path, new_section: str) -> Path:
    new_section = new_section.strip()
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        merged = merge_keel_section(existing, new_section)
    else:
        merged = new_section + "\n"

    path.write_text(merged, encoding="utf-8")
    return path


def merge_keel_section(existing: str, new_section: str) -> str:
    """Insert or replace the marked Keel section without duplicating content."""
    pattern = re.compile(
        rf"{re.escape(KEEL_SECTION_START)}.*?{re.escape(KEEL_SECTION_END)}",
        flags=re.DOTALL,
    )
    if pattern.search(existing):
        merged = pattern.sub(new_section, existing)
    elif KEEL_SECTION_START in existing or KEEL_SECTION_END in existing:
        raise ValueError("Found partial Keel markers in existing file; fix markers manually.")
    else:
        merged = existing.rstrip() + "\n\n" + new_section + "\n"

    return merged


def print_success_summary(written: list[Path], root: Path) -> None:
    console.print("\n[bold green]Keel workspace initialised.[/bold green]\n")
    console.print("Files written:")
    for path in written:
        try:
            display = path.resolve().relative_to(root)
        except ValueError:
            display = path
        console.print(f"  - {display}")
    console.print(
        "\nNext step: run [bold]keel dev[/bold] to open the architecture canvas."
    )
