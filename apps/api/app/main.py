"""HTTP entry point for Agentic Web Intelligence."""

import asyncio
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agent_runtime.contracts import (
    RuntimeRun,
    RuntimeRunList,
    RuntimeStoreUnavailable,
)
from app.agent_runtime.service import RuntimeService
from app.agent_runtime.store import RuntimeStore
from app.identity.contracts import AuthenticatedUser, BootstrapAdminRequest, SignInRequest
from app.identity.service import SESSION_COOKIE_NAME, AuthenticationError, IdentityService
from app.identity.store import IdentityStore, IdentityStoreUnavailable
from app.prompt_templates import (
    GovernedResearchPromptRequest,
    PromptTemplateInfo,
    PromptTemplateList,
    RenderedPrompt,
    governed_research_template_info,
    render_governed_research_prompt,
)
from app.settings import get_settings
from app.web_research.contracts import (
    BatchExtractionOutcome,
    BatchExtractRequest,
    BatchExtractResponse,
    Evidence,
    ExtractRequest,
    McpToolAuditList,
    ResearchRun,
    ResearchRunList,
    ResearchRunRequest,
    ResearchStoreUnavailable,
    SearchRequest,
    SearchResponse,
    SourceCandidate,
    ToolPolicyError,
    ToolProviderError,
    ToolRetrievalError,
)
from app.web_research.mcp_host import GovernedWebMcpHost
from app.web_research.store import ResearchStore
from app.web_research.workflow import run_extract_workflow, run_search_workflow


class HealthResponse(BaseModel):
    """Stable health response shared by operators and infrastructure."""

    status: str
    service: str
    environment: str


class DependencyHealth(BaseModel):
    """A safe, operator-facing status for one platform dependency."""

    name: str
    status: Literal["ready", "unavailable", "unconfigured"]
    detail: str


class ServiceHealthResponse(HealthResponse):
    """Readiness plus bounded dependency health for the developer portal."""

    services: list[DependencyHealth]


