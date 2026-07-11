import uuid
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database import get_db
from src.app.schemas import (
    AvailabilitySlotCreate,
    AvailabilitySlotResponse,
    ConsultationCreate,
    ConsultationResponse,
    PrescriptionCreate,
    PrescriptionResponse,
    PaymentResponse,
    PaymentInitiate
)
from src.app.services import BookingService, PaymentService, ServiceException
from src.app.api.deps import get_current_user, require_role, get_audit_logger

router = APIRouter()

@router.post("/slots", response_model=AvailabilitySlotResponse, status_code=status.HTTP_201_CREATED)
async def create_slot(
    slot_in: AvailabilitySlotCreate,
    current_user: Any = Depends(require_role(["doctor"])),
    db: AsyncSession = Depends(get_db),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    booking_service = BookingService(db)
    try:
        slot = await booking_service.create_availability_slot(
            doctor_user_id=current_user.id,
            start_time=slot_in.start_time,
            end_time=slot_in.end_time
        )
        await db.commit()
        await log_audit(
            user_id=current_user.id,
            action="create_slot",
            resource=f"slot:{slot.id}",
            payload={"start_time": slot_in.start_time.isoformat(), "end_time": slot_in.end_time.isoformat()}
        )
        return slot
    except ServiceException as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/consultations", response_model=ConsultationResponse, status_code=status.HTTP_201_CREATED)
async def book_consultation(
    booking_in: ConsultationCreate,
    current_user: Any = Depends(require_role(["patient"])),
    db: AsyncSession = Depends(get_db),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    booking_service = BookingService(db)
    try:
        consultation = await booking_service.book_consultation(
            patient_user_id=current_user.id,
            slot_id=booking_in.slot_id
        )
        await db.commit()
        await log_audit(
            user_id=current_user.id,
            action="book_consultation",
            resource=f"consultation:{consultation.id}",
            payload={"slot_id": str(booking_in.slot_id)}
        )
        return consultation
    except ServiceException as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/consultations", response_model=List[ConsultationResponse])
async def list_consultations(
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    booking_service = BookingService(db)
    consultations = await booking_service.list_consultations(
        user_id=current_user.id,
        role=current_user.role
    )
    return consultations

@router.get("/consultations/{consultation_id}", response_model=ConsultationResponse)
async def get_consultation(
    consultation_id: uuid.UUID,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    booking_service = BookingService(db)
    try:
        consultation = await booking_service.get_consultation(
            consultation_id=consultation_id,
            user_id=current_user.id,
            role=current_user.role
        )
        await log_audit(
            user_id=current_user.id,
            action="view_consultation",
            resource=f"consultation:{consultation_id}",
            payload={}
        )
        return consultation
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/consultations/{consultation_id}/prescription", response_model=PrescriptionResponse, status_code=status.HTTP_201_CREATED)
async def add_prescription(
    consultation_id: uuid.UUID,
    prescription_in: PrescriptionCreate,
    current_user: Any = Depends(require_role(["doctor"])),
    db: AsyncSession = Depends(get_db),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    booking_service = BookingService(db)
    try:
        meds = [m.model_dump() for m in prescription_in.medications]
        prescription = await booking_service.add_prescription(
            doctor_user_id=current_user.id,
            consultation_id=consultation_id,
            diagnosis=prescription_in.diagnosis,
            medications=meds,
            signature=prescription_in.doctor_signature
        )
        await db.commit()
        await log_audit(
            user_id=current_user.id,
            action="add_prescription",
            resource=f"prescription:{prescription.id}",
            payload={"consultation_id": str(consultation_id)}
        )
        return prescription
    except ServiceException as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/consultations/{consultation_id}/payment", response_model=PaymentResponse)
async def process_payment(
    consultation_id: uuid.UUID,
    payment_in: PaymentInitiate,
    current_user: Any = Depends(require_role(["patient"])),
    db: AsyncSession = Depends(get_db),
    log_audit: Any = Depends(get_audit_logger)
) -> Any:
    payment_service = PaymentService(db)
    try:
        payment = await payment_service.process_payment(
            consultation_id=consultation_id,
            amount=payment_in.amount
        )
        await db.commit()
        await log_audit(
            user_id=current_user.id,
            action="process_payment",
            resource=f"payment:{payment.id}",
            payload={"amount": payment_in.amount, "status": payment.status}
        )
        return payment
    except ServiceException as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.message)
