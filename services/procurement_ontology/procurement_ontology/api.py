"""Same-origin management and read API; enterprise scope is server-owned."""

import threading
import uuid
from contextlib import asynccontextmanager, nullcontext
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field

from .extraction import ExtractionService
from .agent import BuyerAgent
from .governance import GovernanceService
from .identity import Credentials, Identity, authorize
from .intake import IntakeService
from .mcp_server import create_mcp, current_identity
from .model_client import configured_client
from .maintenance import MaintenanceError
from .models import DomainModel, SourceSpan
from .query import KnowledgeQuery, version_pair
from .schema_draft import SchemaDraftService
from .store import VersionConflict

COOKIE = "procurement_session"


class Login(DomainModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=12, max_length=1024, repr=False)


class NewCompany(Login):
    company_id: str


class SourceInput(DomainModel):
    text: str = Field(min_length=1, max_length=300000)
    simulated: bool


class ExtractInput(DomainModel):
    category_key: str = "computer"


class ActivateInput(ExtractInput):
    company_id: str
    version: str


class ChangeInput(DomainModel):
    change: dict
    observed_version: dict[str, str]


class ReviewInput(DomainModel):
    candidate_id: str
    decision: Literal["ACCEPTED", "REJECTED"]
    corrected: dict | None = None


class RestartReviewInput(DomainModel):
    observed_version: dict[str, str]


class PublishInput(DomainModel):
    kind: Literal["tree", "ontology"]


class GapInput(SourceInput):
    category_key: str = "computer"


class QuestionInput(DomainModel):
    question: str = Field(min_length=1, max_length=2000)


