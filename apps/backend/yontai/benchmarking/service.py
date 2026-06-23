import asyncio
import json
import time
import urllib.error
import urllib.request
from typing import Any

from yontai.core.config import get_settings

# Global lock to prevent concurrent Ollama requests locking up the PC
_ollama_lock = asyncio.Lock()


class BenchmarkService:
    def __init__(self) -> None:
        pass

    async def run_ollama_benchmark(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int = 128,
    ) -> dict[str, Any]:
        async with _ollama_lock:
            return await asyncio.to_thread(self._run_sync, model_name, prompt, max_tokens)

    def _run_sync(self, model_name: str, prompt: str, max_tokens: int) -> dict[str, Any]:
        settings = get_settings()
        url = f"{settings.ollama_host.rstrip('/')}/api/generate"
        payload = json.dumps(
            {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.7,
                },
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        start_time = time.time()
        try:
            # Increased timeout for loading large models
            with urllib.request.urlopen(req, timeout=300) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"model": model_name, "error": "Model bulunamadı (Ollama 404)."}
            return {"model": model_name, "error": f"Ollama HTTP Hatası: {exc.code}"}
        except urllib.error.URLError as exc:
            return {
                "model": model_name,
                "error": f"Ollama bağlantı hatası: çalışmıyor olabilir ({exc.reason}).",
            }
        except TimeoutError:
            return {
                "model": model_name,
                "error": "Zaman aşımı (timeout). Model yüklenmesi çok uzun sürmüş olabilir.",
            }
        except Exception as exc:
            return {"model": model_name, "error": f"Bilinmeyen hata: {exc}"}

        total_time_ms = (time.time() - start_time) * 1000

        # Ollama returns durations in nanoseconds
        prompt_eval_ns = result.get("prompt_eval_duration", 0)
        eval_ns = result.get("eval_duration", 0)
        total_ns = result.get("total_duration", 0)

        ttft_ms = prompt_eval_ns / 1_000_000
        output_time_ms = eval_ns / 1_000_000

        input_tokens = result.get("prompt_eval_count", 0)
        output_tokens = result.get("eval_count", 0)

        token_per_sec = 0
        if output_time_ms > 0:
            token_per_sec = (output_tokens / output_time_ms) * 1000

        return {
            "model": model_name,
            "response": result.get("response", ""),
            "latency_ms": total_time_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "token_per_sec": token_per_sec,
            "ttft_ms": ttft_ms,
            "total_time_ms": total_ns / 1_000_000,
        }
