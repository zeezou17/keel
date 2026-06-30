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
from keel.assess import AssessImpactRequest, AssessImpactResponse, assess_impact
from keel.claude_bridge import KeelClaudeError
from keel.document_store import (
    DocumentNotFoundError,
    create_adr,
    create_characteristic,
    create_requirement,
    delete_adr,
    delete_characteristic,
    delete_requirement,
    get_adr,
    get_characteristic,
    get_requirement,
    list_adrs,
    list_characteristics,
    list_requirements,
    save_adr,
    save_characteristic,
    save_requirement,
)
from keel.git_utils import KeelGitError, commit_keel_changes, keel_status, open_repo
from keel.schema import ADR, ADRStatus, ArchitectureFile, Characteristic, FitnessFunction, KeelNode, NodeLevel, NodeType, Priority, Requirement, ReqStatus
from keel.spar import SparRequest, SparResponse, run_spar

STATIC_DIR = Path(__file__).parent / "static"
KEEL_REPO_ROOT_ENV = "KEEL_REPO_ROOT"


class NodeCreateRequest(BaseModel):
    level: int = Field(ge=1, le=3)
    container_id: str | None = None
    node: KeelNode


class CommitRequest(BaseModel):
    message: str = "chore: update keel architecture"


class RequirementCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)


class RequirementUpdateRequest(BaseModel):
    title: str = Field(min_length=1)
    status: ReqStatus
    linked_node_ids: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    body: str = ""


class ADRCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    body: str | None = None


class ADRUpdateRequest(BaseModel):
    title: str = Field(min_length=1)
    status: ADRStatus
    linked_node_ids: list[str] = Field(default_factory=list)
    linked_characteristic_ids: list[str] = Field(default_factory=list)
    body: str = ""


class CharacteristicCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    priority: Priority
    scenario: str = Field(min_length=1)
    fitness_function: FitnessFunction | None = None
    linked_node_ids: list[str] = Field(default_factory=list)


class RequirementResponse(BaseModel):
    id: str
    title: str
    status: ReqStatus
    linked_node_ids: list[str]
    acceptance_criteria: list[str]
    body: str


class ADRResponse(BaseModel):
    id: str
    title: str
    status: ADRStatus
    linked_node_ids: list[str]
    linked_characteristic_ids: list[str]
    body: str


def _requirement_response(requirement: Requirement, body: str) -> RequirementResponse:
    return RequirementResponse(
        id=requirement.id,
        title=requirement.title,
        status=requirement.status,
        linked_node_ids=requirement.linked_node_ids,
        acceptance_criteria=requirement.acceptance_criteria,
        body=body,
    )


def _adr_response(adr: ADR, body: str) -> ADRResponse:
    return ADRResponse(
        id=adr.id,
        title=adr.title,
        status=adr.status,
        linked_node_ids=adr.linked_node_ids,
        linked_characteristic_ids=adr.linked_characteristic_ids,
        body=body,
    )


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

    @app.get("/api/nodes")
    def list_nodes() -> list[KeelNode]:
        root = get_repo_root()
        nodes: list[KeelNode] = []
        for level in (1, 2):
            path = architecture_path(root, level)
            if path.exists():
                arch = load_architecture(root, level)
                nodes.extend(arch.nodes)
        return nodes

    @app.get("/api/requirements")
    def get_requirements() -> list[RequirementResponse]:
        root = get_repo_root()
        return [_requirement_response(req, body) for req, body in list_requirements(root)]

    @app.get("/api/requirements/{req_id}")
    def get_requirement_by_id(req_id: str) -> RequirementResponse:
        root = get_repo_root()
        try:
            req, body = get_requirement(root, req_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _requirement_response(req, body)

    @app.post("/api/requirements")
    def post_requirement(request: RequirementCreateRequest) -> RequirementResponse:
        root = get_repo_root()
        req, body = create_requirement(
            root,
            title=request.title,
            description=request.description,
            acceptance_criteria=request.acceptance_criteria,
        )
        return _requirement_response(req, body)

    @app.put("/api/requirements/{req_id}")
    def put_requirement(req_id: str, request: RequirementUpdateRequest) -> RequirementResponse:
        root = get_repo_root()
        try:
            existing, _ = get_requirement(root, req_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        updated = Requirement(
            id=existing.id,
            title=request.title,
            status=request.status,
            linked_node_ids=request.linked_node_ids,
            acceptance_criteria=request.acceptance_criteria,
        )
        try:
            save_requirement(root, updated, request.body)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _requirement_response(updated, request.body)

    @app.delete("/api/requirements/{req_id}")
    def remove_requirement(req_id: str) -> dict[str, str]:
        root = get_repo_root()
        try:
            delete_requirement(root, req_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"deleted": req_id}

    @app.get("/api/adrs")
    def get_adrs() -> list[ADRResponse]:
        root = get_repo_root()
        return [_adr_response(adr, body) for adr, body in list_adrs(root)]

    @app.get("/api/adrs/{adr_id}")
    def get_adr_by_id(adr_id: str) -> ADRResponse:
        root = get_repo_root()
        try:
            adr, body = get_adr(root, adr_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _adr_response(adr, body)

    @app.post("/api/adrs")
    def post_adr(request: ADRCreateRequest) -> ADRResponse:
        root = get_repo_root()
        adr, body = create_adr(root, title=request.title, body=request.body)
        return _adr_response(adr, body)

    @app.put("/api/adrs/{adr_id}")
    def put_adr(adr_id: str, request: ADRUpdateRequest) -> ADRResponse:
        root = get_repo_root()
        try:
            existing, _ = get_adr(root, adr_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        updated = ADR(
            id=existing.id,
            title=request.title,
            status=request.status,
            linked_node_ids=request.linked_node_ids,
            linked_characteristic_ids=request.linked_characteristic_ids,
        )
        try:
            save_adr(root, updated, request.body)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _adr_response(updated, request.body)

    @app.delete("/api/adrs/{adr_id}")
    def remove_adr(adr_id: str) -> dict[str, str]:
        root = get_repo_root()
        try:
            delete_adr(root, adr_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"deleted": adr_id}

    @app.get("/api/characteristics")
    def get_characteristics() -> list[Characteristic]:
        root = get_repo_root()
        return list_characteristics(root)

    @app.get("/api/characteristics/{char_id}")
    def get_characteristic_by_id(char_id: str) -> Characteristic:
        root = get_repo_root()
        try:
            return get_characteristic(root, char_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/characteristics")
    def post_characteristic(request: CharacteristicCreateRequest) -> Characteristic:
        root = get_repo_root()
        characteristic = Characteristic(
            id="",
            name=request.name,
            priority=request.priority,
            scenario=request.scenario,
            fitness_function=request.fitness_function,
            linked_node_ids=request.linked_node_ids,
        )
        return create_characteristic(root, characteristic)

    @app.put("/api/characteristics/{char_id}")
    def put_characteristic(char_id: str, characteristic: Characteristic) -> Characteristic:
        root = get_repo_root()
        if characteristic.id != char_id:
            raise HTTPException(status_code=400, detail="Characteristic id in body must match path.")
        try:
            return save_characteristic(root, characteristic)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/characteristics/{char_id}")
    def remove_characteristic(char_id: str) -> dict[str, str]:
        root = get_repo_root()
        try:
            delete_characteristic(root, char_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"deleted": char_id}

    @app.post("/api/assess-impact")
    def post_assess_impact(request: AssessImpactRequest) -> AssessImpactResponse:
        root = get_repo_root()
        try:
            return assess_impact(root, request.requirement_id)
        except DocumentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
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
