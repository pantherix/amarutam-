import uuid
from datetime import datetime, date
from typing import List, Optional, Dict
from pydantic import BaseModel, EmailStr, Field, field_validator

# Common Response
class StatusResponse(BaseModel):
    status: str
    message: str

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None

# User Register/Login schemas
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters long")
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

# Saree schemas
class SareeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    price: float = Field(..., ge=0)
    fabric: str = Field(..., min_length=1, max_length=100)
    color: str = Field(..., min_length=1, max_length=50)
    image_url: str = Field(..., min_length=1)
    secondary_images: Optional[List[str]] = None

class SareeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    fabric: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, min_length=1, max_length=50)
    image_url: Optional[str] = None
    secondary_images: Optional[List[str]] = None
    status: Optional[str] = None  # in_stock, low_stock, sold_out

    @field_validator("status")
    def validate_status(cls, v):
        if v is not None and v not in ("in_stock", "low_stock", "sold_out"):
            raise ValueError("Status must be 'in_stock', 'low_stock', or 'sold_out'")
        return v

class SareeResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    price: float
    fabric: str
    color: str
    image_url: str
    secondary_images: Optional[str] = None  # JSON string
    status: str
    clicks: int
    created_at: datetime

    class Config:
        from_attributes = True

# Analytics schemas
class PopularSareeItem(BaseModel):
    id: str
    title: str
    price: float
    fabric: str
    clicks: int

class SareeAnalyticsResponse(BaseModel):
    total_sarees: int
    status_breakdown: Dict[str, int]
    fabric_breakdown: Dict[str, int]
    popular_sarees: List[PopularSareeItem]
