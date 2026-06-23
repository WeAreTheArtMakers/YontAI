"""Ollama API integration for the local model runtime."""

from typing import Any

import httpx

from yontai.core.config import get_settings
from yontai.core.exceptions import OllamaConnectionError, OllamaModelError


class OllamaClient:
    """Async client for Ollama API."""

    def __init__(
        self,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_host).rstrip("/")
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=5.0)
        )
        self._owns_client = client is None

    async def __aenter__(self) -> "OllamaClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def _request_json(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            response = await self.client.request(method, f"{self.base_url}{path}", **kwargs)
            response.raise_for_status()
            data = response.json()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise OllamaConnectionError(
                "Ollama servisine bağlanılamadı. Ollama çalışıyor mu?"
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip() or exc.response.reason_phrase
            status_code = exc.response.status_code
            raise OllamaModelError(f"Ollama HTTP hatası ({status_code}): {detail}") from exc
        except httpx.HTTPError as exc:
            raise OllamaConnectionError(f"Ollama bağlantı hatası: {exc}") from exc
        except ValueError as exc:
            raise OllamaModelError("Ollama geçersiz JSON yanıtı döndürdü.") from exc

        if not isinstance(data, dict):
            raise OllamaModelError("Ollama beklenmeyen yanıt formatı döndürdü.")
        return data

    async def health_check(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            await self._request_json("GET", "/api/tags")
        except (OllamaConnectionError, OllamaModelError):
            return False
        return True

    async def list_models(self) -> list[dict[str, Any]]:
        """List all models available in Ollama."""
        data = await self._request_json("GET", "/api/tags")
        models = data.get("models", [])
        if not isinstance(models, list):
            raise OllamaModelError("Ollama model listesi beklenen formatta değil.")
        return models

    async def generate(
        self, model: str, prompt: str, stream: bool = False
    ) -> dict[str, Any]:
        """Generate text completion from a model."""
        return await self._request_json(
            "POST",
            "/api/generate",
            json={"model": model, "prompt": prompt, "stream": stream},
        )

    async def chat(
        self, model: str, messages: list[dict[str, str]], stream: bool = False
    ) -> dict[str, Any]:
        """Chat completion with conversation history."""
        return await self._request_json(
            "POST",
            "/api/chat",
            json={"model": model, "messages": messages, "stream": stream},
        )

    async def show_model_info(self, model: str) -> dict[str, Any]:
        """Get detailed information about a specific model."""
        return await self._request_json("POST", "/api/show", json={"name": model})
