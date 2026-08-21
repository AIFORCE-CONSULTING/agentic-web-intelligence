"""HTTP entry point for Agentic Web Intelligence."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.settings import get_settings
from app.web_research.contracts import (
    Evidence,
    ExtractRequest,
    SearchRequest,
    SearchResponse,
    ToolPolicyError,
    ToolProviderError,
)
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

    return app


app = create_app()
