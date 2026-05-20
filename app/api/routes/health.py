from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.core.config import get_settings
from app.models.schemas import (
    HealthResponse,
    Marketplace,
    PeriodType,
    SalesQueryParams,
)
from app.services.sales_service import sales_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        marketplace="dropdax",
    )
