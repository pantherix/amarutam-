from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database import get_db
from src.app.schemas import SareeAnalyticsResponse
from src.app.services import SareeService
from src.app.api.deps import require_role

router = APIRouter()

@router.get("/analytics", response_model=SareeAnalyticsResponse)
async def get_saree_analytics(
    current_user: Any = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db)
) -> Any:
    saree_service = SareeService(db)
    analytics = await saree_service.get_analytics()
    return analytics
