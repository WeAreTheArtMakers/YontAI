from fastapi.testclient import TestClient

from yontai.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
