import uuid
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.app.models.entities import User, Profile, Doctor, AvailabilitySlot, Consultation, Prescription, Payment
from src.app.repositories import UserRepository, DoctorRepository, BookingRepository, PaymentRepository, AuditLogRepository
from src.app.security import (
    verify_password,
    create_access_token,
    decode_token,
    generate_totp_secret,
    get_totp_uri,
    verify_totp_code
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
        self.doc_repo = DoctorRepository(db)

    async def register(self, user_data: Dict[str, Any]) -> User:
        # Check if email exists
        existing = await self.user_repo.get_by_email(user_data["email"])
        if existing:
            raise ServiceException("Email already registered", status_code=400)
            
        role = user_data["role"]
        
        # Start transaction
        user = await self.user_repo.create_user(
            email=user_data["email"],
            password_plain=user_data["password"],
            role=role,
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            phone=user_data["phone"],
            date_of_birth=user_data["date_of_birth"]
        )
        
        # If doctor role, create Doctor entity
        if role == "doctor":
            specialty = user_data.get("specialty")
            bio = user_data.get("bio")
            fee = user_data.get("consultation_fee")
            
            if not specialty or not bio or fee is None:
                raise ServiceException("Specialty, bio, and consultation fee are required for doctors", status_code=400)
                
            await self.doc_repo.create_doctor_profile(
                user_id=user.id,
                specialty=specialty,
                bio=bio,
                consultation_fee=fee
            )
            
        return user

    async def authenticate(self, email: str, password_plain: str) -> Dict[str, Any]:
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password_plain, user.password_hash):
            raise ServiceException("Invalid email or password", status_code=401)
            
        if user.is_mfa_enabled:
            # Generate a temporary step-up token valid for 5 minutes
            temp_token = create_access_token(
                data={"sub": str(user.id), "role": user.role, "mfa_verified": False},
                expires_delta=timedelta(minutes=5)
            )
            return {"is_mfa_required": True, "temp_token": temp_token}
            
        # Standard login
        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role, "mfa_verified": False}
        )
        return {"is_mfa_required": False, "access_token": access_token}

    async def setup_mfa(self, user_id: uuid.UUID) -> Dict[str, str]:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise ServiceException("User not found", status_code=404)
            
        secret = generate_totp_secret()
        qr_uri = get_totp_uri(secret, user.email)
        
        # Save temporary or enable immediately? Let's return it. The user will verify it
        # to finalize enabling MFA.
        return {"secret": secret, "qr_code_url": qr_uri}

    async def verify_and_enable_mfa(self, user_id: uuid.UUID, secret: str, code: str) -> None:
        if not verify_totp_code(secret, code):
            raise ServiceException("Invalid verification code", status_code=400)
            
        await self.user_repo.enable_mfa(user_id, secret)

    async def login_mfa(self, temp_token: str, code: str) -> str:
        payload = decode_token(temp_token)
        if not payload or payload.get("mfa_verified") is True:
            raise ServiceException("Invalid temporary token", status_code=401)
            
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise ServiceException("Invalid token payload", status_code=401)
            
        user_id = uuid.UUID(user_id_str)
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_mfa_enabled or not user.mfa_secret:
            raise ServiceException("MFA not enabled for user", status_code=400)
            
        if not verify_totp_code(user.mfa_secret, code):
            raise ServiceException("Invalid MFA verification code", status_code=401)
            
        # Return fully verified JWT
        return create_access_token(
            data={"sub": str(user.id), "role": user.role, "mfa_verified": True}
        )


class BookingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.doc_repo = DoctorRepository(db)
        self.booking_repo = BookingRepository(db)
        self.user_repo = UserRepository(db)

    async def create_availability_slot(
        self,
        doctor_user_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime
    ) -> AvailabilitySlot:
        doctor = await self.doc_repo.get_by_user_id(doctor_user_id)
        if not doctor:
            raise ServiceException("Doctor profile not found", status_code=404)
            
        if start_time >= end_time:
            raise ServiceException("Start time must be before end time", status_code=400)
            
        # Check for overlaps
        existing_slots = await self.booking_repo.get_slots_for_doctor(doctor.id, available_only=False)
        for slot in existing_slots:
            if (start_time < slot.end_time) and (end_time > slot.start_time):
                raise ServiceException("Overlapping availability slot exists", status_code=400)
                
        return await self.booking_repo.create_slot(doctor.id, start_time, end_time)

    async def get_doctor_slots(self, doctor_id: uuid.UUID) -> List[AvailabilitySlot]:
        return await self.booking_repo.get_slots_for_doctor(doctor_id, available_only=True)

    async def book_consultation(
        self,
        patient_user_id: uuid.UUID,
        slot_id: uuid.UUID
    ) -> Consultation:
        # Start transaction boundary
        async with self.db.begin_nested():
            # Get slot with pessimistic lock
            slot = await self.booking_repo.get_slot_by_id_for_update(slot_id)
            if not slot:
                raise ServiceException("Availability slot not found", status_code=404)
                
            if slot.status != "available":
                raise ServiceException("Slot is already booked", status_code=409)
                
            # Update slot status
            slot.status = "booked"
            
            # Create consultation
            consultation = await self.booking_repo.create_consultation(
                patient_id=patient_user_id,
                doctor_id=slot.doctor_id,
                slot_id=slot.id
            )
            
            # Enqueue background notification and compliance tasks
            from src.app.worker import enqueue_task
            patient = await self.user_repo.get_by_id(patient_user_id)
            doctor = await self.doc_repo.get_by_id(slot.doctor_id)
            patient_email = patient.email if patient else "unknown@amrutam.com"
            doctor_name = f"Dr. {doctor.user.profile.first_name} {doctor.user.profile.last_name}" if doctor and doctor.user and doctor.user.profile else "Doctor"
            
            await enqueue_task(
                "send_booking_notification",
                patient_email,
                doctor_name,
                slot.start_time.isoformat()
            )
            await enqueue_task("run_compliance_check", str(patient_user_id), "book_consultation")
            
            return consultation

    async def get_consultation(self, consultation_id: uuid.UUID, user_id: uuid.UUID, role: str) -> Consultation:
        consultation = await self.booking_repo.get_consultation_by_id(consultation_id)
        if not consultation:
            raise ServiceException("Consultation not found", status_code=404)
            
        # RBAC and tenancy checks
        if role == "patient" and consultation.patient_id != user_id:
            raise ServiceException("Access denied to this consultation", status_code=403)
        elif role == "doctor":
            doctor = await self.doc_repo.get_by_user_id(user_id)
            if not doctor or consultation.doctor_id != doctor.id:
                raise ServiceException("Access denied to this consultation", status_code=403)
                
        return consultation

    async def list_consultations(self, user_id: uuid.UUID, role: str) -> List[Consultation]:
        return await self.booking_repo.list_consultations(user_id, role)

    async def add_prescription(
        self,
        doctor_user_id: uuid.UUID,
        consultation_id: uuid.UUID,
        diagnosis: str,
        medications: List[dict],
        signature: str
    ) -> Prescription:
        consultation = await self.booking_repo.get_consultation_by_id(consultation_id)
        if not consultation:
            raise ServiceException("Consultation not found", status_code=404)
            
        # Confirm this doctor is assigned to consultation
        doctor = await self.doc_repo.get_by_user_id(doctor_user_id)
        if not doctor or consultation.doctor_id != doctor.id:
            raise ServiceException("Access denied: You are not the assigned doctor for this consultation", status_code=403)
            
        # Create prescription
        prescription = await self.booking_repo.create_prescription(
            consultation_id=consultation.id,
            diagnosis=diagnosis,
            medications=medications,
            doctor_signature=signature
        )
        
        # Complete consultation lifecycle status
        consultation.status = "completed"
        
        # Enqueue background pdf generation task
        from src.app.worker import enqueue_task
        await enqueue_task("generate_prescription_pdf", str(prescription.id))
        
        return prescription


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.pay_repo = PaymentRepository(db)
        self.booking_repo = BookingRepository(db)

    async def process_payment(self, consultation_id: uuid.UUID, amount: float) -> Payment:
        consultation = await self.booking_repo.get_consultation_by_id(consultation_id)
        if not consultation:
            raise ServiceException("Consultation not found", status_code=404)
            
        # Generate dummy transaction reference representing payment gateway handshake
        ref = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        
        # Create payment record
        payment = await self.pay_repo.create_payment(
            consultation_id=consultation_id,
            amount=amount,
            transaction_reference=ref
        )
        
        # Simulate payment gateway approval
        payment.status = "success"
        consultation.payment_status = "paid"
        
        return payment


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


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_overview(self) -> Dict[str, Any]:
        # Aggregate statistics queries
        # Total consultations
        result_total = await self.db.execute(select(func.count(Consultation.id)))
        total_consults = result_total.scalar() or 0
        
        # Total revenue
        result_revenue = await self.db.execute(
            select(func.sum(Payment.amount)).where(Payment.status == "success")
        )
        total_rev = float(result_revenue.scalar() or 0.0)
        
        # Consultations by status
        result_status = await self.db.execute(
            select(Consultation.status, func.count(Consultation.id))
            .group_by(Consultation.status)
        )
        status_map = {row[0]: row[1] for row in result_status.all()}
        
        # Revenue by doctor specialty
        result_spec = await self.db.execute(
            select(Doctor.specialty, func.sum(Payment.amount))
            .join(Consultation, Consultation.doctor_id == Doctor.id)
            .join(Payment, Payment.consultation_id == Consultation.id)
            .where(Payment.status == "success")
            .group_by(Doctor.specialty)
        )
        spec_revenue = {row[0]: float(row[1]) for row in result_spec.all()}
        
        return {
            "total_consultations": total_consults,
            "total_revenue": total_rev,
            "consultations_by_status": status_map,
            "revenue_by_specialty": spec_revenue
        }
