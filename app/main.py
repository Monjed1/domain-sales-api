from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health, sales
from app.core.config import get_settings
from app.scrapers.errors import DropDaxRateLimitError, DropDaxUpstreamError


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Production-ready API for scraping daily domain sales data from "
            "DropDax and other marketplaces. Filter by extension, date range, "
            "price, and venue."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(sales.router, prefix=settings.api_prefix)

    @app.exception_handler(DropDaxRateLimitError)
    async def dropdax_rate_limit_handler(
        _request: Request, exc: DropDaxRateLimitError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": str(exc), "retry_after_seconds": 120},
        )

    @app.exception_handler(DropDaxUpstreamError)
    async def dropdax_upstream_handler(
        _request: Request, exc: DropDaxUpstreamError
    ) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.get("/", tags=["Root"])
    async def root() -> dict[str, str]:
        return {
            "message": settings.app_name,
            "docs": "/docs",
            "health": f"{settings.api_prefix}/health",
            "sales": f"{settings.api_prefix}/sales",
        }

    return app


app = create_app()
