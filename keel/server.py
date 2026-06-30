"""FastAPI server for Keel dev UI and architecture API."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from keel.architecture_store import (
    ArchitectureNotFoundError,
    NodeNotFoundError,
    add_node,
    architecture_path,
    delete_node,
    find_node_location,
    load_architecture,
    save_architecture,
    update_node,
)
from keel.claude_bridge import KeelClaudeError
from keel.git_utils import KeelGitError, commit_keel_changes, keel_status, open_repo
from keel.schema import ArchitectureFile, KeelNode, NodeLevel, NodeType
from keel.spar import SparRequest, SparResponse, run_spar

STATIC_DIR = Path(__file__).parent / "static"
KEEL_REPO_ROOT_ENV = "KEEL_REPO_ROOT"


class NodeCreateRequest(BaseModel):
    level: int = Field(ge=1, le=3)
    container_id: str | None = None
    node: KeelNode


class CommitRequest(BaseModel):
    message: str = "chore: update keel architecture"


def get_repo_root() -> Path:
    configured = os.environ.get(KEEL_REPO_ROOT_ENV)
    if configured:
        return Path(configured).resolve()
    return Path.cwd().resolve()


def create_app() -> FastAPI:
    app = FastAPI(title="Keel", version="0.1.0")

    @app.get("/api/architecture/{level}")
    def get_architecture(
        level: int,
        container_id: str | None = Query(default=None),
    ) -> ArchitectureFile:
        root = get_repo_root()
        try:
            return load_architecture(root, level, container_id)
        except ArchitectureNotFoundError as exc:
            if level == 3:
                return ArchitectureFile(
                    level=NodeLevel.c3,
                    container_id=container_id,
                    nodes=[],
                    edges=[],
                )
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/api/architecture/{level}")
    def put_architecture(
        level: int,
        body: ArchitectureFile,
        container_id: str | None = Query(default=None),
    ) -> ArchitectureFile:
        root = get_repo_root()
        if body.level.value != level:
            raise HTTPException(status_code=400, detail="Body level does not match path level.")

        path = architecture_path(root, level, container_id or body.container_id)
        save_architecture(path, body)
        return body

    @app.post("/api/architecture/node")
    def create_node(request: NodeCreateRequest) -> ArchitectureFile:
        root = get_repo_root()
        try:
            return add_node(root, request.level, request.node, request.container_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/architecture/node/{node_id}")
    def put_node(node_id: str, node: KeelNode) -> ArchitectureFile:
        root = get_repo_root()
        if node.id != node_id:
            raise HTTPException(status_code=400, detail="Node id in body must match path.")
        try:
            return update_node(root, node_id, node)
        except NodeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/architecture/node/{node_id}")
    def remove_node(node_id: str) -> ArchitectureFile:
        root = get_repo_root()
        try:
            return delete_node(root, node_id)
        except NodeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/git/status")
    def git_status() -> dict[str, object]:
        root = get_repo_root()
        try:
            repo = open_repo(root)
        except KeelGitError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return keel_status(repo)

    @app.post("/api/commit")
    def commit_changes(request: CommitRequest) -> dict[str, str]:
        root = get_repo_root()
        try:
            repo = open_repo(root)
            commit_sha = commit_keel_changes(repo, request.message)
        except KeelGitError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"commit": commit_sha}

    @app.post("/api/spar")
    def spar(request: SparRequest) -> SparResponse:
        root = get_repo_root()
        try:
            return run_spar(root, request)
        except KeelClaudeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/")
    def index() -> FileResponse:
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(
                status_code=503,
                detail="Frontend bundle missing. Run scripts/build_frontend.sh.",
            )
        return FileResponse(index_path)

    if STATIC_DIR.exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    return app


app = create_app()
