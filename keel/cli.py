"""Typer CLI entry point for Keel."""

import os
import shutil
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

import typer
import uvicorn

from keel.init_cmd import print_success_summary, run_init
from keel.server import KEEL_REPO_ROOT_ENV, STATIC_DIR

app = typer.Typer(
    name="keel",
    help="Living software architecture — C4 diagrams, specs, ADRs, and agile delivery.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Keel orchestrates the non-code phases of the SDLC inside your git repo."""


# -- keel init: scaffold .keel/ in a git repo --------------------------------


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


# -- keel dev: local web UI + API for editing architecture -------------------


@app.command()
def dev(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository path containing .keel/ (defaults to current directory).",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    port: int = typer.Option(3141, help="Port for the local dev server."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Do not open a browser tab."),
) -> None:
    """Start the Keel dev server and open the architecture canvas."""
    root = (path or Path.cwd()).resolve()
    if not (root / ".keel").exists():
        raise typer.Exit("No .keel/ workspace found. Run `keel init` first.")

    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        npm_hint = ""
        if shutil.which("npm") is None:
            npm_hint = (
                "\n\nnpm was not found on PATH. Install Node.js 18+ and npm, then rebuild:\n"
                "  conda install -c conda-forge nodejs   # or use nvm / your OS package manager"
            )
        raise typer.Exit(
            "Frontend bundle missing. Build it before running `keel dev`:\n"
            "  ./scripts/build_frontend.sh\n"
            "Run that command from the Keel source repository (where frontend/ lives)."
            f"{npm_hint}"
        )

    os.environ[KEEL_REPO_ROOT_ENV] = str(root)
    url = f"http://127.0.0.1:{port}"

    if not no_browser:
        def _open_browser() -> None:
            time.sleep(0.8)
            webbrowser.open(url)

        threading.Thread(target=_open_browser, daemon=True).start()

    typer.echo(f"Keel dev server running at {url}")
    uvicorn.run("keel.server:app", host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    app()

