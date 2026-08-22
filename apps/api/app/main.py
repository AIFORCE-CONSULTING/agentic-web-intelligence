"""HTTP entry point for Agentic Web Intelligence."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.settings import get_settings
from app.web_research.contracts import (
    Evidence,
    ExtractRequest,
    ResearchRun,
    ResearchRunRequest,
    ResearchStoreUnavailable,
    SearchRequest,
    SearchResponse,
    SourceCandidate,
    ToolPolicyError,
    ToolProviderError,
)
from app.web_research.store import ResearchStore
from app.web_research.workflow import run_extract_workflow, run_search_workflow


class HealthResponse(BaseModel):
    """Stable health response shared by operators and infrastructure."""

    status: str
    service: str
    environment: str


def create_app() -> FastAPI:
    """Create the platform API with explicit cross-origin policy."""

    settings = get_settings()
    app = FastAPI(
        title="Agentic Web Intelligence API",
        version="0.1.0",
        description="Gateway and orchestration boundary for enterprise AI agent capabilities.",
    )
    app.state.research_store = ResearchStore(settings.database_url)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

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

    @app.post("/v1/research/extract", response_model=Evidence, tags=["research"])
    async def extract_public_page(request: ExtractRequest) -> Evidence:
        """Return bounded evidence from one approved public HTML page."""

        try:
            return await run_extract_workflow(request.url)
        except ToolPolicyError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

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

    @app.post("/v1/research/runs/{run_id}/extract", response_model=Evidence, tags=["research"])
    async def extract_run_evidence(
        run_id: str, request: ExtractRequest, http_request: Request
    ) -> Evidence:
        """Extract approved evidence and attach it to an existing durable run."""

        store: ResearchStore = http_request.app.state.research_store
        try:
            from uuid import UUID

            evidence = await run_extract_workflow(request.url)
            await store.save_evidence(UUID(run_id), evidence)
            return evidence
        except ValueError as error:
            raise HTTPException(status_code=422, detail="run_id must be a UUID.") from error
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Research run was not found.") from error
        except ToolPolicyError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ResearchStoreUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    return app


app = create_app()
