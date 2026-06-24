"""Multi-Model Orchestrator - Çoklu Model Yönetim Sistemi.

Ollama, MLX ve llama.cpp gibi farklı backend'leri tek bir arayüz altında
yönetir. Katmanlı model stratejisi uygular:
- Hızlı katman (1-3B): FIM/tamamlama için sürekli sıcak
- Akıllı katman (7-16B): Sohbet/refactoring için isteğe bağlı yükleme

M1 Pro 16 GB için optimize edilmiştir.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from yontai.core.hardware import detect_hardware_profile

logger = logging.getLogger(__name__)


class ModelBackend(StrEnum):
    """Desteklenen model backend'leri."""
    OLLAMA = "ollama"
    MLX = "mlx"
    LLAMACPP = "llamacpp"
    TRANSFORMERS = "transformers"
    UNKNOWN = "unknown"


class ModelTier(StrEnum):
    """Model katmanları."""
    FAST = "fast"        # 1-3B: FIM, hızlı tamamlama
    SMART = "smart"      # 7-16B: Sohbet, refactoring
    LARGE = "large"      # >16B: Derin analiz (dış kaynak)


@dataclass
class TieredModelConfig:
    """Katmanlı model yapılandırması."""
    fast_model: str = "deepseek-coder-1.3b-instruct"     # FIM için
    smart_model: str = "deepseek-coder-6.7b-instruct"    # Sohbet için
    large_model: str = "deepseek-coder-33b-instruct"     # Derin analiz
    fast_backend: ModelBackend = ModelBackend.MLX
    smart_backend: ModelBackend = ModelBackend.MLX
    large_backend: ModelBackend = ModelBackend.OLLAMA
    fast_max_tokens: int = 2048
    smart_max_tokens: int = 4096
    large_max_tokens: int = 8192
    fast_temperature: float = 0.1    # Düşük sıcaklık (kesin)
    smart_temperature: float = 0.3   # Orta sıcaklık (yaratıcı)
    large_temperature: float = 0.5   # Yüksek sıcaklık (analiz)


@dataclass
class OrchestratorStats:
    """Orkestratör istatistikleri."""
    total_requests: int = 0
    fast_requests: int = 0
    smart_requests: int = 0
    large_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: int = 0
    avg_latency_fast_ms: float = 0.0
    avg_latency_smart_ms: float = 0.0
    current_memory_mb: int = 0
    max_memory_mb: int = 14000


