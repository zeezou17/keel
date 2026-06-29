"""Typer CLI entry point for Keel."""

import typer

app = typer.Typer(
    name="keel",
    help="Living software architecture — C4 diagrams, specs, ADRs, and agile delivery.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Keel orchestrates the non-code phases of the SDLC inside your git repo."""


if __name__ == "__main__":
    app()
