from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database import get_db
from src.app.schemas import DoctorPublicResponse, AvailabilitySlotResponse
from src.app.services import BookingService
from src.app.repositories import DoctorRepository

router = APIRouter()

@router.get("/", response_model=List[DoctorPublicResponse])
async def list_doctors(
    specialty: Optional[str] = None,
    min_rating: Optional[float] = None,
    db: AsyncSession = Depends(get_db)
):
    doc_repo = DoctorRepository(db)
    doctors = await doc_repo.list_doctors(specialty=specialty, min_rating=min_rating)
    
    response = []
    for doc in doctors:
        response.append(
            DoctorPublicResponse(
                id=doc.id,
                first_name=doc.user.profile.first_name if doc.user and doc.user.profile else "Unknown",
                last_name=doc.user.profile.last_name if doc.user and doc.user.profile else "Unknown",
                specialty=doc.specialty,
                bio=doc.bio,
                consultation_fee=float(doc.consultation_fee),
                rating=float(doc.rating)
            )
        )
    return response

@router.get("/{doctor_id}/slots", response_model=List[AvailabilitySlotResponse])
async def list_slots(
    doctor_id: str,
    db: AsyncSession = Depends(get_db)
):
    import uuid
    booking_service = BookingService(db)
    try:
        slots = await booking_service.get_doctor_slots(uuid.UUID(doctor_id))
        return slots
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid doctor ID format")
