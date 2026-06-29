"""Typer CLI entry point for Keel."""

from pathlib import Path
from typing import Optional

import typer

from keel.init_cmd import print_success_summary, run_init

app = typer.Typer(
    name="keel",
    help="Living software architecture — C4 diagrams, specs, ADRs, and agile delivery.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Keel orchestrates the non-code phases of the SDLC inside your git repo."""


@app.command()
def init(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path to initialise (defaults to current directory).",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    description: Optional[str] = typer.Option(
        None,
        "--description",
        "-d",
        help="One-sentence system description (skips prompt; empty means brownfield).",
    ),
    skip_commit: bool = typer.Option(
        False,
        "--skip-commit",
        help="Write files without creating a git commit (for testing).",
        hidden=True,
    ),
) -> None:
    """Initialise a Keel workspace in the current git repository."""
    written = run_init(path=path, description=description, skip_commit=skip_commit)
    root = (path or Path.cwd()).resolve()
    print_success_summary(written, root)


if __name__ == "__main__":
    app()
