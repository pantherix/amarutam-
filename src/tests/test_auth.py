import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_and_login_patient(client: AsyncClient):
    # 1. Register Patient
    reg_payload = {
        "email": "patient@amrutam.com",
        "password": "securepassword123",
        "role": "patient",
        "first_name": "Ramesh",
        "last_name": "Kumar",
        "phone": "+919876543210",
        "date_of_birth": "1995-08-15"
    }
    response = await client.post("/api/v1/auth/register", json=reg_payload)
    assert response.status_code == 201
    user_data = response.json()
    assert user_data["email"] == "patient@amrutam.com"
    assert user_data["role"] == "patient"
    assert "id" in user_data
    
    # 2. Login Patient
    login_payload = {
        "email": "patient@amrutam.com",
        "password": "securepassword123"
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["is_mfa_required"] is False

@pytest.mark.asyncio
async def test_register_and_login_doctor(client: AsyncClient):
    # 1. Register Doctor
    reg_payload = {
        "email": "doctor@amrutam.com",
        "password": "securepassword123",
        "role": "doctor",
        "first_name": "Sunita",
        "last_name": "Sharma",
        "phone": "+919876543211",
        "date_of_birth": "1988-11-20",
        "specialty": "Ayurveda",
        "bio": "Ayurvedic specialist with 10+ years experience",
        "consultation_fee": 500.00
    }
    response = await client.post("/api/v1/auth/register", json=reg_payload)
    assert response.status_code == 201
    user_data = response.json()
    assert user_data["email"] == "doctor@amrutam.com"
    assert user_data["role"] == "doctor"
    
    # 2. Login Doctor
    login_payload = {
        "email": "doctor@amrutam.com",
        "password": "securepassword123"
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data

@pytest.mark.asyncio
async def test_mfa_flow(client: AsyncClient):
    # 1. Register User
    reg_payload = {
        "email": "mfauser@amrutam.com",
        "password": "securepassword123",
        "role": "patient",
        "first_name": "Amit",
        "last_name": "Patel",
        "phone": "+919876543212",
        "date_of_birth": "1990-01-01"
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    
    # 2. Login to get token
    login_payload = {"email": "mfauser@amrutam.com", "password": "securepassword123"}
    res = await client.post("/api/v1/auth/login", json=login_payload)
    token = res.json()["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Setup MFA
    res = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    assert res.status_code == 200
    mfa_setup = res.json()
    assert "secret" in mfa_setup
    assert "qr_code_url" in mfa_setup
    
    # Generate valid code using the secret
    import pyotp
    totp = pyotp.TOTP(mfa_setup["secret"])
    code = totp.now()
    
    # 4. Verify MFA setup
    res = await client.post(f"/api/v1/auth/mfa/verify?code={code}&secret={mfa_setup['secret']}", headers=headers)
    assert res.status_code == 200
    
    # 5. Login again: Should now require MFA step up
    res = await client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["is_mfa_required"] is True
    temp_token = res_data["access_token"]
    
    # 6. Verify MFA code for login completion
    code = totp.now()
    mfa_login_payload = {
        "code": code,
        "temp_token": temp_token
    }
    res = await client.post("/api/v1/auth/mfa/login", json=mfa_login_payload)
    assert res.status_code == 200
    final_token = res.json()["access_token"]
    assert final_token is not None
