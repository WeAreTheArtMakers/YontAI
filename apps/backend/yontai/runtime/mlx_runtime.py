"""MLX runtime for Apple Silicon (M1/M2/M3/M4) optimized model inference.

MLX, Apple Silicon için özel olarak optimize edilmiş bir makine öğrenimi
framework'üdür. Bu modül, MLX formatındaki modelleri yüklemek ve çalıştırmak
için gerekli altyapıyı sağlar.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# MLX kullanılabilir mi kontrol et
try:
    import mlx.core as mx
    from mlx_lm import generate, load
    from mlx_lm.sample_utils import make_sampler

    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False
    logger.warning("MLX kütüphanesi bulunamadı. MLX runtime devre dışı.")

# M1 Pro 16 GB için optimize edilmiş varsayılan yapılandırma
MLX_DEFAULT_CONFIG = {
    "max_tokens": 2048,
    "temperature": 0.2,
    "top_p": 0.9,
    "top_k": 40,
    "repetition_penalty": 1.05,
    "stop_strings": ["<|fim_end|>", "<|endoftext|>", "<|im_end|>"],
}


@dataclass
class MLXModelInfo:
    """MLX modeli hakkında bilgiler."""

    model_path: str
    model_type: str = "mlx"
    parameter_count: int | None = None
    quantization: str | None = None
    context_length: int = 8192
    dtype: str = "float16"
    metadata: dict[str, Any] = field(default_factory=dict)


class MLXRuntimeError(Exception):
    """MLX runtime ile ilgili hatalar."""


class MLXRuntime:
    """MLX model çalıştırma runtime'ı.

    Apple Silicon üzerinde MLX formatındaki modelleri yükler ve çalıştırır.
    """

    def __init__(self) -> None:
        if not MLX_AVAILABLE:
            raise MLXRuntimeError(
                "MLX kütüphanesi kurulu değil. Lütfen 'pip install mlx mlx-lm' komutunu çalıştırın."
            )
        self._model = None
        self._tokenizer = None
        self._model_path: str | None = None
        self._is_loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def load_model(self, model_path: str | Path) -> None:
        """MLX modelini belleğe yükle.

        Args:
            model_path: MLX formatındaki modelin yolu (yerel dosya veya HF repo ID)
        """
        try:
            logger.info("MLX modeli yükleniyor: %s", model_path)
            path = str(model_path)
            self._model, self._tokenizer = load(path)
            self._model_path = path
            self._is_loaded = True
            logger.info("MLX modeli başarıyla yüklendi: %s", path)
        except Exception as exc:
            self._is_loaded = False
            raise MLXRuntimeError(f"MLX modeli yüklenemedi: {exc}") from exc

    def unload_model(self) -> None:
        """Modeli bellekten boşalt."""
        self._model = None
        self._tokenizer = None
        self._is_loaded = False
        self._model_path = None
        if MLX_AVAILABLE:
            import gc
            gc.collect()
            try:
                mx.clear_cache()
            except Exception:
                pass
        logger.info("MLX modeli bellekten boşaltıldı.")

    def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.2,
        top_p: float = 0.9,
        top_k: int = 40,
        repetition_penalty: float = 1.05,
        stop_strings: list[str] | None = None,
        stream: bool = False,
    ) -> str | Any:
        """Metin üretimi yap.

        Args:
            prompt: Giriş metni
            max_tokens: Maksimum token sayısı
            temperature: Sıcaklık parametresi (0 = deterministik)
            top_p: Nucleus sampling parametresi
            top_k: Top-K sampling parametresi
            repetition_penalty: Tekrar cezası
            stop_strings: Durma stringleri
            stream: Stream modu (True ise generator döner)

        Returns:
            Üretilen metin veya stream generator
        """
        if not self._is_loaded or self._model is None:
            raise MLXRuntimeError("Model yüklenmemiş. Önce load_model() çağırın.")

        try:
            stop_strings = stop_strings or MLX_DEFAULT_CONFIG.get("stop_strings", [])

            if stream:
                return self._stream_generate(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    repetition_penalty=repetition_penalty,
                    stop_strings=stop_strings,
                )

            sampler = make_sampler(
                temp=temperature,
                top_p=top_p,
                top_k=top_k,
            )

            response = generate(
                self._model,
                self._tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
                sampler=sampler,
                repetition_penalty=repetition_penalty,
                stop_strings=stop_strings or [],
            )

            return str(response)

        except Exception as exc:
            raise MLXRuntimeError(f"Metin üretimi başarısız: {exc}") from exc

    def _stream_generate(
        self,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float,
        top_p: float,
        top_k: int,
        repetition_penalty: float,
        stop_strings: list[str],
    ) -> Any:
        """Stream modunda metin üretimi."""
        try:
            sampler = make_sampler(
                temp=temperature,
                top_p=top_p,
                top_k=top_k,
            )

            return generate(
                self._model,
                self._tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
                sampler=sampler,
                repetition_penalty=repetition_penalty,
                stop_strings=stop_strings or [],
                stream=True,
            )

        except Exception as exc:
            raise MLXRuntimeError(f"Stream üretimi başarısız: {exc}") from exc

    def fill_in_middle(
        self,
        prefix: str,
        suffix: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.1,
        top_p: float = 0.9,
        top_k: int = 40,
    ) -> str:
        """Fill-in-the-Middle (FIM) tamamlama.

        DeepSeek-Coder FIM formatını kullanır:
        <|fim_begin|>{prefix}<|fim_hole|>{suffix}<|fim_end|>

        Args:
            prefix: İmleç öncesi kod
            suffix: İmleç sonrası kod
            max_tokens: Maksimum üretilecek token
            temperature: Düşük sıcaklık (kesin tamamlama için)

        Returns:
            Ortaya (middle) üretilen kod
        """
        fim_prompt = (
            f"<|fim_begin|>{prefix}"
            f"<|fim_hole|>{suffix}"
            f"<|fim_end|>"
        )

        result = self.generate(
            prompt=fim_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repetition_penalty=1.0,
            stop_strings=["<|fim_end|>", "<|endoftext|>"],
        )

        if isinstance(result, str):
            return result.strip()
        return str(result)

    def get_model_info(self, model_path: str | Path | None = None) -> MLXModelInfo:
        """Model hakkında metadata bilgisi döndür.

        Args:
            model_path: Model yolu (None ise yüklenmiş model kullanılır)

        Returns:
            MLXModelInfo: Model bilgileri
        """
        path = model_path or self._model_path
        if not path:
            raise MLXRuntimeError("Model yolu belirtilmedi.")

        path = str(path)
        metadata: dict[str, Any] = {}

        # config.json'dan metadata oku
        config_path = Path(path) / "config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                metadata = config if isinstance(config, dict) else {}
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("config.json okunamadı: %s", exc)

        # Parametre sayısını tahmin et
        param_count = metadata.get("num_parameters")
        if param_count is None and "hidden_size" in metadata:
            hidden = int(metadata["hidden_size"])
            layers = int(metadata.get("num_hidden_layers", 32))
            vocab = int(metadata.get("vocab_size", 32000))
            intermediate = int(metadata.get("intermediate_size", hidden * 4))
            # MoE kontrolü
            num_experts = metadata.get("num_local_experts", 1)
            if isinstance(num_experts, int | float) and num_experts > 1:
                int(metadata.get("num_experts_per_tok", 2))
                param_count = (
                    (hidden * vocab * 2)  # embedding
                    + layers * (
                        4 * hidden * hidden  # attention
                        + num_experts * hidden * intermediate  # MoE FFN
                    )
                )
            else:
                param_count = (
                    (hidden * vocab * 2)  # embedding
                    + layers * (
                        4 * hidden * hidden  # attention
                        + 3 * hidden * intermediate  # FFN
                    )
                )

        # Quantization tespiti
        quantization = None
        q_str = path.lower()
        for marker in ["q4", "q8", "q2", "q3", "q5", "q6", "bf16", "fp16"]:
            if marker in q_str:
                quantization = marker.upper()
                break
        if quantization is None:
            for fname in os.listdir(path):
                if "q4" in fname.lower() or "int4" in fname.lower():
                    quantization = "Q4"
                    break
                if "q8" in fname.lower() or "int8" in fname.lower():
                    quantization = "Q8"
                    break

        # Context length
        ctx_length = metadata.get(
            "max_position_embeddings",
            metadata.get("n_ctx", metadata.get("context_length", 8192)),
        )

        # Dtype
        dtype = metadata.get("torch_dtype", metadata.get("dtype", "float16"))

        return MLXModelInfo(
            model_path=path,
            model_type="mlx",
            parameter_count=int(param_count) if param_count else None,
            quantization=quantization,
            context_length=int(ctx_length) if ctx_length else 8192,
            dtype=str(dtype),
            metadata=metadata,
        )

    def benchmark(
        self,
        prompt: str = "def fibonacci(n):",
        max_tokens: int = 128,
        warmup_runs: int = 2,
        num_runs: int = 5,
    ) -> dict[str, object]:
        """Model inference hızını test et.

        Args:
            prompt: Test prompt'u
            max_tokens: Üretilecek token sayısı
            warmup_runs: Isınma çalıştırma sayısı
            num_runs: Ölçüm çalıştırma sayısı

        Returns:
            dict: tokens_per_second, total_tokens, avg_latency_ms gibi metrikler
        """
        if not self._is_loaded:
            raise MLXRuntimeError("Önce bir model yükleyin.")

        # Isınma
        for _ in range(warmup_runs):
            self.generate(prompt=prompt, max_tokens=32, temperature=0.0)

        # Ölçüm
        latencies: list[float] = []
        total_tokens = 0

        for _ in range(num_runs):
            start = time.perf_counter()
            result = self.generate(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=0.0,
            )
            elapsed = time.perf_counter() - start

            if isinstance(result, str):
                token_count = len(result.split())
            else:
                token_count = max_tokens

            total_tokens += token_count
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        tokens_per_sec = total_tokens / sum(latencies)

        return {
            "tokens_per_second": round(tokens_per_sec, 2),
            "total_tokens_generated": total_tokens,
            "average_latency_ms": round(avg_latency * 1000, 2),
            "num_runs": num_runs,
            "max_tokens_per_run": max_tokens,
            "model_path": self._model_path,
        }

    @staticmethod
    def convert_to_mlx(
        hf_model_id: str,
        output_dir: str | Path | None = None,
        quantization: str | None = None,
    ) -> Path:
        """HuggingFace modelini MLX formatına dönüştür.

        Args:
            hf_model_id: HuggingFace model ID (ör: "deepseek-ai/deepseek-coder-1.3b-instruct")
            output_dir: Çıktı dizini (None = varsayılan models/ dizini)
            quantization: Quantization seviyesi (None = otomatik, "q4", "q8" vb.)

        Returns:
            Path: Dönüştürülen modelin yolu

        Raises:
            MLXRuntimeError: Dönüşüm başarısız olursa
        """
        from yontai.core.paths import storage_path

        if output_dir is None:
            output_dir = storage_path("models") / "mlx" / hf_model_id.replace("/", "--")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("HF modeli MLX'e dönüştürülüyor: %s -> %s", hf_model_id, output_dir)

        try:
            # mlx_lm.convert kullan

            cmd = [
                "python3", "-m", "mlx_lm.convert",
                "--hf-path", hf_model_id,
                "--mlx-path", str(output_dir),
            ]

            if quantization:
                cmd.extend(["--q_bits", quantization.replace("q", "")])

            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)

            logger.info("MLX dönüşümü tamamlandı: %s", output_dir)
            return output_dir

        except subprocess.CalledProcessError as exc:
            raise MLXRuntimeError(
                f"MLX dönüşümü başarısız: {exc.stderr}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise MLXRuntimeError("MLX dönüşümü zaman aşımı.") from exc
        except Exception as exc:
            raise MLXRuntimeError(f"MLX dönüşüm hatası: {exc}") from exc


def get_mlx_runtime() -> MLXRuntime | None:
    """MLX runtime singleton'ı döndür.

    Returns:
        MLXRuntime instance veya MLX yoksa None
    """
    if not MLX_AVAILABLE:
        return None
    try:
        return MLXRuntime()
    except MLXRuntimeError:
        return None