class ModelSession:
    """Model oturumu - context manager ile geçici model yükleme.

    Kullanım:
        async with orchestrator.session("smart") as runtime:
            result = runtime.generate("merhaba")
    """

    def __init__(
        self,
        orchestrator: ModelOrchestrator,
        tier: ModelTier | str,
        model_override: str | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._tier = ModelTier(tier) if isinstance(tier, str) else tier
        self._model_override = model_override
        self._runtime: Any = None

    async def __aenter__(self) -> Any:
        self._runtime = await self._orchestrator._load_for_tier(
            self._tier,
            self._model_override,
        )
        return self._runtime

    async def __aexit__(self, *_: object) -> None:
        if self._runtime and not self._model_override:
            await self._orchestrator._maybe_unload(self._tier)
        self._runtime = None


class ModelOrchestrator:
    """Ana model orkestratörü.

    Farklı backend'ler arasında otomatik geçiş yapar, modelleri
    önbellekte tutar ve bellek yönetimini sağlar.
    """

    def __init__(self, config: TieredModelConfig | None = None) -> None:
        self.config = config or TieredModelConfig()
        self.stats = OrchestratorStats()

        # Backend'ler
        self._mlx_provider: Any = None
        self._ollama_client: Any = None
        self._fast_loaded = False
        self._smart_loaded = False

        # Aktif runtime
        self._active_runtime: Any = None
        self._active_backend: ModelBackend | None = None

        # Hardware profili
        self._hw_profile = detect_hardware_profile()

    async def initialize(self) -> None:
        """Orkestratörü başlat - backend'leri hazırla."""
        logger.info("ModelOrchestrator başlatılıyor...")

        # MLX provider'ı başlat
        try:
            from yontai.integrations.mlx_provider import MLXProviderClient
            self._mlx_provider = MLXProviderClient()
            logger.info("MLX provider hazır.")
        except Exception as exc:
            logger.warning("MLX provider başlatılamadı: %s", exc)

        # Ollama client'ı başlat
        try:
            from yontai.integrations.ollama import OllamaClient
            self._ollama_client = OllamaClient()
            logger.info("Ollama client hazır.")
        except Exception as exc:
            logger.warning("Ollama client başlatılamadı: %s", exc)

        # Hızlı modeli önceden yükle (FIM için)
        if self._mlx_provider and self.config.fast_backend == ModelBackend.MLX:
            try:
                await self._load_for_tier(ModelTier.FAST)
                self._fast_loaded = True
                logger.info("Hızlı model ön yüklendi: %s", self.config.fast_model)
            except Exception as exc:
                logger.warning("Hızlı model yüklenemedi: %s", exc)

        logger.info("ModelOrchestrator hazır.")

    async def shutdown(self) -> None:
        """Orkestratörü kapat - tüm modelleri boşalt."""
        if self._mlx_provider:
            try:
                await self._mlx_provider.unload_all()
            except Exception:
                pass
        self._fast_loaded = False
        self._smart_loaded = False
        self._active_runtime = None
        logger.info("ModelOrchestrator kapatıldı.")

    async def complete(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        stream: bool = False,
    ) -> str | Any:
        """Kod tamamlama (FIM için hızlı model kullanılır).

        Args:
            prompt: Prompt metni
            max_tokens: Maksimum token
            temperature: Sıcaklık
            stream: Stream modu

        Returns:
            Tamamlanan metin
        """
        self.stats.total_requests += 1
        self.stats.fast_requests += 1

        runtime = await self._load_for_tier(ModelTier.FAST)
        if not runtime:
            raise RuntimeError("Hiçbir backend kullanılamıyor.")

        result = runtime.generate(
            prompt=prompt,
            max_tokens=max_tokens or self.config.fast_max_tokens,
            temperature=temperature if temperature is not None else self.config.fast_temperature,
            stream=stream,
        )

        await self._maybe_unload(ModelTier.FAST)
        return result

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        stream: bool = False,
    ) -> str | Any:
        """Sohbet tamamlama (akıllı model kullanılır).

        Args:
            messages: Mesaj listesi [{"role": "user", "content": "..."}]
            max_tokens: Maksimum token
            temperature: Sıcaklık
            stream: Stream modu

        Returns:
            Yanıt metni
        """
        self.stats.total_requests += 1
        self.stats.smart_requests += 1

        runtime = await self._load_for_tier(ModelTier.SMART)
        if not runtime:
            raise RuntimeError("Hiçbir backend kullanılamıyor.")

        # Prompt'a çevir
        prompt = self._messages_to_prompt(messages)

        result = runtime.generate(
            prompt=prompt,
            max_tokens=max_tokens or self.config.smart_max_tokens,
            temperature=temperature if temperature is not None else self.config.smart_temperature,
            stream=stream,
        )

        await self._maybe_unload(ModelTier.SMART)
        return result

    async def fill_in_middle(
        self,
        prefix: str,
        suffix: str,
        *,
        max_tokens: int = 512,
    ) -> str:
        """Fill-in-the-Middle tamamlama.

        Args:
            prefix: İmleç öncesi kod
            suffix: İmleç sonrası kod
            max_tokens: Maksimum token

        Returns:
            Ortaya üretilen kod
        """
        self.stats.total_requests += 1
        self.stats.fast_requests += 1

        runtime = await self._load_for_tier(ModelTier.FAST)
        if not runtime:
            raise RuntimeError("Hiçbir backend kullanılamıyor.")

        # MLX runtime FIM destekliyor
        if hasattr(runtime, "fill_in_middle"):
            result = runtime.fill_in_middle(
                prefix=prefix,
                suffix=suffix,
                max_tokens=max_tokens,
            )
        else:
            # Ollama için manuel FIM prompt
            fim_prompt = (
                f"<|fim_begin|>{prefix}"
                f"<|fim_hole|>{suffix}"
                f"<|fim_end|>"
            )
            result = runtime.generate(
                prompt=fim_prompt,
                max_tokens=max_tokens,
                temperature=0.1,
                stop_strings=["<|fim_end|>", "<|endoftext|>"],
            )

        await self._maybe_unload(ModelTier.FAST)
        return str(result)

    @asynccontextmanager
    async def session(
        self,
        tier: ModelTier | str = ModelTier.SMART,
        model_override: str | None = None,
    ) -> AsyncIterator[Any]:
        """Model oturumu başlat.

        Kullanım:
            async with orchestrator.session("fast") as runtime:
                result = await runtime.generate("kod")
        """
        session = ModelSession(self, tier, model_override)
        async with session as runtime:
            yield runtime

    async def _load_for_tier(
        self,
        tier: ModelTier,
        model_override: str | None = None,
    ) -> Any:
        """Belirtilen katman için model yükle."""
        if tier == ModelTier.FAST:
            model_name = model_override or self.config.fast_model
            backend = self.config.fast_backend
        elif tier == ModelTier.SMART:
            model_name = model_override or self.config.smart_model
            backend = self.config.smart_backend
        else:
            model_name = model_override or self.config.large_model
            backend = self.config.large_backend

        # Önbellekte var mı?
        if self._active_runtime and self._active_backend == backend:
            if hasattr(self._active_runtime, "is_loaded") and self._active_runtime.is_loaded:
                self.stats.cache_hits += 1
                return self._active_runtime

        self.stats.cache_misses += 1

        # Backend'e göre yükle
        try:
            if backend == ModelBackend.MLX and self._mlx_provider:
                runtime = await self._mlx_provider.load_model(model_name)
                self._active_runtime = runtime
                self._active_backend = backend
                return runtime

            elif backend == ModelBackend.OLLAMA and self._ollama_client:
                # Ollama için doğrudan client döndür
                self._active_runtime = self._ollama_client
                self._active_backend = backend
                return self._ollama_client

            else:
                raise RuntimeError(f"Backend kullanılamıyor: {backend}")

        except Exception as exc:
            self.stats.errors += 1
            logger.error("Model yüklenemedi (%s/%s): %s", backend, model_name, exc)
            raise

    async def _maybe_unload(self, tier: ModelTier) -> None:
        """Gerekirse modeli boşalt.

        Hızlı model her zaman sıcak kalır (FIM için).
        Akıllı model isteğe bağlı boşaltılır.
        """
        if tier == ModelTier.FAST:
            # Hızlı modeli sıcak tut
            return

        if tier == ModelTier.SMART:
            # Bellek durumuna göre boşalt
            if self._mlx_provider and self._mlx_provider._cache:
                memory_pct = (
                    self._mlx_provider._cache.current_memory_mb
                    / self._mlx_provider._cache.max_memory_mb
                )
                if memory_pct > 0.8:  # %80 üzerinde
                    await self._mlx_provider.unload_all()
                    self._active_runtime = None
                    self._active_backend = None
                    logger.info("Bellek optimizasyonu: tüm modeller boşaltıldı.")

    def _messages_to_prompt(self, messages: list[dict[str, str]]) -> str:
        """Mesaj listesini prompt string'ine çevir."""
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"<|system|>\n{content}\n")
            elif role == "user":
                parts.append(f"<|user|>\n{content}\n")
            elif role == "assistant":
                parts.append(f"<|assistant|>\n{content}\n")
        parts.append("<|assistant|>\n")
        return "".join(parts)

    def get_stats(self) -> dict[str, Any]:
        """Orkestratör istatistiklerini döndür."""
        memory_info = {}
        if self._mlx_provider and hasattr(self._mlx_provider, "_cache"):
            cache = self._mlx_provider._cache
            memory_info = {
                "current_memory_mb": cache.current_memory_mb,
                "max_memory_mb": cache.max_memory_mb,
                "loaded_models": cache.loaded_models,
            }

        return {
            "total_requests": self.stats.total_requests,
            "fast_requests": self.stats.fast_requests,
            "smart_requests": self.stats.smart_requests,
            "large_requests": self.stats.large_requests,
            "cache_hits": self.stats.cache_hits,
            "cache_misses": self.stats.cache_misses,
            "errors": self.stats.errors,
            "memory": memory_info,
            "config": {
                "fast_model": self.config.fast_model,
                "smart_model": self.config.smart_model,
                "fast_backend": self.config.fast_backend,
                "smart_backend": self.config.smart_backend,
            },
            "hardware": self._hw_profile,
        }