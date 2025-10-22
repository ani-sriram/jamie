import pytest
from fastapi.testclient import TestClient
from src.web.api import app

client = TestClient(app)

class TestAPI:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()
    
    def test_chat_endpoint(self):
        response = client.post(
            "/chat/test_user",
            json={"message": "I want Italian food"}
        )
        assert response.status_code == 200
        assert "response" in response.json()
        assert "user_id" in response.json()
    
    def test_empty_message(self):
        response = client.post(
            "/chat/test_user",
            json={"message": ""}
        )
        assert response.status_code == 400
    
    def test_clear_session(self):
        response = client.delete("/chat/test_user")
        assert response.status_code == 200

if __name__ == "__main__":
    pytest.main([__file__])