def create_app() -> FastAPI:
    """Create the platform API with explicit cross-origin policy."""

    settings = get_settings()
    app = FastAPI(
        title="Agentic Web Intelligence API",
        version="0.1.0",
        description="Gateway and orchestration boundary for enterprise AI agent capabilities.",
    )
    app.state.research_store = ResearchStore(settings.database_url)
    app.state.runtime_store = RuntimeStore(settings.database_url)
    app.state.runtime_service = RuntimeService(app.state.runtime_store)
    app.state.identity_store = IdentityStore(settings.database_url)
    app.state.identity_service = IdentityService(
        app.state.identity_store, settings.auth_bootstrap_secret
    )
    app.state.mcp_host = GovernedWebMcpHost(
        audit_recorder=app.state.research_store.record_mcp_tool_event
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    def set_session_cookie(response: Response, token: str) -> None:
        """Set an opaque, HttpOnly session token that browser JavaScript cannot read."""

        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            max_age=8 * 60 * 60,
            httponly=True,
            secure=settings.app_environment != "development",
            samesite="lax",
            path="/",
        )

    @app.post(
        "/v1/auth/bootstrap",
        response_model=AuthenticatedUser,
        status_code=201,
        tags=["auth"],
    )
    async def bootstrap_local_administrator(
        request: BootstrapAdminRequest, response: Response, http_request: Request
    ) -> AuthenticatedUser:
        """Create the only initial local administrator when deployment secret proof succeeds."""

        service: IdentityService = http_request.app.state.identity_service
        try:
            user, token = await service.bootstrap_admin(
                request.bootstrap_secret, str(request.email), request.password
            )
        except AuthenticationError as error:
            raise HTTPException(status_code=401, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except IdentityStoreUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        set_session_cookie(response, token)
        return user

    @app.post("/v1/auth/sign-in", response_model=AuthenticatedUser, tags=["auth"])
    async def sign_in_local_user(
        request: SignInRequest, response: Response, http_request: Request
    ) -> AuthenticatedUser:
        """Authenticate a local user without disclosing whether an account exists."""

        service: IdentityService = http_request.app.state.identity_service
        try:
            user, token = await service.sign_in(str(request.email), request.password)
        except AuthenticationError as error:
            raise HTTPException(status_code=401, detail=str(error)) from error
        except IdentityStoreUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        set_session_cookie(response, token)
        return user

    @app.get("/v1/auth/me", response_model=AuthenticatedUser, tags=["auth"])
    async def current_authenticated_user(http_request: Request) -> AuthenticatedUser:
        """Return the server-validated identity associated with the opaque browser session."""

        service: IdentityService = http_request.app.state.identity_service
        try:
            user = await service.current_user(http_request.cookies.get(SESSION_COOKIE_NAME))
        except IdentityStoreUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication is required.")
        return user

    @app.post("/v1/auth/sign-out", status_code=204, tags=["auth"])
    async def sign_out_local_user(response: Response, http_request: Request) -> Response:
        """Revoke the server session and remove its browser cookie."""

        service: IdentityService = http_request.app.state.identity_service
        try:
            await service.sign_out(http_request.cookies.get(SESSION_COOKIE_NAME))
        except IdentityStoreUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        return response

    @app.get("/health/live", response_model=HealthResponse, tags=["health"])
    async def liveness() -> HealthResponse:
        """Confirm that the API process is running."""

        return HealthResponse(
            status="ok",
            service="agentic-web-intelligence-api",
            environment=settings.app_environment,
        )

    @app.get("/health/ready", response_model=HealthResponse, tags=["health"])
    async def readiness() -> HealthResponse:
        """Confirm that the API can accept platform requests.

        Future phases will extend this check with required dependency probes.
        """

        return HealthResponse(
            status="ready",
            service="agentic-web-intelligence-api",
            environment=settings.app_environment,
        )

    @app.get("/health/services", response_model=ServiceHealthResponse, tags=["health"])
    async def service_health(http_request: Request) -> ServiceHealthResponse:
        """Report whether the Phase 2 persistence and discovery dependencies are usable."""

        store: ResearchStore = http_request.app.state.research_store

        async def persistence_health() -> DependencyHealth:
            try:
                await store.healthcheck()
            except ResearchStoreUnavailable:
                return DependencyHealth(
                    name="Research persistence",
                    status="unavailable" if settings.database_url else "unconfigured",
                    detail="Postgres is not available for durable research runs.",
                )
            return DependencyHealth(
                name="Research persistence",
                status="ready",
                detail="Postgres is available for durable research runs and audit history.",
            )

        async def discovery_health() -> DependencyHealth:
            if not settings.searxng_base_url:
                return DependencyHealth(
                    name="Governed discovery",
                    status="unconfigured",
                    detail="No internal search provider is configured.",
                )
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    response = await client.get(f"{settings.searxng_base_url.rstrip('/')}/healthz")
                    response.raise_for_status()
            except httpx.HTTPError:
                return DependencyHealth(
                    name="Governed discovery",
                    status="unavailable",
                    detail="The internal search provider is unavailable.",
                )
            return DependencyHealth(
                name="Governed discovery",
                status="ready",
                detail="The internal search provider is available through the governed boundary.",
            )

        services = await asyncio.gather(persistence_health(), discovery_health())
        return ServiceHealthResponse(
            status=(
                "ready" if all(service.status == "ready" for service in services) else "degraded"
            ),
            service="agentic-web-intelligence-api",
            environment=settings.app_environment,
            services=services,
        )

    @app.get("/v1/mcp/tools", tags=["mcp"])
    async def list_mcp_tools(http_request: Request) -> dict[str, object]:
        """List the small, platform-owned tool registry visible to agents."""

        host: GovernedWebMcpHost = http_request.app.state.mcp_host
        return {"tools": host.list_tools()}

    @app.get("/v1/runtime/runs/{run_id}", response_model=RuntimeRun, tags=["runtime"])
    async def get_runtime_run(run_id: str, http_request: Request) -> RuntimeRun:
        """Inspect a runtime run without exposing mutation of its authority fields."""

        from uuid import UUID

        try:
            parsed_run_id = UUID(run_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail="run_id must be a UUID.") from error
        store: RuntimeStore = http_request.app.state.runtime_store
        try:
            run = await store.get_run(parsed_run_id)
        except RuntimeStoreUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        if run is None:
            raise HTTPException(status_code=404, detail="Runtime run was not found.")
        return run

    @app.get("/v1/runtime/runs", response_model=RuntimeRunList, tags=["runtime"])
    async def list_runtime_runs(
        http_request: Request, limit: int = Query(default=25, ge=1, le=50)
    ) -> RuntimeRunList:
        """List bounded runtime state for operator inspection."""

        store: RuntimeStore = http_request.app.state.runtime_store
        try:
            return RuntimeRunList(runs=await store.list_runs(limit))
        except RuntimeStoreUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.get("/v1/mcp/audit", response_model=McpToolAuditList, tags=["mcp"])
    async def list_mcp_tool_audit(
        http_request: Request, limit: int = Query(default=25, ge=1, le=100)
    ) -> McpToolAuditList:
        """List bounded, durable outcomes from direct MCP tool calls."""

        store: ResearchStore = http_request.app.state.research_store
        try:
            return McpToolAuditList(events=await store.list_mcp_tool_events(limit))
        except ResearchStoreUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.post("/mcp", tags=["mcp"])
    async def serve_mcp(payload: dict[str, object], http_request: Request) -> dict[str, object]:
        """Serve the Phase 2 MCP JSON-RPC tool protocol over HTTP."""

        host: GovernedWebMcpHost = http_request.app.state.mcp_host
        return await host.handle(payload)

    @app.get("/v1/prompts", response_model=PromptTemplateList, tags=["prompts"])
    async def list_prompt_templates() -> PromptTemplateList:
        """List stable prompt declarations without rendering caller inputs."""

        return PromptTemplateList(prompts=[governed_research_template_info()])

    @app.get("/v1/prompts/governed-research", response_model=PromptTemplateInfo, tags=["prompts"])
    async def get_governed_research_template() -> PromptTemplateInfo:
        """Return the prompt declaration that future MCP clients can discover."""

        return governed_research_template_info()

    @app.post(
        "/v1/prompts/governed-research/render", response_model=RenderedPrompt, tags=["prompts"]
    )
    async def render_governed_research_template(
        request: GovernedResearchPromptRequest,
    ) -> RenderedPrompt:
        """Render an auditable, versioned research instruction without calling a model."""

        return render_governed_research_prompt(request)

    @app.post("/v1/research/extract", response_model=Evidence, tags=["research"])
    async def extract_public_page(request: ExtractRequest) -> Evidence:
        """Return bounded evidence from one approved public HTML page."""

        try:
            return await run_extract_workflow(request.url)
        except ToolPolicyError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ToolRetrievalError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @app.post("/v1/research/search", response_model=SearchResponse, tags=["research"])
    async def search_public_web(request: SearchRequest) -> SearchResponse:
        """Return bounded candidate sources from the internal search provider."""

        try:
            return await run_search_workflow(request.query, request.max_results)
        except ToolProviderError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.post("/v1/research/runs", response_model=ResearchRun, status_code=201, tags=["research"])
    async def create_research_run(
        request: ResearchRunRequest, http_request: Request
    ) -> ResearchRun:
        """Persist a discovery run and its source provenance as one durable record."""

        store: ResearchStore = http_request.app.state.research_store
        try:
            run = await store.create_run(request.question)
            try:
                search = await run_search_workflow(request.question, request.max_results)
            except ToolProviderError as error:
                await store.mark_failed(run.id, str(error))
                raise HTTPException(status_code=503, detail=str(error)) from error
            sources = [
                SourceCandidate(rank=index, **result.model_dump())
                for index, result in enumerate(search.results, start=1)
            ]
            await store.save_sources(run.id, sources)
            persisted_run = await store.get_run(run.id)
            assert persisted_run is not None
            return persisted_run
        except ResearchStoreUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.get("/v1/research/runs/{run_id}", response_model=ResearchRun, tags=["research"])
    async def get_research_run(run_id: str, http_request: Request) -> ResearchRun:
        """Retrieve sources, evidence, and audit events from a prior research run."""

        store: ResearchStore = http_request.app.state.research_store
        try:
            from uuid import UUID

            run = await store.get_run(UUID(run_id))
        except ValueError as error:
            raise HTTPException(status_code=422, detail="run_id must be a UUID.") from error
        except ResearchStoreUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        if run is None:
            raise HTTPException(status_code=404, detail="Research run was not found.")
        return run

    @app.get("/v1/research/runs", response_model=ResearchRunList, tags=["research"])
    async def list_research_runs(
        http_request: Request, limit: int = Query(default=25, ge=1, le=50)
    ) -> ResearchRunList:
        """List recent durable runs without returning the potentially large evidence bodies."""

        store: ResearchStore = http_request.app.state.research_store
        try:
            return ResearchRunList(runs=await store.list_runs(limit))
        except ResearchStoreUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.post("/v1/research/runs/{run_id}/extract", response_model=Evidence, tags=["research"])
    async def extract_run_evidence(
        run_id: str, request: ExtractRequest, http_request: Request
    ) -> Evidence:
        """Extract approved evidence and attach it to an existing durable run."""

        store: ResearchStore = http_request.app.state.research_store
        try:
            from uuid import UUID

            parsed_run_id = UUID(run_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail="run_id must be a UUID.") from error
        try:
            if not await store.run_exists(parsed_run_id):
                raise HTTPException(status_code=404, detail="Research run was not found.")
            try:
                evidence = await run_extract_workflow(request.url)
            except ToolPolicyError as error:
                await store.record_policy_denial(parsed_run_id, request.url, str(error))
                raise HTTPException(status_code=422, detail=str(error)) from error
            except ToolRetrievalError as error:
                await store.record_extraction_failure(
                    parsed_run_id, request.url, str(error), error.upstream_status
                )
                raise HTTPException(status_code=502, detail=str(error)) from error
            await store.save_evidence(parsed_run_id, evidence)
            return evidence
        except ResearchStoreUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.post(
        "/v1/research/runs/{run_id}/extract-batch",
        response_model=BatchExtractResponse,
        tags=["research"],
    )
    async def extract_run_evidence_batch(
        run_id: str, request: BatchExtractRequest, http_request: Request
    ) -> BatchExtractResponse:
        """Sequentially extract selected candidates and preserve every outcome."""

        store: ResearchStore = http_request.app.state.research_store
        try:
            from uuid import UUID

            parsed_run_id = UUID(run_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail="run_id must be a UUID.") from error
        try:
            run = await store.get_run(parsed_run_id)
            if run is None:
                raise HTTPException(status_code=404, detail="Research run was not found.")
            if len(set(request.urls)) != len(request.urls):
                raise HTTPException(
                    status_code=422, detail="Each selected source URL must be unique."
                )
            candidate_urls = {source.url for source in run.sources}
            unknown_urls = [url for url in request.urls if url not in candidate_urls]
            if unknown_urls:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Batch extraction accepts only source candidates from this research run."
                    ),
                )

            await store.record_batch_extraction_started(parsed_run_id, request.urls)
            outcomes: list[BatchExtractionOutcome] = []
            for url in request.urls:
                try:
                    evidence = await run_extract_workflow(url)
                except ToolPolicyError as error:
                    await store.record_policy_denial(parsed_run_id, url, str(error))
                    outcomes.append(
                        BatchExtractionOutcome(url=url, status="denied", reason=str(error))
                    )
                except ToolRetrievalError as error:
                    await store.record_extraction_failure(
                        parsed_run_id, url, str(error), error.upstream_status
                    )
                    outcomes.append(
                        BatchExtractionOutcome(
                            url=url,
                            status="failed",
                            reason=str(error),
                            upstream_status=error.upstream_status,
                        )
                    )
                except ToolProviderError as error:
                    await store.record_extraction_failure(parsed_run_id, url, str(error), None)
                    outcomes.append(
                        BatchExtractionOutcome(url=url, status="failed", reason=str(error))
                    )
                else:
                    await store.save_evidence(parsed_run_id, evidence)
                    outcomes.append(
                        BatchExtractionOutcome(url=url, status="succeeded", evidence=evidence)
                    )

            succeeded = sum(outcome.status == "succeeded" for outcome in outcomes)
            failed = sum(outcome.status == "failed" for outcome in outcomes)
            denied = sum(outcome.status == "denied" for outcome in outcomes)
            await store.record_batch_extraction_completed(parsed_run_id, succeeded, failed, denied)
            return BatchExtractResponse(run_id=parsed_run_id, outcomes=outcomes)
        except ResearchStoreUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    return app


app = create_app()
