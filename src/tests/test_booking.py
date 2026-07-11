import pytest
import uuid
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from src.app.models.entities import Prescription

@pytest.mark.asyncio
async def test_booking_concurrency_and_prescription_encryption(client: AsyncClient, db):
    # 1. Register Patient Ramesh
    patient_res = await client.post("/api/v1/auth/register", json={
        "email": "ramesh@amrutam.com", "password": "securepassword123", "role": "patient",
        "first_name": "Ramesh", "last_name": "Kumar", "phone": "+919876543210", "date_of_birth": "1995-08-15"
    })
    patient_id = patient_res.json()["id"]
    
    # 2. Register Doctor Sunita
    doctor_res = await client.post("/api/v1/auth/register", json={
        "email": "sunita@amrutam.com", "password": "securepassword123", "role": "doctor",
        "first_name": "Sunita", "last_name": "Sharma", "phone": "+919876543211", "date_of_birth": "1988-11-20",
        "specialty": "Ayurveda", "bio": "Ayurvedic specialist", "consultation_fee": 500.00
    })
    
    # 3. Logins to get JWT Tokens
    p_login = await client.post("/api/v1/auth/login", json={"email": "ramesh@amrutam.com", "password": "securepassword123"})
    patient_token = p_login.json()["access_token"]
    
    d_login = await client.post("/api/v1/auth/login", json={"email": "sunita@amrutam.com", "password": "securepassword123"})
    doctor_token = d_login.json()["access_token"]
    
    p_headers = {"Authorization": f"Bearer {patient_token}"}
    d_headers = {"Authorization": f"Bearer {doctor_token}"}
    
    # 4. Doctor creates a slot
    start_time = datetime.utcnow() + timedelta(days=1)
    end_time = start_time + timedelta(hours=1)
    slot_res = await client.post(
        "/api/v1/bookings/slots",
        json={"start_time": start_time.isoformat(), "end_time": end_time.isoformat()},
        headers=d_headers
    )
    assert slot_res.status_code == 201
    slot_id = slot_res.json()["id"]
    doctor_profile_id = slot_res.json()["doctor_id"]

    # 5. Patient lists public doctors (Search & Filter)
    search_res = await client.get("/api/v1/doctors/?specialty=Ayurveda")
    assert search_res.status_code == 200
    assert len(search_res.json()) > 0
    assert search_res.json()[0]["first_name"] == "Sunita"

    # 6. Patient books the slot
    booking_res = await client.post(
        "/api/v1/bookings/consultations",
        json={"slot_id": slot_id},
        headers=p_headers
    )
    assert booking_res.status_code == 201
    consultation_id = booking_res.json()["id"]
    
    # 7. Concurrency Test: Try booking the SAME slot again
    # Register another patient to try the concurrent booking
    await client.post("/api/v1/auth/register", json={
        "email": "other@amrutam.com", "password": "securepassword123", "role": "patient",
        "first_name": "Other", "last_name": "Patient", "phone": "+919876543213", "date_of_birth": "1994-01-01"
    })
    other_login = await client.post("/api/v1/auth/login", json={"email": "other@amrutam.com", "password": "securepassword123"})
    other_token = other_login.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}
    
    dup_booking = await client.post(
        "/api/v1/bookings/consultations",
        json={"slot_id": slot_id},
        headers=other_headers
    )
    # Assert conflict status code returned by double booking prevention
    assert dup_booking.status_code == 409
    
    # 8. RBAC Test: Patient attempts to add a prescription
    pres_payload = {
        "consultation_id": consultation_id,
        "diagnosis": "Chronic fatigue mitigated with Ashwagandha.",
        "medications": [
            {"name": "Ashwagandha", "dosage": "500mg", "duration": "30 days", "instructions": "Take once daily after food"}
        ],
        "doctor_signature": "SIG-SHA-256-SUNITA-SHARMA"
    }
    bad_pres_res = await client.post(
        f"/api/v1/bookings/consultations/{consultation_id}/prescription",
        json=pres_payload,
        headers=p_headers
    )
    assert bad_pres_res.status_code == 403  # Forbidden
    
    # 9. Doctor adds the prescription
    pres_res = await client.post(
        f"/api/v1/bookings/consultations/{consultation_id}/prescription",
        json=pres_payload,
        headers=d_headers
    )
    assert pres_res.status_code == 201
    pres_data = pres_res.json()
    assert pres_data["diagnosis"] == "Chronic fatigue mitigated with Ashwagandha."
    assert len(pres_data["medications"]) == 1
    assert pres_data["medications"][0]["name"] == "Ashwagandha"
    
    # 10. Process Payment for Consultation
    payment_res = await client.post(
        f"/api/v1/bookings/consultations/{consultation_id}/payment",
        json={"consultation_id": consultation_id, "amount": 500.00},
        headers=p_headers
    )
    assert payment_res.status_code == 200
    assert payment_res.json()["status"] == "success"
    
    # 11. Verify Database Level Encryption
    # Query database directly using SQLAlchemy session to assert that PHI is encrypted at rest
    result = await db.execute(select(Prescription).where(Prescription.consultation_id == uuid.UUID(consultation_id)))
    raw_prescription = result.scalar_one()
    
    # Raw diagnosis field in database must NOT equal plaintext
    assert raw_prescription.diagnosis_encrypted != "Chronic fatigue mitigated with Ashwagandha."
    # Raw diagnosis field must be a valid base64 encrypted string (checked by confirming we can decrypt it)
    from src.app.security import encryptor
    decrypted_diag = encryptor.decrypt(raw_prescription.diagnosis_encrypted)
    assert decrypted_diag == "Chronic fatigue mitigated with Ashwagandha."
