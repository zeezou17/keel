"""Atomic read/write helpers for ``.keel/`` files.

This module provides safe file I/O operations for Keel's data files,
supporting JSON, YAML, and Markdown with YAML frontmatter formats.
All write operations are atomic (temp file + rename) to prevent data
corruption on crashes or interrupts.

Supported file types:
    - ``.json``: Architecture files (``c1-context.json``, ``c2-containers.json``)
    - ``.yml/.yaml``: Characteristics files (``CHAR-*.yml``)
    - ``.md``: Requirements, ADRs, and work packages with YAML frontmatter

Example:
    Writing and reading an architecture file::

        from keel.file_io import write_keel_file, read_keel_file
        from keel.schema import ArchitectureFile

        write_keel_file(Path(".keel/architecture/c1-context.json"), arch)
        loaded = read_keel_file(Path(".keel/architecture/c1-context.json"), ArchitectureFile)
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Type, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)(.*)$", re.DOTALL)


# -- JSON and YAML files (architecture, characteristics) ---------------------


def write_keel_file(path: Path, model: BaseModel) -> None:
    """Validate and atomically write a Pydantic model to a JSON or YAML file.

    Uses a temporary file and atomic rename (``os.replace``) to ensure the
    target file is never left in a partial or corrupted state.

    Args:
        path: Destination file path. Must have ``.json``, ``.yml``, or ``.yaml``
            extension. Parent directories are created if they don't exist.
        model: Pydantic model instance to serialize and write.

    Raises:
        ValidationError: If the model fails validation before writing.
        ValueError: If the file extension is not supported.
        OSError: If file I/O fails (permissions, disk full, etc.).

    Example:
        >>> from keel.schema import ArchitectureFile, NodeLevel
        >>> arch = ArchitectureFile(level=NodeLevel.c1, nodes=[], edges=[])
        >>> write_keel_file(Path(".keel/architecture/c1-context.json"), arch)
    """
    try:
        data = model.model_dump(mode="json")
        type(model).model_validate(data)
    except ValidationError:
        raise

    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix
    tmp_path: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            suffix=suffix,
            delete=False,
            encoding="utf-8",
        ) as tmp:
            if suffix == ".json":
                json.dump(data, tmp, indent=2, ensure_ascii=False)
            elif suffix in (".yml", ".yaml"):
                yaml.safe_dump(data, tmp, allow_unicode=True)
            else:
                raise ValueError(f"Unsupported .keel/ file extension: {suffix}")
            tmp_path = tmp.name

        os.replace(tmp_path, path)
        tmp_path = None
    except Exception:
        if tmp_path is not None and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def read_keel_file(path: Path, model_class: Type[T]) -> T:
    """Read a JSON or YAML file and parse it into a Pydantic model.

    Args:
        path: Path to the file to read. Must have ``.json``, ``.yml``, or
            ``.yaml`` extension.
        model_class: The Pydantic model class to parse the data into.

    Returns:
        An instance of ``model_class`` populated with the file's data.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValidationError: If the file content does not match the model schema.
        ValueError: If the file extension is not supported.
        json.JSONDecodeError: If a JSON file contains invalid JSON.
        yaml.YAMLError: If a YAML file contains invalid YAML.

    Example:
        >>> from keel.schema import ArchitectureFile
        >>> arch = read_keel_file(Path(".keel/architecture/c1-context.json"), ArchitectureFile)
        >>> print(arch.level)
        NodeLevel.c1
    """
    suffix = path.suffix
    raw = path.read_text(encoding="utf-8")

    if suffix == ".json":
        data = json.loads(raw)
    elif suffix in (".yml", ".yaml"):
        data = yaml.safe_load(raw)
    else:
        raise ValueError(f"Unsupported .keel/ file extension: {suffix}")

    return model_class.model_validate(data)


# -- Markdown with YAML frontmatter (requirements, ADRs, work packages) ---------


def write_keel_markdown(path: Path, model: BaseModel, body: str = "") -> None:
    """Validate and atomically write a Markdown file with YAML frontmatter.

    Creates a Markdown file with YAML frontmatter (delimited by ``---``) from
    the model, followed by the markdown body content.

    Args:
        path: Destination file path. Parent directories are created if needed.
        model: Pydantic model instance for the YAML frontmatter.
        body: Markdown body content to write after the frontmatter.

    Raises:
        ValidationError: If the model fails validation before writing.
        OSError: If file I/O fails.

    Example:
        >>> from keel.schema import Requirement, ReqStatus
        >>> req = Requirement(id="REQ-001", title="User login", status=ReqStatus.draft)
        >>> write_keel_markdown(Path(".keel/requirements/REQ-001.md"), req, "## Details\\n...")
    """
    try:
        data = model.model_dump(mode="json")
        type(model).model_validate(data)
    except ValidationError:
        raise

    frontmatter = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()
    content = f"---\n{frontmatter}\n---\n\n{body.rstrip()}\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            suffix=path.suffix,
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        os.replace(tmp_path, path)
        tmp_path = None
    except Exception:
        if tmp_path is not None and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def read_keel_markdown(path: Path, model_class: Type[T]) -> tuple[T, str]:
    """Read a Markdown file with YAML frontmatter into a model and body.

    Parses the YAML frontmatter (delimited by ``---``) into the specified
    Pydantic model class and returns both the model and the remaining
    markdown body.

    Args:
        path: Path to the Markdown file to read.
        model_class: The Pydantic model class for the frontmatter.

    Returns:
        A tuple of (model_instance, body_string) where:
            - model_instance: Parsed frontmatter as a Pydantic model
            - body_string: Markdown content after the frontmatter (stripped)

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file does not contain valid YAML frontmatter.
        ValidationError: If the frontmatter does not match the model schema.

    Example:
        >>> from keel.schema import Requirement
        >>> req, body = read_keel_markdown(Path(".keel/requirements/REQ-001.md"), Requirement)
        >>> print(req.title)
        "User login"
        >>> print(body)
        "## Details\\n..."
    """
    raw = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_PATTERN.match(raw)
    if not match:
        raise ValueError(f"File does not contain YAML frontmatter: {path}")

    data = yaml.safe_load(match.group(1))
    body = match.group(2).strip()
    return model_class.model_validate(data), body
