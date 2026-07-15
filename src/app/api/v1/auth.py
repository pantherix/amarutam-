from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database import get_db
from src.app.schemas import UserRegister, UserResponse, UserLogin, Token
from src.app.services import AuthService, ServiceException
from src.app.api.deps import get_audit_logger
from src.app.middleware.rate_limit import RateLimiter

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(RateLimiter(limit=5, window=60))])
async def register_admin(
    user_in: UserRegister,
    db: AsyncSession = Depends(get_db),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    auth_service = AuthService(db)
    try:
        user = await auth_service.register_admin(user_in.model_dump())
        await db.commit()
        await log_audit(
            user_id=user.id,
            action="register_admin",
            resource=f"user:{user.id}",
            payload={"email": user.email, "role": user.role}
        )
        return user
    except ServiceException as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/login", response_model=Token, dependencies=[Depends(RateLimiter(limit=10, window=60))])
async def login_admin(
    user_in: UserLogin,
    db: AsyncSession = Depends(get_db),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    auth_service = AuthService(db)
    try:
        res = await auth_service.authenticate_admin(user_in.email, user_in.password)
        user = res["user"]
        await log_audit(
            user_id=user.id,
            action="login_admin_success",
            resource=f"user:{user.id}",
            payload={"email": user_in.email}
        )
        return Token(
            access_token=res["access_token"],
            token_type="bearer"
        )
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
