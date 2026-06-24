"""MLX model provider integration module.

MLX modellerini yönetmek için birleşik API. Model keşfi, yükleme/boşaltma,
HuggingFace'den MLX'e dönüşüm ve LRU önbellek yönetimi sağlar.
M1 Pro 16 GB için optimize edilmiştir.
"""

from __future__ import annotations

import asyncio
import gc
import json
import logging
import shutil
import subprocess
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from yontai.core.paths import storage_path
from yontai.runtime.mlx_runtime import MLXRuntime, MLXRuntimeError, get_mlx_runtime

logger = logging.getLogger(__name__)


class MLXConnectionError(Exception):
    """MLX bağlantı/konfigürasyon hatası."""


class MLXModelError(Exception):
    """MLX model işlem hatası."""


@dataclass
class MLXModelInfo:
    """MLX model bilgisi."""

    model_id: str
    path: str
    name: str
    parameter_count: int | None = None
    quantization: str | None = None
    context_length: int = 8192
    size_bytes: int | None = None
    format: str = "mlx"
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelCache:
    """LRU model önbelleği - 16 GB RAM için optimize.

    Modelleri LRU (Least Recently Used) stratejisi ile önbellekte tutar.
    Bellek limiti aşıldığında en az kullanılan modeli otomatik boşaltır.
    """

    def __init__(self, max_memory_mb: int = 14000) -> None:
        self._max_memory_mb = max_memory_mb
        self._cache: OrderedDict[str, MLXRuntime] = OrderedDict()
        self._sizes: dict[str, int] = {}  # model_id -> estimated_mb
        self._lock = asyncio.Lock()
        self._current_memory_mb = 0

    @property
    def current_memory_mb(self) -> int:
        return self._current_memory_mb

    @property
    def max_memory_mb(self) -> int:
        return self._max_memory_mb

    @property
    def loaded_models(self) -> list[str]:
        return list(self._cache.keys())

    async def get(self, model_id: str) -> MLXRuntime | None:
        """Model önbellekten al, LRU pozisyonunu güncelle."""
        async with self._lock:
            if model_id not in self._cache:
                return None
            self._cache.move_to_end(model_id)
            return self._cache[model_id]

    async def put(self, model_id: str, runtime: MLXRuntime, estimated_mb: int = 0) -> None:
        """Modeli önbelleğe ekle, gerekirse LRU boşaltma yap."""
        async with self._lock:
            if model_id in self._cache:
                self._cache.move_to_end(model_id)
                return

            # Bellek limitini kontrol et
            self._ensure_space(estimated_mb)

            self._cache[model_id] = runtime
            self._sizes[model_id] = estimated_mb
            self._current_memory_mb += estimated_mb
            logger.info(
                "Model önbelleğe alındı: %s (%d MB) [toplam: %d MB]",
                model_id, estimated_mb, self._current_memory_mb,
            )

    async def remove(self, model_id: str) -> None:
        """Modeli önbellekten çıkar ve belleği boşalt."""
        async with self._lock:
            runtime = self._cache.pop(model_id, None)
            size = self._sizes.pop(model_id, 0)
            if runtime:
                self._unload_sync(runtime)
            self._current_memory_mb -= size
            logger.info("Model önbellekten çıkarıldı: %s", model_id)

    async def clear(self) -> None:
        """Tüm önbelleği temizle."""
        async with self._lock:
            for _model_id, runtime in list(self._cache.items()):
                self._unload_sync(runtime)
            self._cache.clear()
            self._sizes.clear()
            self._current_memory_mb = 0
            gc.collect()
            logger.info("Model önbelleği temizlendi.")

    def _ensure_space(self, needed_mb: int) -> None:
        """Gerekli alanı sağlamak için LRU modelleri boşalt."""
        while (self._current_memory_mb + needed_mb > self._max_memory_mb
               and self._cache):
            # En az kullanılan modeli bul (ilk sıradaki)
            lru_id, lru_runtime = next(iter(self._cache.items()))
            self._unload_sync(lru_runtime)
            lru_size = self._sizes.pop(lru_id, 0)
            del self._cache[lru_id]
            self._current_memory_mb -= lru_size
            logger.info("LRU model boşaltıldı: %s (%d MB)", lru_id, lru_size)

    def _unload_sync(self, runtime: MLXRuntime) -> None:
        """Runtime'ı senkron boşalt (event loop'u bloke etmez)."""
        try:
            runtime.unload_model()
        except Exception as exc:
            logger.warning("Model boşaltma hatası: %s", exc)

    def estimate_model_size(self, model_path: str | Path) -> int:
        """Model dosyalarının yaklaşık boyutunu MB cinsinden hesapla.

        Args:
            model_path: Model yolu

        Returns:
            Tahmini MB
        """
        path = Path(model_path)
        if not path.exists():
            return 1000  # Varsayılan 1 GB

        total_bytes = 0
        if path.is_file():
            total_bytes = path.stat().st_size
        else:
            for f in path.rglob("*.safetensors"):
                total_bytes += f.stat().st_size
            for f in path.rglob("*.bin"):
                total_bytes += f.stat().st_size
            for f in path.rglob("*.gguf"):
                total_bytes += f.stat().st_size

        # Overhead: model yükleme ek yükü ~500MB
        return int(total_bytes / (1024 * 1024) * 1.25 + 500)


