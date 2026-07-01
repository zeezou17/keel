"""GitPython helpers for Keel.

This module provides git operations for Keel, including repository
access, commit creation, and tracking of changes to the ``.keel/``
directory.

Example:
    Basic repository operations::

        from pathlib import Path
        from keel.git_utils import open_repo, repo_root, keel_status

        repo = open_repo(Path("."))
        root = repo_root(repo)
        status = keel_status(repo)

        if status["dirty"]:
            print(f"Changed files: {status['changed_files']}")
"""

from __future__ import annotations

from pathlib import Path

import git
from git import Repo


class KeelGitError(Exception):
    """Raised when a git operation required by Keel fails.

    This exception is raised for git-related errors such as:
        - Directory is not inside a git repository
        - No files to commit
        - No uncommitted changes when trying to commit
    """


def open_repo(path: Path) -> Repo:
    """Open the git repository containing the given path.

    Searches parent directories to find the repository root, so this
    works when called from any subdirectory within a repository.

    Args:
        path: Path within the repository (can be any subdirectory).

    Returns:
        GitPython Repo object for the repository.

    Raises:
        KeelGitError: If the path is not inside a git repository.

    Example:
        >>> repo = open_repo(Path("/path/to/repo/subdir"))
        >>> print(repo.working_tree_dir)
        "/path/to/repo"
    """
    try:
        return git.Repo(path, search_parent_directories=True)
    except git.InvalidGitRepositoryError as exc:
        raise KeelGitError(
            "This directory is not inside a git repository. Run `git init` first."
        ) from exc


def repo_root(repo: Repo) -> Path:
    """Get the repository root directory as a Path.

    Args:
        repo: GitPython Repo object.

    Returns:
        Resolved Path to the repository root directory.

    Example:
        >>> repo = open_repo(Path("."))
        >>> root = repo_root(repo)
        >>> print(root)
        PosixPath("/path/to/repo")
    """
    return Path(repo.working_tree_dir or repo.git_dir).resolve()


# -- Commits and .keel/ dirty tracking (used by dev UI toolbar) --------------


def commit_paths(repo: Repo, paths: list[Path], message: str) -> str:
    """Stage specific paths and create a single git commit.

    All paths are converted to repository-relative paths before staging.

    Args:
        repo: GitPython Repo object.
        paths: List of file paths to stage and commit.
        message: Commit message.

    Returns:
        The hexadecimal SHA of the created commit.

    Raises:
        KeelGitError: If paths list is empty.

    Example:
        >>> repo = open_repo(Path("."))
        >>> sha = commit_paths(repo, [Path(".keel/architecture/c1.json")], "Add C1 diagram")
        >>> print(sha[:7])
        "a1b2c3d"
    """
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
    """Get git status for the ``.keel/`` directory.

    Checks for uncommitted changes (staged, unstaged, or untracked)
    in the ``.keel/`` directory only.

    Args:
        repo: GitPython Repo object.

    Returns:
        Dictionary with:
            - ``dirty``: Boolean indicating if there are uncommitted changes
            - ``changed_files``: List of changed file paths (relative to repo)

    Example:
        >>> repo = open_repo(Path("."))
        >>> status = keel_status(repo)
        >>> if status["dirty"]:
        ...     print(f"Changed: {status['changed_files']}")
    """
    root = repo_root(repo)
    keel_rel = ".keel"
    porcelain = repo.git.status("--porcelain", keel_rel).splitlines()
    changed = [line[3:] for line in porcelain if len(line) > 3]
    return {
        "dirty": bool(porcelain),
        "changed_files": changed,
    }


def commit_keel_changes(repo: Repo, message: str = "chore: update keel architecture") -> str:
    """Stage all ``.keel/`` changes and create a commit.

    Convenience function that stages all changes in the ``.keel/``
    directory and creates a commit. Used by the dev UI toolbar's
    commit button.

    Args:
        repo: GitPython Repo object.
        message: Commit message. Defaults to "chore: update keel architecture".

    Returns:
        The hexadecimal SHA of the created commit.

    Raises:
        KeelGitError: If there are no uncommitted changes under ``.keel/``.

    Example:
        >>> repo = open_repo(Path("."))
        >>> sha = commit_keel_changes(repo, "Add new API container")
        >>> print(f"Created commit {sha[:7]}")
    """
    status = keel_status(repo)
    if not status["dirty"]:
        raise KeelGitError("No uncommitted changes under .keel/.")

    repo.index.add([".keel"])
    commit = repo.index.commit(message)
    return commit.hexsha

