import uuid
from datetime import datetime, date
from typing import List, Optional
from sqlalchemy import String, Boolean, DateTime, Date, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.app.models.base import Base

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # patient, doctor, admin
    is_mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    profile: Mapped[Optional["Profile"]] = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    doctor_profile: Mapped[Optional["Doctor"]] = relationship("Doctor", back_populates="user", uselist=False, cascade="all, delete-orphan")
    consultations_as_patient: Mapped[List["Consultation"]] = relationship("Consultation", back_populates="patient")

class Profile(Base):
    __tablename__ = "profiles"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    first_name_encrypted: Mapped[str] = mapped_column("first_name", Text, nullable=False)
    last_name_encrypted: Mapped[str] = mapped_column("last_name", Text, nullable=False)
    phone_encrypted: Mapped[str] = mapped_column("phone", Text, nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    
    user: Mapped["User"] = relationship("User", back_populates="profile")

    @property
    def first_name(self) -> str:
        from src.app.security import encryptor
        return encryptor.decrypt(self.first_name_encrypted)

    @first_name.setter
    def first_name(self, val: str):
        from src.app.security import encryptor
        self.first_name_encrypted = encryptor.encrypt(val)

    @property
    def last_name(self) -> str:
        from src.app.security import encryptor
        return encryptor.decrypt(self.last_name_encrypted)

    @last_name.setter
    def last_name(self, val: str):
        from src.app.security import encryptor
        self.last_name_encrypted = encryptor.encrypt(val)

    @property
    def phone(self) -> str:
        from src.app.security import encryptor
        return encryptor.decrypt(self.phone_encrypted)

    @phone.setter
    def phone(self, val: str):
        from src.app.security import encryptor
        self.phone_encrypted = encryptor.encrypt(val)

class Doctor(Base):
    __tablename__ = "doctors"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    specialty: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    bio: Mapped[str] = mapped_column(Text, nullable=False)
    consultation_fee: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    rating: Mapped[float] = mapped_column(Numeric(3, 2), default=0.0, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    user: Mapped["User"] = relationship("User", back_populates="doctor_profile")
    slots: Mapped[List["AvailabilitySlot"]] = relationship("AvailabilitySlot", back_populates="doctor", cascade="all, delete-orphan")
    consultations: Mapped[List["Consultation"]] = relationship("Consultation", back_populates="doctor")

class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"
    __table_args__ = (
        UniqueConstraint("doctor_id", "start_time", name="uq_doctor_slot_time"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="available", nullable=False)  # available, booked
    
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="slots")
    consultation: Mapped[Optional["Consultation"]] = relationship("Consultation", back_populates="slot", uselist=False)

class Consultation(Base):
    __tablename__ = "consultations"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False, index=True)
    slot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("availability_slots.id", ondelete="RESTRICT"), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)  # scheduled, active, completed, cancelled
    payment_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, paid, refunded
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    patient: Mapped["User"] = relationship("User", back_populates="consultations_as_patient")
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="consultations")
    slot: Mapped["AvailabilitySlot"] = relationship("AvailabilitySlot", back_populates="consultation")
    prescription: Mapped[Optional["Prescription"]] = relationship("Prescription", back_populates="consultation", uselist=False, cascade="all, delete-orphan")
    payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="consultation")

class Prescription(Base):
    __tablename__ = "prescriptions"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consultation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("consultations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    diagnosis_encrypted: Mapped[str] = mapped_column("diagnosis", Text, nullable=False)
    medications_encrypted: Mapped[str] = mapped_column("medications", Text, nullable=False)
    doctor_signature: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    consultation: Mapped["Consultation"] = relationship("Consultation", back_populates="prescription")

    @property
    def diagnosis(self) -> str:
        from src.app.security import encryptor
        return encryptor.decrypt(self.diagnosis_encrypted)

    @diagnosis.setter
    def diagnosis(self, val: str):
        from src.app.security import encryptor
        self.diagnosis_encrypted = encryptor.encrypt(val)

    @property
    def medications(self) -> List[dict]:
        from src.app.security import encryptor
        try:
            decrypted = encryptor.decrypt(self.medications_encrypted)
            import json
            return json.loads(decrypted)
        except Exception:
            return []

    @medications.setter
    def medications(self, val: List[dict]):
        from src.app.security import encryptor
        import json
        self.medications_encrypted = encryptor.encrypt(json.dumps(val))

class Payment(Base):
    __tablename__ = "payments"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consultation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("consultations.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    transaction_reference: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, success, failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    consultation: Mapped["Consultation"] = relationship("Consultation", back_populates="payments")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
