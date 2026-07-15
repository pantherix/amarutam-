import uuid
import json
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models.entities import User, Saree, AuditLog
from src.app.security import get_password_hash

class BaseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

class UserRepository(BaseRepository):
    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        password_plain: str,
        first_name: str,
        last_name: str,
        role: str = "admin"
    ) -> User:
        password_hash = get_password_hash(password_plain)
        user = User(
            email=email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        self.db.add(user)
        await self.db.flush()
        return user

class SareeRepository(BaseRepository):
    async def get_by_id(self, saree_id: uuid.UUID) -> Optional[Saree]:
        result = await self.db.execute(
            select(Saree).where(Saree.id == saree_id)
        )
        return result.scalar_one_or_none()

    async def create_saree(
        self,
        title: str,
        description: str,
        price: float,
        fabric: str,
        color: str,
        image_url: str,
        secondary_images: Optional[List[str]] = None,
        status: str = "in_stock"
    ) -> Saree:
        sec_images_str = json.dumps(secondary_images) if secondary_images else None
        saree = Saree(
            title=title,
            description=description,
            price=price,
            fabric=fabric,
            color=color,
            image_url=image_url,
            secondary_images=sec_images_str,
            status=status
        )
        self.db.add(saree)
        await self.db.flush()
        return saree

    async def update_saree(
        self,
        saree_id: uuid.UUID,
        update_data: Dict[str, Any]
    ) -> Optional[Saree]:
        saree = await self.get_by_id(saree_id)
        if not saree:
            return None
        
        for key, value in update_data.items():
            if key == "secondary_images" and isinstance(value, list):
                saree.secondary_images = json.dumps(value)
            elif hasattr(saree, key):
                setattr(saree, key, value)
                
        await self.db.flush()
        return saree

    async def delete_saree(self, saree_id: uuid.UUID) -> bool:
        saree = await self.get_by_id(saree_id)
        if not saree:
            return False
        await self.db.delete(saree)
        await self.db.flush()
        return True

    async def list_sarees(
        self,
        fabric: Optional[str] = None,
        color: Optional[str] = None,
        status_filter: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None
    ) -> List[Saree]:
        query = select(Saree)
        conditions = []
        
        if fabric:
            conditions.append(Saree.fabric.ilike(f"%{fabric}%"))
        if color:
            conditions.append(Saree.color.ilike(f"%{color}%"))
        if status_filter:
            conditions.append(Saree.status == status_filter)
        if min_price is not None:
            conditions.append(Saree.price >= min_price)
        if max_price is not None:
            conditions.append(Saree.price <= max_price)
            
        if conditions:
            query = query.where(and_(*conditions))
            
        result = await self.db.execute(query.order_by(Saree.created_at.desc()))
        return list(result.scalars().all())

    async def increment_clicks(self, saree_id: uuid.UUID) -> None:
        await self.db.execute(
            update(Saree)
            .where(Saree.id == saree_id)
            .values(clicks=Saree.clicks + 1)
        )
        await self.db.flush()

class AuditLogRepository(BaseRepository):
    async def create_log(
        self,
        user_id: Optional[uuid.UUID],
        action: str,
        resource: str,
        ip_address: str,
        user_agent: str,
        payload: Dict[str, Any]
    ) -> AuditLog:
        payload_str = json.dumps(payload, sort_keys=True)
        payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            ip_address=ip_address,
            user_agent=user_agent,
            payload_hash=payload_hash
        )
        self.db.add(log)
        await self.db.flush()
        return log