class MLXProviderClient:
    """MLX model sağlayıcı istemcisi.

    OllamaClient ile benzer API pattern'ini kullanır.
    """

    def __init__(self) -> None:
        self._cache = ModelCache()
        self._runtimes: dict[str, MLXRuntime] = {}
        self._models_dir = Path(storage_path("models")) / "mlx"
        self._models_dir.mkdir(parents=True, exist_ok=True)

    async def __aenter__(self) -> MLXProviderClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._cache.clear()
        for runtime in self._runtimes.values():
            try:
                runtime.unload_model()
            except Exception:
                pass
        self._runtimes.clear()

    async def health_check(self) -> bool:
        """MLX runtime'ın kullanılabilir olduğunu kontrol et."""
        try:
            runtime = get_mlx_runtime()
            return runtime is not None
        except MLXRuntimeError:
            return False

    async def list_models(self) -> list[MLXModelInfo]:
        """Yerel MLX modellerini listele.

        Returns:
            MLX model bilgileri listesi
        """
        models: list[MLXModelInfo] = []

        if not self._models_dir.exists():
            return models

        for item in sorted(self._models_dir.iterdir()):
            if not item.is_dir():
                continue

            # config.json'dan metadata oku
            config = {}
            config_path = item / "config.json"
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        config = json.load(f)
                except (json.JSONDecodeError, OSError):
                    pass

            # Model bilgilerini çıkar
            model_id = item.name.replace("--", "/")
            param_count = config.get("num_parameters")
            if param_count is None:
                param_count = self._estimate_params_from_name(model_id)

            ctx_length = config.get(
                "max_position_embeddings",
                config.get("n_ctx", 8192),
            )

            models.append(
                MLXModelInfo(
                    model_id=model_id,
                    path=str(item),
                    name=item.name,
                    parameter_count=int(param_count) if param_count else None,
                    quantization=self._detect_quantization(item),
                    context_length=int(ctx_length) if ctx_length else 8192,
                    size_bytes=self._get_dir_size(item),
                    metadata=config,
                )
            )

        return models

    async def show_model_info(self, model_path: str) -> MLXModelInfo:
        """Belirli bir model hakkında detaylı bilgi al.

        Args:
            model_path: Model yolu veya HF ID

        Returns:
            MLXModelInfo
        """
        path = self._resolve_model_path(model_path)
        if not path.exists():
            raise MLXModelError(f"Model bulunamadı: {model_path}")

        runtime = MLXRuntime()
        info = runtime.get_model_info(path)

        return MLXModelInfo(
            model_id=model_path,
            path=str(path),
            name=path.stem or path.name,
            parameter_count=info.parameter_count,
            quantization=info.quantization,
            context_length=info.context_length,
            size_bytes=self._get_dir_size(path),
            metadata=info.metadata,
        )

    async def load_model(self, model_path: str) -> MLXRuntime:
        """Modeli belleğe yükle (önbellek üzerinden).

        Args:
            model_path: Model yolu

        Returns:
            MLXRuntime instance
        """
        path = self._resolve_model_path(model_path)
        model_id = str(path)

        # Önbellekte varsa direkt döndür
        cached = await self._cache.get(model_id)
        if cached:
            return cached

        # Yeni runtime oluştur
        runtime = MLXRuntime()
        runtime.load_model(path)

        # Önbelleğe ekle
        estimated_mb = self._cache.estimate_model_size(path)
        await self._cache.put(model_id, runtime, estimated_mb)
        self._runtimes[model_id] = runtime

        return runtime

    async def unload_model(self, model_path: str) -> None:
        """Modeli bellekten boşalt."""
        path = self._resolve_model_path(model_path)
        model_id = str(path)
        await self._cache.remove(model_id)
        self._runtimes.pop(model_id, None)

    async def unload_all(self) -> None:
        """Tüm modelleri boşalt."""
        await self._cache.clear()
        self._runtimes.clear()

    async def convert_hf_to_mlx(
        self,
        hf_model_id: str,
        quantization: str | None = None,
        force: bool = False,
    ) -> Path:
        """HuggingFace modelini MLX formatına dönüştür.

        Args:
            hf_model_id: HuggingFace model ID
            quantization: Quantization seviyesi (örn: "q4", "q8")
            force: Varolan dönüşümü zorla yenile

        Returns:
            Dönüştürülen modelin yolu
        """
        output_dir = self._models_dir / hf_model_id.replace("/", "--")

        if output_dir.exists() and not force:
            logger.info("MLX modeli zaten mevcut: %s", output_dir)
            return output_dir

        logger.info("HF modeli MLX'e dönüştürülüyor: %s -> %s", hf_model_id, output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            cmd = [
                "python3", "-m", "mlx_lm.convert",
                "--hf-path", hf_model_id,
                "--mlx-path", str(output_dir),
            ]
            if quantization:
                bits = quantization.replace("q", "").replace("Q", "")
                cmd.extend(["--q-bits", bits])

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 dakika timeout
            )
            logger.info("MLX dönüşümü tamamlandı: %s", result.stdout[-200:])

        except subprocess.CalledProcessError as exc:
            error_msg = exc.stderr[-500:] if exc.stderr else str(exc)
            logger.error("MLX dönüşüm hatası: %s", error_msg)
            # Başarısız dönüşümü temizle
            if output_dir.exists():
                shutil.rmtree(output_dir)
            raise MLXModelError(f"MLX dönüşümü başarısız: {error_msg}") from exc
        except subprocess.TimeoutExpired:
            raise MLXModelError("MLX dönüşümü zaman aşımı (30 dk).") from None

        return output_dir

    async def discover_models(self) -> list[MLXModelInfo]:
        """Tüm kaynaklardan MLX modellerini keşfet.

        Yerel dizin + HuggingFace'de MLX formatındaki modelleri tara.

        Returns:
            MLX model listesi
        """
        models = await self.list_models()

        # HuggingFace'de yaygın MLX modellerini de ekle
        common_mlx_models = [
            "mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
            "mlx-community/CodeQwen-7B-Chat-4bit",
            "mlx-community/StarCoder2-3B-4bit",
            "mlx-community/Mistral-7B-Instruct-v0.3-4bit",
            "mlx-community/Llama-3.2-3B-Instruct-4bit",
            "mlx-community/Phi-3-mini-4k-instruct-4bit",
            "mlx-community/gemma-2-2b-it-4bit",
        ]

        for hf_id in common_mlx_models:
            # Yerelde var mı kontrol et
            local_path = self._models_dir / hf_id.replace("/", "--")
            if local_path.exists():
                continue  # Zaten listede

            models.append(
                MLXModelInfo(
                    model_id=hf_id,
                    path=f"hf://{hf_id}",
                    name=hf_id.split("/")[-1],
                    parameter_count=self._estimate_params_from_name(hf_id),
                    format="huggingface_mlx",
                )
            )

        return models

    def _resolve_model_path(self, model_path: str) -> Path:
        """Model yolunu çözümle (kısa ID veya tam yol)."""
        path = Path(model_path)
        if path.exists():
            return path

        # models/mlx/ altında ara
        alt_path = self._models_dir / model_path.replace("/", "--")
        if alt_path.exists():
            return alt_path

        # Kısa isimle ara
        for item in self._models_dir.iterdir():
            if item.is_dir() and item.name.lower() == model_path.lower():
                return item

        return path

    def _detect_quantization(self, model_dir: Path) -> str | None:
        """Model dizinindeki quantization seviyesini tespit et."""
        name_lower = model_dir.name.lower()
        for marker in ["q4", "q8", "q2", "q3", "q5", "q6", "bf16", "fp16"]:
            if marker in name_lower:
                return marker.upper()
        # Dosya isimlerinde de ara
        for f in model_dir.iterdir():
            fname = f.name.lower()
            if "q4" in fname or "int4" in fname:
                return "Q4"
            if "q8" in fname or "int8" in fname:
                return "Q8"
        return None

    def _estimate_params_from_name(self, name: str) -> int | None:
        """Model adından parametre sayısını tahmin et."""
        name_lower = name.lower().replace("-", " ").replace("_", " ")
        import re
        for pattern, multiplier in [
            (r"(\d+(?:\.\d+)?)\s*b", 1_000_000_000),
            (r"(\d+(?:\.\d+)?)\s*m", 1_000_000),
        ]:
            match = re.search(pattern, name_lower)
            if match:
                return int(float(match.group(1)) * multiplier)
        return None

    @staticmethod
    def _get_dir_size(path: Path) -> int:
        """Dizin boyutunu byte olarak hesapla."""
        if path.is_file():
            return path.stat().st_size
        total = 0
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
        return total