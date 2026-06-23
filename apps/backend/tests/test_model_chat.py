from types import SimpleNamespace

from fastapi.testclient import TestClient

from yontai.api.routes import models as model_routes
from yontai.main import app


class FakeModelRegistryService:
    model = SimpleNamespace(
        id="model-1",
        name="Görünen Model Adı",
        provider_id="llama3.2:latest",
        source="ollama",
    )

    def __init__(self, _db: object) -> None:
        pass

    def get_model(self, _model_id: str) -> SimpleNamespace:
        return self.model


class FakeOllamaClient:
    called_model: str | None = None

    async def __aenter__(self) -> "FakeOllamaClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def health_check(self) -> bool:
        return True

    async def chat(self, model: str, messages: list[dict[str, str]]) -> dict[str, object]:
        self.__class__.called_model = model
        return {"message": {"content": f"Yanıt: {messages[0]['content']}"}}


def test_chat_uses_ollama_provider_id(monkeypatch) -> None:
    monkeypatch.setattr(model_routes, "ModelRegistryService", FakeModelRegistryService)
    monkeypatch.setattr(model_routes, "OllamaClient", FakeOllamaClient)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/models/chat",
            json={"model_id": "model-1", "prompt": "Merhaba"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "response": "Yanıt: Merhaba",
        "model_id": "model-1",
        "model_name": "llama3.2:latest",
    }
    assert FakeOllamaClient.called_model == "llama3.2:latest"


def test_chat_rejects_non_ollama_models(monkeypatch) -> None:
    class NonOllamaService(FakeModelRegistryService):
        model = SimpleNamespace(
            id="model-2",
            name="Yerel Model",
            provider_id=None,
            source="local",
        )

    monkeypatch.setattr(model_routes, "ModelRegistryService", NonOllamaService)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/models/chat",
            json={"model_id": "model-2", "prompt": "Merhaba"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Chat şu anda yalnızca Ollama modelleriyle destekleniyor."
