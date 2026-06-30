"""`keel init` implementation."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import typer
from jinja2 import Template
from pydantic import BaseModel, ValidationError
from rich.console import Console

from keel.claude_bridge import (
    KeelClaudeError,
    KeelClaudeNotFoundError,
    KeelClaudeOutputError,
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

console = Console()


class InitArchitectureBundle(BaseModel):
    c1: ArchitectureFile
    c2: ArchitectureFile


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
    prompt = _build_architecture_prompt(description=description, mode=mode)

    with console.status(
        "[bold green]Generating C1/C2 architecture with Claude Code...",
        spinner="dots",
    ):
        result = run_claude(prompt, output_schema=InitArchitectureBundle, cwd=root)

    if not isinstance(result, InitArchitectureBundle):
        raise KeelClaudeOutputError("Expected validated InitArchitectureBundle from Claude Code.")

    if result.c1.level != NodeLevel.c1:
        raise KeelClaudeOutputError("Generated C1 architecture has incorrect level.")
    if result.c2.level != NodeLevel.c2:
        raise KeelClaudeOutputError("Generated C2 architecture has incorrect level.")
    if result.c2.container_id is not None:
        raise KeelClaudeOutputError("C2 skeleton must not include C3 container breakdown.")

    return result


def _build_architecture_prompt(description: str, mode: str) -> str:
    if mode == "greenfield":
        context = (
            f"The user described the system as: {description}\n"
            "Infer a reasonable C1 context and C2 container skeleton from this description."
        )
    else:
        context = (
            "Analyze the existing codebase in the current working directory. "
            "Explore the repository structure agentically and infer architecture from real files."
        )

    return f"""You are generating initial Keel architecture files for a software project.

{context}

Return a single JSON object with exactly two keys:
- "c1": an ArchitectureFile for C1 (level 1) with person, system, and external nodes as appropriate
- "c2": an ArchitectureFile for C2 (level 2) with container nodes only — no C3 component breakdown

Requirements:
- Every non-external node must have stable string ids (e.g. "node_api-gateway") and `paths` globs binding nodes to real files
- C1 nodes use level 1; C2 nodes use level 2
- Include meaningful edges between nodes at each level
- Set schema_version to 1 on both files
- C2 must have container_id set to null
- Return JSON only, no markdown fences or commentary

ArchitectureFile shape:
{{
  "schema_version": 1,
  "level": 1,
  "container_id": null,
  "nodes": [...],
  "edges": [...]
}}
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
