import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.app.models.entities import User, Saree
from src.app.repositories import UserRepository, SareeRepository, AuditLogRepository
from src.app.security import (
    verify_password,
    create_access_token
)

class ServiceException(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def register_admin(self, user_data: Dict[str, Any]) -> User:
        existing = await self.user_repo.get_by_email(user_data["email"])
        if existing:
            raise ServiceException("Email already registered", status_code=400)
            
        user = await self.user_repo.create_user(
            email=user_data["email"],
            password_plain=user_data["password"],
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            role="admin"
        )
        return user

    async def authenticate_admin(self, email: str, password_plain: str) -> Dict[str, Any]:
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password_plain, user.password_hash):
            raise ServiceException("Invalid email or password", status_code=401)
            
        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role}
        )
        return {"access_token": access_token, "user": user}


class SareeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.saree_repo = SareeRepository(db)

    async def list_sarees(
        self,
        fabric: Optional[str] = None,
        color: Optional[str] = None,
        status_filter: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None
    ) -> List[Saree]:
        return await self.saree_repo.list_sarees(
            fabric=fabric,
            color=color,
            status_filter=status_filter,
            min_price=min_price,
            max_price=max_price
        )

    async def get_saree(self, saree_id: uuid.UUID) -> Saree:
        saree = await self.saree_repo.get_by_id(saree_id)
        if not saree:
            raise ServiceException("Saree not found", status_code=404)
        return saree

    async def create_saree(self, saree_data: Dict[str, Any]) -> Saree:
        return await self.saree_repo.create_saree(
            title=saree_data["title"],
            description=saree_data["description"],
            price=saree_data["price"],
            fabric=saree_data["fabric"],
            color=saree_data["color"],
            image_url=saree_data["image_url"],
            secondary_images=saree_data.get("secondary_images"),
            status=saree_data.get("status", "in_stock")
        )

    async def update_saree(self, saree_id: uuid.UUID, update_data: Dict[str, Any]) -> Saree:
        saree = await self.saree_repo.update_saree(saree_id, update_data)
        if not saree:
            raise ServiceException("Saree not found", status_code=404)
        return saree

    async def delete_saree(self, saree_id: uuid.UUID) -> None:
        success = await self.saree_repo.delete_saree(saree_id)
        if not success:
            raise ServiceException("Saree not found", status_code=404)

    async def record_click(self, saree_id: uuid.UUID) -> None:
        saree = await self.saree_repo.get_by_id(saree_id)
        if not saree:
            raise ServiceException("Saree not found", status_code=404)
        await self.saree_repo.increment_clicks(saree_id)

    async def get_analytics(self) -> Dict[str, Any]:
        # Count total sarees
        result_total = await self.db.execute(select(func.count(Saree.id)))
        total_sarees = result_total.scalar() or 0
        
        # Breakdown by status
        result_status = await self.db.execute(
            select(Saree.status, func.count(Saree.id)).group_by(Saree.status)
        )
        status_map = {row[0]: row[1] for row in result_status.all()}
        
        # Breakdown by fabric
        result_fabric = await self.db.execute(
            select(Saree.fabric, func.count(Saree.id)).group_by(Saree.fabric)
        )
        fabric_map = {row[0]: row[1] for row in result_fabric.all()}
        
        # Top clicked sarees (most popular)
        result_popular = await self.db.execute(
            select(Saree).order_by(Saree.clicks.desc()).limit(5)
        )
        popular_sarees = list(result_popular.scalars().all())
        
        return {
            "total_sarees": total_sarees,
            "status_breakdown": status_map,
            "fabric_breakdown": fabric_map,
            "popular_sarees": [
                {
                    "id": str(s.id),
                    "title": s.title,
                    "price": float(s.price),
                    "fabric": s.fabric,
                    "clicks": s.clicks
                } for s in popular_sarees
            ]
        }


class ComplianceService:
    def __init__(self, db: AsyncSession):
        self.audit_repo = AuditLogRepository(db)

    async def log_action(
        self,
        user_id: Optional[uuid.UUID],
        action: str,
        resource: str,
        ip_address: str,
        user_agent: str,
        payload: Dict[str, Any]
    ) -> None:
        await self.audit_repo.create_log(
            user_id=user_id,
            action=action,
            resource=resource,
            ip_address=ip_address,
            user_agent=user_agent,
            payload=payload
        )
