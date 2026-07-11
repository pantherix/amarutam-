import uuid
from datetime import datetime, date
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, EmailStr, Field, field_validator

# Common Response
class StatusResponse(BaseModel):
    status: str
    message: str

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    is_mfa_required: bool = False

class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None
    mfa_verified: bool = False

# User Register/Login schemas
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters long")
    role: str = Field("patient", description="Role: patient, doctor, admin")
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    phone: str = Field(..., description="Phone number")
    date_of_birth: date
    
    # Doctor specific (required if role is doctor)
    specialty: Optional[str] = None
    bio: Optional[str] = None
    consultation_fee: Optional[float] = Field(None, ge=0)

    @field_validator("role")
    def validate_role(cls, v):
        if v not in ("patient", "doctor", "admin"):
            raise ValueError("Role must be 'patient', 'doctor', or 'admin'")
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: str
    is_mfa_enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True

# MFA schemas
class MFASetupResponse(BaseModel):
    secret: str
    qr_code_url: str

class MFAVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    temp_token: str

class ProfileResponse(BaseModel):
    user_id: uuid.UUID
    first_name: str
    last_name: str
    phone: str
    date_of_birth: date

    class Config:
        from_attributes = True

class DoctorProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    specialty: str
    bio: str
    consultation_fee: float
    rating: float
    is_verified: bool

    class Config:
        from_attributes = True

class DoctorPublicResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    specialty: str
    bio: str
    consultation_fee: float
    rating: float

# Availability Slot schemas
class AvailabilitySlotCreate(BaseModel):
    start_time: datetime
    end_time: datetime

    @field_validator("end_time")
    def validate_end_time(cls, v, info):
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("end_time must be after start_time")
        return v

class AvailabilitySlotResponse(BaseModel):
    id: uuid.UUID
    doctor_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    status: str

    class Config:
        from_attributes = True

# Consultation schemas
class ConsultationCreate(BaseModel):
    slot_id: uuid.UUID

class ConsultationResponse(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    slot_id: uuid.UUID
    status: str
    payment_status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Prescription schemas
class MedicationItem(BaseModel):
    name: str = Field(..., min_length=1)
    dosage: str = Field(..., min_length=1)
    duration: str = Field(..., min_length=1)
    instructions: Optional[str] = None

class PrescriptionCreate(BaseModel):
    consultation_id: uuid.UUID
    diagnosis: str = Field(..., min_length=1)
    medications: List[MedicationItem]
    doctor_signature: str = Field(..., min_length=1)

class PrescriptionResponse(BaseModel):
    id: uuid.UUID
    consultation_id: uuid.UUID
    diagnosis: str
    medications: List[MedicationItem]
    doctor_signature: str
    created_at: datetime

    class Config:
        from_attributes = True

# Payment schemas
class PaymentInitiate(BaseModel):
    consultation_id: uuid.UUID
    amount: float = Field(..., gt=0)

class PaymentResponse(BaseModel):
    id: uuid.UUID
    consultation_id: uuid.UUID
    amount: float
    transaction_reference: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Admin Analytics schema
class AnalyticsOverview(BaseModel):
    total_consultations: int
    total_revenue: float
    consultations_by_status: Dict[str, int]
    revenue_by_specialty: Dict[str, float]