def create_app(identities, store, catalog, *, draft_parent, client_factory=configured_client,
               frontend_dist: Path | None = None, public_origin: str | None = None):
    origin = urlsplit(public_origin) if public_origin else None
    if origin and (origin.scheme not in {"http", "https"} or not origin.hostname
                   or origin.username or origin.password or "*" in origin.netloc
                   or origin.path or origin.query or origin.fragment):
        raise ValueError("PROCUREMENT_PUBLIC_ORIGIN must be an exact HTTP(S) origin")
    secure_cookie = bool(origin and origin.scheme == "https")
    gate = store.gate
    identities.gate = catalog.gate = gate
    query = KnowledgeQuery(store)
    agent = BuyerAgent(query, client_factory)
    governance, intake = GovernanceService(store, catalog), IntakeService(store)
    drafts = SchemaDraftService(store, draft_parent, client_factory)
    extraction = ExtractionService(store, catalog, client_factory, gap_handler=drafts.from_suggestion)
    mcp = create_mcp(query)
    mcp_app = mcp.streamable_http_app(streamable_http_path="/", stateless_http=True, json_response=True,
                                    transport_security=TransportSecuritySettings(
                                        allowed_hosts=[origin.netloc] if origin else ["127.0.0.1:*", "localhost:*"],
                                        allowed_origins=[public_origin] if origin else ["http://127.0.0.1:*", "http://localhost:*"]))
    provision_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        for company in identities.ready_company_ids():
            extraction.recover_interrupted(company)
        async with mcp.session_manager.run():
            yield

    app = FastAPI(title="采购本体知识服务", lifespan=lifespan)
    if origin:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=[origin.hostname, "127.0.0.1", "localhost"])
    app.state.query, app.state.governance, app.state.extraction, app.state.mcp = query, governance, extraction, mcp
    app.state.identities, app.state.catalog, app.state.store = identities, catalog, store
    app.state.gate = gate

    def error(status, code, message):
        return JSONResponse(status_code=status, content={"code": code, "message": message, "request_id": uuid.uuid4().hex})

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        reset = None
        if request.url.path.startswith("/mcp"):
            try:
                authorization = request.headers.get("Authorization", "")
                if not authorization.startswith("Bearer "):
                    raise PermissionError()
                actor = identities.authenticate_service_token(authorization[7:])
                reset = current_identity.set(actor)
            except MaintenanceError:
                return error(503, "MAINTENANCE", "服务处于维护窗口")
            except PermissionError:
                return error(401, "UNAUTHENTICATED", "需要有效的企业服务令牌")
        elif request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("Origin")
            if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
                return error(403, "ORIGIN_REJECTED", "只接受同源管理请求")
            if request.cookies.get(COOKIE) and not request.headers.get("Authorization") and request.headers.get("X-Requested-With") != "procurement-ontology":
                return error(403, "CSRF_REJECTED", "管理请求缺少同源标记")
        try:
            with gate.writer() if request.method not in {"GET", "HEAD", "OPTIONS"} and not request.url.path.startswith("/mcp") else nullcontext():
                response = await call_next(request)
            if request.url.path.startswith(("/v1", "/mcp")):
                response.headers["Cache-Control"] = "no-store"
            return response
        except MaintenanceError:
            return error(503, "MAINTENANCE", "服务处于维护窗口，暂不接受新写入")
        finally:
            if reset is not None:
                current_identity.reset(reset)

    @app.exception_handler(MaintenanceError)
    async def maintenance(request, exception):
        return error(503, "MAINTENANCE", "服务处于维护窗口")

    @app.exception_handler(PermissionError)
    async def forbidden(request, exception):
        return error(403, "FORBIDDEN", "当前身份无权执行此操作")

    @app.exception_handler(KeyError)
    async def missing(request, exception):
        return error(404, "NOT_FOUND", "记录不存在")

    @app.exception_handler(VersionConflict)
    async def conflict(request, exception):
        return error(409, "VERSION_CHANGED", "版本已变化，请刷新后重新提交")

    @app.exception_handler(ValueError)
    @app.exception_handler(RequestValidationError)
    async def invalid(request, exception):
        return error(422, "VALIDATION_FAILED", "未通过校验，请检查字段、来源、引用及当前版本")

    def identity(request: Request):
        authorization = request.headers.get("Authorization", "")
        token = authorization[7:] if authorization.startswith("Bearer ") else request.cookies.get(COOKIE)
        try:
            if not token:
                raise PermissionError()
            return identities.authenticate_token(token)
        except PermissionError:
            raise HTTPException(401, detail="需要登录") from None

    Actor = Annotated[Identity, Depends(identity)]

    def scoped(request: Request, actor: Actor):
        platform_path = request.url.path.startswith("/v1/platform/")
        if platform_path != (actor.scope_id == "platform"):
            raise PermissionError()
        return actor

    Scoped = Annotated[Identity, Depends(scoped)]

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/v1/session")
    def login(data: Login, response: Response):
        try:
            actor = identities.authenticate(Credentials(data.username, data.password))
        except PermissionError:
            raise HTTPException(401, detail="认证失败") from None
        response.set_cookie(COOKIE, identities.issue_session(actor), secure=secure_cookie,
                            httponly=True, samesite="strict", max_age=3600)
        return asdict(actor)

    @app.get("/v1/me")
    def me(actor: Actor):
        return asdict(actor)

    @app.delete("/v1/session")
    def logout(request: Request, response: Response, actor: Actor):
        token = request.headers.get("Authorization", "")[7:] or request.cookies.get(COOKIE)
        if token:
            identities.revoke_session(token)
        response.delete_cookie(COOKIE, secure=secure_cookie, httponly=True, samesite="strict")
        return {"status": "logged_out"}

    @app.post("/v1/platform/companies")
    def provision(data: NewCompany, actor: Scoped):
        authorize(actor, "platform", "provision")
        with provision_lock:
            state = identities.company_state(data.company_id, actor)
            if state and state["status"] == "READY":
                return state
            identities.create_company(data.company_id, actor)
            store.provision_company(data.company_id, version_pair(store.read_pair("platform")))
            if not identities.company_has_account(data.company_id, actor):
                identities.create_account(data.company_id, "company_admin", Credentials(data.username, data.password), actor)
            identities.mark_company_ready(data.company_id, actor)
            return {"company_id": data.company_id, "status": "READY"}

    @app.post("/v1/manage/schemas/activate")
    def activate(data: ActivateInput, actor: Scoped):
        return asdict(catalog.activate_schema(actor, data.company_id, data.category_key, data.version))

    @app.get("/v1/manage/schemas/active")
    def active_schema(actor: Scoped, category_key: str = "computer"):
        authorize(actor, actor.scope_id, "write")
        binding = catalog.active(actor.scope_id, category_key)
        relation_class = next(slot.range for slot in binding.schema_view.class_induced_slots(binding.root_class) if slot.name == "relations")
        predicate_range = next(slot.range for slot in binding.schema_view.class_induced_slots(relation_class) if slot.name == "predicate")
        return {"version": binding.version, "yaml_sha256": binding.yaml_sha256, "python_sha256": binding.python_sha256,
                "item_types": [slot.range for slot in binding.schema_view.class_induced_slots(binding.root_class) if slot.name not in {"relations", "unmapped_suggestions"}],
                "relation_types": list(binding.schema_view.get_enum(predicate_range).permissible_values),
                "json_schema": binding.python_class.model_json_schema()}

    @app.post("/v1/manage/sources")
    @app.post("/v1/platform/sources")
    def submit_source(data: SourceInput, actor: Scoped):
        return intake.submit(actor, data.text, data.simulated)

    @app.get("/v1/manage/sources")
    @app.get("/v1/platform/sources")
    def sources(actor: Scoped):
        authorize(actor, actor.scope_id, "write")
        return store.list_sources(actor.scope_id)

    @app.post("/v1/manage/sources/{revision_id}/extract")
    def extract(revision_id: str, data: ExtractInput, actor: Scoped):
        return extraction.extract(actor, revision_id, data.category_key)

    @app.get("/v1/manage/runs")
    def runs(actor: Scoped):
        authorize(actor, actor.scope_id, "write")
        return store.list_runs(actor.scope_id)

    @app.get("/v1/manage/runs/{run_id}")
    def run(run_id: str, actor: Scoped):
        authorize(actor, actor.scope_id, "write")
        result = store.read_run(actor.scope_id, run_id)
        if result is None:
            raise KeyError()
        return result

    @app.get("/v1/manage/batches")
    @app.get("/v1/platform/batches")
    def batches(actor: Scoped):
        authorize(actor, actor.scope_id, "write")
        return store.list_change_batches(actor.scope_id)

    @app.get("/v1/manage/batches/{batch_id}")
    @app.get("/v1/platform/batches/{batch_id}")
    def batch(batch_id: str, actor: Scoped):
        authorize(actor, actor.scope_id, "write")
        result = store.read_change_batch(actor.scope_id, batch_id)
        candidates = store.read_batch(actor.scope_id, batch_id)
        if result is None and not candidates:
            raise KeyError()
        return {"batch": result, "candidates": candidates}

    @app.post("/v1/manage/batches/{batch_id}/reviews")
    def review(batch_id: str, data: ReviewInput, actor: Scoped):
        authorize(actor, actor.scope_id, "review")
        if data.candidate_id not in {candidate.id for candidate in store.read_batch(actor.scope_id, batch_id)}:
            raise KeyError()
        return governance.review(actor, data.candidate_id, data.decision, corrected=data.corrected)

    @app.post("/v1/manage/batches/{batch_id}/restart-review")
    def restart_review(batch_id: str, data: RestartReviewInput, actor: Scoped):
        return governance.restart_review(actor, batch_id, data.observed_version)

    @app.get("/v1/manage/tree")
    @app.get("/v1/platform/tree")
    def tree(actor: Scoped):
        return query.tree(actor)

    @app.post("/v1/manage/tree")
    @app.post("/v1/platform/tree")
    def edit_tree(data: ChangeInput, actor: Scoped):
        return governance.edit_tree(actor, data.change, data.observed_version)

    @app.post("/v1/manage/ontology/changes")
    @app.post("/v1/platform/ontology/changes")
    def edit_item(data: ChangeInput, actor: Scoped):
        return governance.edit_item(actor, data.change, data.observed_version)

    @app.post("/v1/manage/batches/{batch_id}/publish")
    @app.post("/v1/platform/batches/{batch_id}/publish")
    def publish(batch_id: str, data: PublishInput, actor: Scoped):
        return governance.publish(actor, data.kind, batch_id)

    @app.get("/v1/ontology/items")
    @app.get("/v1/platform/ontology/items")
    def search(actor: Scoped, q: str = "", category_key: str = "computer"):
        return query.search(actor, q, category_key)

    @app.get("/v1/ontology/items/{item_id}")
    @app.get("/v1/platform/ontology/items/{item_id}")
    def detail(item_id: str, actor: Scoped, ontology_version: str | None = None, tree_version: str | None = None):
        observed = {"tree": tree_version, "ontology": ontology_version} if ontology_version is not None or tree_version is not None else None
        return query.get(actor, item_id, observed)

    @app.post("/v1/manage/schema-gaps")
    def new_gap(data: GapInput, actor: Scoped):
        source = intake.submit(actor, data.text, data.simulated)
        span = SourceSpan(revision_id=source.id, start=0, end=len(source.text), quote=source.text)
        return drafts.from_suggestion(actor, catalog.active(actor.scope_id, data.category_key), source,
                                      {"source_spans": [span.model_dump(mode="json")]})

    @app.get("/v1/manage/schema-drafts")
    def schema_drafts(actor: Scoped):
        authorize(actor, actor.scope_id, "write")
        return store.list_schema_drafts(actor.scope_id)

    @app.get("/v1/manage/schema-drafts/{draft_id}")
    def schema_draft(draft_id: str, actor: Scoped):
        authorize(actor, actor.scope_id, "write")
        result = store.read_schema_draft(actor.scope_id, draft_id)
        if result is None:
            raise KeyError()
        return result

    @app.post("/v1/manage/service-token")
    def service_token(actor: Scoped):
        return {"token": identities.issue_service_token(actor), "expires_in": 86400}

    @app.post("/v1/agent/questions")
    def answer(data: QuestionInput, actor: Actor):
        return agent.answer_laptop_question(actor, data.question)

    app.mount("/mcp", mcp_app)
    if frontend_dist and Path(frontend_dist).is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    return app
