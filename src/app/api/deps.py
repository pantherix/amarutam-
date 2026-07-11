import uuid
from typing import AsyncGenerator, Callable
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database import get_db
from src.app.models.entities import User
from src.app.repositories import UserRepository, DoctorRepository, BookingRepository
from src.app.services import ComplianceService
from src.app.security import decode_token

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(uuid.UUID(user_id_str))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Check if MFA is enabled but NOT verified in token
    if user.is_mfa_enabled and not payload.get("mfa_verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA verification required",
        )
        
    return user

def require_role(allowed_roles: list[str]) -> Callable:
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for this user role",
            )
        return current_user
    return role_checker

async def get_audit_logger(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Callable:
    compliance_service = ComplianceService(db)
    
    async def log_audit(user_id: uuid.UUID | None, action: str, resource: str, payload: dict):
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "unknown")
        await compliance_service.log_action(
            user_id=user_id,
            action=action,
            resource=resource,
            ip_address=client_ip,
            user_agent=user_agent,
            payload=payload
        )
        
    return log_audit
