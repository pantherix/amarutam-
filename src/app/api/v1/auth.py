import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database import get_db
from src.app.schemas import UserRegister, UserResponse, UserLogin, Token, MFASetupResponse, StatusResponse, MFAVerifyRequest
from src.app.services import AuthService, ServiceException
from src.app.api.deps import get_current_user, require_role, get_audit_logger

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserRegister,
    db: AsyncSession = Depends(get_db),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    auth_service = AuthService(db)
    try:
        user = await auth_service.register(user_in.model_dump())
        await db.commit()
        await log_audit(
            user_id=user.id,
            action="register_user",
            resource=f"user:{user.id}",
            payload={"email": user.email, "role": user.role}
        )
        return user
    except ServiceException as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/login", response_model=Token)
async def login(
    user_in: UserLogin,
    db: AsyncSession = Depends(get_db),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    auth_service = AuthService(db)
    try:
        res = await auth_service.authenticate(user_in.email, user_in.password)
        await log_audit(
            user_id=None,
            action="login_attempt",
            resource=f"user:{user_in.email}",
            payload={"email": user_in.email, "mfa_required": res["is_mfa_required"]}
        )
        if res["is_mfa_required"]:
            return Token(
                access_token=res["temp_token"],
                token_type="bearer",
                is_mfa_required=True
            )
        return Token(
            access_token=res["access_token"],
            token_type="bearer",
            is_mfa_required=False
        )
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    auth_service = AuthService(db)
    try:
        res = await auth_service.setup_mfa(current_user.id)
        await log_audit(
            user_id=current_user.id,
            action="setup_mfa_attempt",
            resource=f"user:{current_user.id}",
            payload={}
        )
        return res
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/mfa/verify", response_model=StatusResponse)
async def verify_mfa(
    code: str,
    secret: str,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    auth_service = AuthService(db)
    try:
        await auth_service.verify_and_enable_mfa(current_user.id, secret, code)
        await db.commit()
        await log_audit(
            user_id=current_user.id,
            action="enable_mfa",
            resource=f"user:{current_user.id}",
            payload={}
        )
        return StatusResponse(status="success", message="MFA successfully enabled")
    except ServiceException as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/mfa/login", response_model=Token)
async def login_mfa(
    req: MFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    auth_service = AuthService(db)
    try:
        access_token = await auth_service.login_mfa(req.temp_token, req.code)
        await log_audit(
            user_id=None,
            action="login_mfa_success",
            resource="mfa",
            payload={}
        )
        return Token(
            access_token=access_token,
            token_type="bearer",
            is_mfa_required=False
        )
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
