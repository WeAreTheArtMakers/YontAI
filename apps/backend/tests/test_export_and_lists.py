from fastapi.testclient import TestClient

from yontai.db.models import Model
from yontai.db.session import SessionLocal
from yontai.main import app
from yontai.repositories.models import ModelRepository


def test_export_job_uses_registered_model_path(tmp_path) -> None:
    model_file = tmp_path / "demo.gguf"
    model_file.write_bytes(b"GGUF")

    with SessionLocal() as db:
        model = ModelRepository(db).add(
            Model(
                name="demo",
                source="local",
                path=str(model_file),
            )
        )
        model_id = model.id

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/exports/model",
            json={
                "model_id": model_id,
                "format": "gguf",
                "output_name": "demo-export",
                "quantization": "Q4_K_M",
            },
        )
        assert response.status_code == 201
        payload = response.json()["payload"]
        assert payload["model_path"] == str(model_file)


def test_list_exports_and_deployments_include_jobs() -> None:
    with TestClient(app) as client:
        export_response = client.post(
            "/api/v1/exports/model",
            json={
                "model_id": "missing-model",
                "format": "gguf",
                "output_name": "x",
            },
        )
        assert export_response.status_code == 404

        exports = client.get("/api/v1/exports")
        deployments = client.get("/api/v1/deployments")
        assert exports.status_code == 200
        assert deployments.status_code == 200
        assert isinstance(exports.json(), list)
        assert isinstance(deployments.json(), list)
