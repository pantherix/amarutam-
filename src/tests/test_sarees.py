import pytest
import uuid
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_saree_lifecycle(client: AsyncClient):
    # 1. Register Admin
    reg_payload = {
        "email": "owner@zari.com",
        "password": "securepassword123",
        "first_name": "Meera",
        "last_name": "Sen"
    }
    await client.post("/api/v1/auth/register", json=reg_payload)
    
    # 2. Login to get token
    login_payload = {"email": "owner@zari.com", "password": "securepassword123"}
    login_res = await client.post("/api/v1/auth/login", json=login_payload)
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Admin creates a Saree listing
    saree_payload = {
        "title": "Royal Crimson Banarasi Silk",
        "description": "Exquisite handwoven Banarasi pure silk saree with intricate zari work.",
        "price": 4500.00,
        "fabric": "Banarasi Silk",
        "color": "Crimson Red",
        "image_url": "https://example.com/saree1.jpg",
        "secondary_images": ["https://example.com/saree1_detail.jpg"]
    }
    create_res = await client.post("/api/v1/sarees/", json=saree_payload, headers=headers)
    assert create_res.status_code == 201
    saree_id = create_res.json()["id"]
    assert create_res.json()["title"] == "Royal Crimson Banarasi Silk"
    
    # 4. Public lists sarees (filter by fabric and color)
    list_res = await client.get("/api/v1/sarees/?fabric=Silk&color=Red")
    assert list_res.status_code == 200
    sarees = list_res.json()
    assert len(sarees) > 0
    assert sarees[0]["title"] == "Royal Crimson Banarasi Silk"
    
    # 5. Public gets a single saree
    get_res = await client.get(f"/api/v1/sarees/{saree_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == saree_id
    
    # 6. Public clicks the saree
    click_res = await client.post(f"/api/v1/sarees/{saree_id}/click")
    assert click_res.status_code == 200
    
    # 7. Check if click was recorded in analytics
    analytics_res = await client.get("/api/v1/admin/analytics", headers=headers)
    assert analytics_res.status_code == 200
    analytics_data = analytics_res.json()
    assert analytics_data["total_sarees"] == 1
    assert len(analytics_data["popular_sarees"]) > 0
    assert analytics_data["popular_sarees"][0]["clicks"] == 1
    
    # 8. Admin updates the saree status to sold_out
    update_res = await client.put(f"/api/v1/sarees/{saree_id}", json={"status": "sold_out"}, headers=headers)
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "sold_out"
    
    # 9. Admin deletes the saree
    delete_res = await client.delete(f"/api/v1/sarees/{saree_id}", headers=headers)
    assert delete_res.status_code == 200
    
    # 10. Verify deletion
    final_res = await client.get(f"/api/v1/sarees/{saree_id}")
    assert final_res.status_code == 404
