"""Atomic read/write helpers for .keel/ files."""

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


def write_keel_file(path: Path, model: BaseModel) -> None:
    """
    Validate `model`, then write atomically (temp file + os.replace).

    Raises ValidationError before touching disk if model is invalid.
    Raises on any I/O error — never leaves a partial file at the target path.
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
    """
    Read a .keel/ file and parse it into `model_class`.

    Raises ValidationError if the file does not match the schema.
    Raises FileNotFoundError if the file does not exist.
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


def write_keel_markdown(path: Path, model: BaseModel, body: str = "") -> None:
    """Validate `model` and write YAML frontmatter + markdown body atomically."""
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
    """Read markdown with YAML frontmatter into `model_class` and return the body."""
    raw = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_PATTERN.match(raw)
    if not match:
        raise ValueError(f"File does not contain YAML frontmatter: {path}")

    data = yaml.safe_load(match.group(1))
    body = match.group(2).strip()
    return model_class.model_validate(data), body
