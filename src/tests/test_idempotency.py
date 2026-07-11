import pytest
import json
from httpx import AsyncClient
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_idempotency_middleware_returns_cached_response(client: AsyncClient, mock_redis):
    # 1. Setup Redis mock to simulate a cached response for an idempotency key
    cached_response_payload = {
        "status_code": 200,
        "body": json.dumps({"status": "cached_ok", "payload": "duplicate_prevented"}),
        "headers": {"content-type": "application/json"}
    }
    
    # Configure redis get mock
    mock_redis.get = AsyncMock(return_value=json.dumps(cached_response_payload))
    
    headers = {"Idempotency-Key": "unique-uuid-key-value-1234"}
    
    # 2. Issue write request
    response = await client.post(
        "/api/v1/auth/register",
        json={},
        headers=headers
    )
    
    # 3. Assert cached response is returned directly, bypassing route logic
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cached_ok"
    assert data["payload"] == "duplicate_prevented"
    
    # Verify that get was called with the correct idempotency key
    mock_redis.get.assert_called_with("idempotency:unique-uuid-key-value-1234")
