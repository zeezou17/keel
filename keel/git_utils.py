"""GitPython helpers for Keel."""

from __future__ import annotations

from pathlib import Path

import git
from git import Repo


class KeelGitError(Exception):
    """Raised when a git operation required by Keel fails."""


def open_repo(path: Path) -> Repo:
    """Open the git repository containing `path`."""
    try:
        return git.Repo(path, search_parent_directories=True)
    except git.InvalidGitRepositoryError as exc:
        raise KeelGitError(
            "This directory is not inside a git repository. Run `git init` first."
        ) from exc


def repo_root(repo: Repo) -> Path:
    """Return the repository root as a Path."""
    return Path(repo.working_tree_dir or repo.git_dir).resolve()


def commit_paths(repo: Repo, paths: list[Path], message: str) -> str:
    """Stage the given paths and create a single commit."""
    if not paths:
        raise KeelGitError("No files to commit.")

    relative_paths = sorted(
        {
            str(path.resolve().relative_to(repo_root(repo)))
            for path in paths
        }
    )
    repo.index.add(relative_paths)
    commit = repo.index.commit(message)
    return commit.hexsha


def keel_status(repo: Repo) -> dict[str, object]:
    """Return git status for the `.keel/` directory."""
    root = repo_root(repo)
    keel_rel = ".keel"
    porcelain = repo.git.status("--porcelain", keel_rel).splitlines()
    changed = [line[3:] for line in porcelain if len(line) > 3]
    return {
        "dirty": bool(porcelain),
        "changed_files": changed,
    }


def commit_keel_changes(repo: Repo, message: str = "chore: update keel architecture") -> str:
    """Stage all `.keel/` changes and create a commit."""
    status = keel_status(repo)
    if not status["dirty"]:
        raise KeelGitError("No uncommitted changes under .keel/.")

    repo.index.add([".keel"])
    commit = repo.index.commit(message)
    return commit.hexsha

