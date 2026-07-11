from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database import get_db
from src.app.schemas import AnalyticsOverview
from src.app.services import AnalyticsService
from src.app.api.deps import require_role

router = APIRouter()

@router.get("/analytics", response_model=AnalyticsOverview)
async def get_analytics(
    current_user: Any = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db)
) -> Any:
    analytics_service = AnalyticsService(db)
    overview = await analytics_service.get_overview()
    return overview
