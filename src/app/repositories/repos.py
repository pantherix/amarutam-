import uuid
import json
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.app.models.entities import User, Profile, Doctor, AvailabilitySlot, Consultation, Prescription, Payment, AuditLog
from src.app.security import get_password_hash

class BaseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

class UserRepository(BaseRepository):
    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.profile), selectinload(User.doctor_profile))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.profile), selectinload(User.doctor_profile))
            .where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        password_plain: str,
        role: str,
        first_name: str,
        last_name: str,
        phone: str,
        date_of_birth: Any,
        is_mfa_enabled: bool = False,
        mfa_secret: Optional[str] = None
    ) -> User:
        # Create User
        password_hash = get_password_hash(password_plain)
        user = User(
            email=email,
            password_hash=password_hash,
            role=role,
            is_mfa_enabled=is_mfa_enabled,
            mfa_secret=mfa_secret
        )
        self.db.add(user)
        await self.db.flush()  # Generate user.id

        # Create Profile (property handles transparent GCM encryption)
        profile = Profile(
            user_id=user.id,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            date_of_birth=date_of_birth
        )
        self.db.add(profile)
        user.profile = profile
        
        await self.db.flush()
        return user

    async def enable_mfa(self, user_id: uuid.UUID, mfa_secret: str) -> None:
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_mfa_enabled=True, mfa_secret=mfa_secret)
        )


class DoctorRepository(BaseRepository):
    async def get_by_id(self, doctor_id: uuid.UUID) -> Optional[Doctor]:
        result = await self.db.execute(
            select(Doctor)
            .options(selectinload(Doctor.user).selectinload(User.profile))
            .where(Doctor.id == doctor_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: uuid.UUID) -> Optional[Doctor]:
        result = await self.db.execute(
            select(Doctor).where(Doctor.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_doctor_profile(
        self,
        user_id: uuid.UUID,
        specialty: str,
        bio: str,
        consultation_fee: float
    ) -> Doctor:
        doctor = Doctor(
            user_id=user_id,
            specialty=specialty,
            bio=bio,
            consultation_fee=consultation_fee
        )
        self.db.add(doctor)
        await self.db.flush()
        return doctor

    async def list_doctors(
        self,
        specialty: Optional[str] = None,
        min_rating: Optional[float] = None
    ) -> List[Doctor]:
        query = select(Doctor).options(selectinload(Doctor.user).selectinload(User.profile))
        
        conditions = []
        if specialty:
            conditions.append(Doctor.specialty.ilike(f"%{specialty}%"))
        if min_rating:
            conditions.append(Doctor.rating >= min_rating)
            
        if conditions:
            query = query.where(and_(*conditions))
            
        result = await self.db.execute(query)
        return list(result.scalars().all())


class BookingRepository(BaseRepository):
    async def create_slot(
        self,
        doctor_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime
    ) -> AvailabilitySlot:
        slot = AvailabilitySlot(
            doctor_id=doctor_id,
            start_time=start_time,
            end_time=end_time,
            status="available"
        )
        self.db.add(slot)
        await self.db.flush()
        return slot

    async def get_slots_for_doctor(
        self,
        doctor_id: uuid.UUID,
        available_only: bool = True
    ) -> List[AvailabilitySlot]:
        query = select(AvailabilitySlot).where(AvailabilitySlot.doctor_id == doctor_id)
        if available_only:
            query = query.where(AvailabilitySlot.status == "available")
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_slot_by_id(self, slot_id: uuid.UUID) -> Optional[AvailabilitySlot]:
        result = await self.db.execute(
            select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id)
        )
        return result.scalar_one_or_none()

    async def get_slot_by_id_for_update(self, slot_id: uuid.UUID) -> Optional[AvailabilitySlot]:
        # Critical pessimistic locking for double booking prevention
        result = await self.db.execute(
            select(AvailabilitySlot)
            .where(AvailabilitySlot.id == slot_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def create_consultation(
        self,
        patient_id: uuid.UUID,
        doctor_id: uuid.UUID,
        slot_id: uuid.UUID
    ) -> Consultation:
        consultation = Consultation(
            patient_id=patient_id,
            doctor_id=doctor_id,
            slot_id=slot_id,
            status="scheduled",
            payment_status="pending"
        )
        self.db.add(consultation)
        await self.db.flush()
        return consultation

    async def get_consultation_by_id(self, consultation_id: uuid.UUID) -> Optional[Consultation]:
        result = await self.db.execute(
            select(Consultation)
            .options(
                selectinload(Consultation.prescription),
                selectinload(Consultation.doctor).selectinload(Doctor.user).selectinload(User.profile),
                selectinload(Consultation.patient).selectinload(User.profile)
            )
            .where(Consultation.id == consultation_id)
        )
        return result.scalar_one_or_none()

    async def list_consultations(self, user_id: uuid.UUID, role: str) -> List[Consultation]:
        query = select(Consultation).options(
            selectinload(Consultation.prescription),
            selectinload(Consultation.doctor).selectinload(Doctor.user).selectinload(User.profile),
            selectinload(Consultation.patient).selectinload(User.profile)
        )
        if role == "patient":
            query = query.where(Consultation.patient_id == user_id)
        elif role == "doctor":
            # Find the doctor entity first
            result = await self.db.execute(select(Doctor.id).where(Doctor.user_id == user_id))
            doc_id = result.scalar_one_or_none()
            if not doc_id:
                return []
            query = query.where(Consultation.doctor_id == doc_id)
        else:
            # Admin gets all
            pass
            
        result = await self.db.execute(query.order_by(Consultation.created_at.desc()))
        return list(result.scalars().all())

    async def create_prescription(
        self,
        consultation_id: uuid.UUID,
        diagnosis: str,
        medications: List[dict],
        doctor_signature: str
    ) -> Prescription:
        prescription = Prescription(
            consultation_id=consultation_id,
            diagnosis=diagnosis,
            medications=medications,
            doctor_signature=doctor_signature
        )
        self.db.add(prescription)
        await self.db.flush()
        return prescription

    async def get_prescription_by_consultation_id(self, consultation_id: uuid.UUID) -> Optional[Prescription]:
        result = await self.db.execute(
            select(Prescription).where(Prescription.consultation_id == consultation_id)
        )
        return result.scalar_one_or_none()


class PaymentRepository(BaseRepository):
    async def create_payment(
        self,
        consultation_id: uuid.UUID,
        amount: float,
        transaction_reference: str
    ) -> Payment:
        payment = Payment(
            consultation_id=consultation_id,
            amount=amount,
            transaction_reference=transaction_reference,
            status="pending"
        )
        self.db.add(payment)
        await self.db.flush()
        return payment

    async def get_payment_by_reference(self, reference: str) -> Optional[Payment]:
        result = await self.db.execute(
            select(Payment).where(Payment.transaction_reference == reference)
        )
        return result.scalar_one_or_none()

    async def update_payment_status(self, payment_id: uuid.UUID, status: str) -> None:
        await self.db.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(status=status)
        )


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
