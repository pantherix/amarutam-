import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_and_login_admin(client: AsyncClient):
    # 1. Register Admin
    reg_payload = {
        "email": "admin@zari.com",
        "password": "securepassword123",
        "first_name": "Rajesh",
        "last_name": "Kumar"
    }
    response = await client.post("/api/v1/auth/register", json=reg_payload)
    assert response.status_code == 201
    user_data = response.json()
    assert user_data["email"] == "admin@zari.com"
    assert user_data["role"] == "admin"
    assert "id" in user_data
    
    # 2. Login Admin
    login_payload = {
        "email": "admin@zari.com",
        "password": "securepassword123"
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
