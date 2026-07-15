import uuid
import os
import shutil
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database import get_db
from src.app.schemas import (
    SareeCreate,
    SareeUpdate,
    SareeResponse,
    StatusResponse
)
from src.app.services import SareeService, ServiceException
from src.app.api.deps import require_role, get_audit_logger
from src.app.middleware.rate_limit import RateLimiter

router = APIRouter()

@router.get("/config")
async def get_saree_config():
    from src.app.config import settings
    return {
        "whatsapp_phone": settings.WHATSAPP_PHONE_NUMBER,
        "project_name": settings.PROJECT_NAME
    }

# Public catalog endpoints
@router.get("/", response_model=List[SareeResponse])
async def list_sarees(
    fabric: Optional[str] = None,
    color: Optional[str] = None,
    status_filter: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    db: AsyncSession = Depends(get_db)
) -> Any:
    saree_service = SareeService(db)
    sarees = await saree_service.list_sarees(
        fabric=fabric,
        color=color,
        status_filter=status_filter,
        min_price=min_price,
        max_price=max_price
    )
    return sarees

@router.get("/{saree_id}", response_model=SareeResponse)
async def get_saree(
    saree_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> Any:
    saree_service = SareeService(db)
    try:
        saree = await saree_service.get_saree(saree_id)
        return saree
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/{saree_id}/click", response_model=StatusResponse)
async def record_saree_click(
    saree_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    rate_limit: Any = Depends(RateLimiter(limit=30, window=60))  # Anti-spam for clicks
) -> Any:
    saree_service = SareeService(db)
    try:
        await saree_service.record_click(saree_id)
        await db.commit()
        return StatusResponse(status="success", message="Click recorded")
    except ServiceException as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.message)

# Admin only management endpoints
@router.post("/", response_model=SareeResponse, status_code=status.HTTP_201_CREATED)
async def create_saree(
    saree_in: SareeCreate,
    current_user: Any = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    saree_service = SareeService(db)
    try:
        saree = await saree_service.create_saree(saree_in.model_dump())
        await db.commit()
        await log_audit(
            user_id=current_user.id,
            action="create_saree",
            resource=f"saree:{saree.id}",
            payload={"title": saree.title, "price": saree.price}
        )
        return saree
    except ServiceException as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.put("/{saree_id}", response_model=SareeResponse)
async def update_saree(
    saree_id: uuid.UUID,
    saree_in: SareeUpdate,
    current_user: Any = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    saree_service = SareeService(db)
    try:
        saree = await saree_service.update_saree(saree_id, saree_in.model_dump(exclude_unset=True))
        await db.commit()
        await log_audit(
            user_id=current_user.id,
            action="update_saree",
            resource=f"saree:{saree_id}",
            payload=saree_in.model_dump(exclude_unset=True)
        )
        return saree
    except ServiceException as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.delete("/{saree_id}", response_model=StatusResponse)
async def delete_saree(
    saree_id: uuid.UUID,
    current_user: Any = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    saree_service = SareeService(db)
    try:
        await saree_service.delete_saree(saree_id)
        await db.commit()
        await log_audit(
            user_id=current_user.id,
            action="delete_saree",
            resource=f"saree:{saree_id}",
            payload={}
        )
        return StatusResponse(status="success", message="Saree deleted successfully")
    except ServiceException as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.message)

# Admin image upload route
@router.post("/upload", response_model=StatusResponse)
async def upload_image(
    file: UploadFile = File(...),
    current_user: Any = Depends(require_role(["admin"])),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    # Ensure static uploads directory exists
    uploads_dir = os.path.join("src", "app", "static", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Save file with secure or simple uuid prefix to prevent collision
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(uploads_dir, unique_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        public_url = f"/static/uploads/{unique_filename}"
        
        await log_audit(
            user_id=current_user.id,
            action="upload_saree_image",
            resource=public_url,
            payload={"filename": file.filename}
        )
        return StatusResponse(status="success", message=public_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")
