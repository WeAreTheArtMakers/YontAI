"""Hardware detection and profiling module.

Sistem donanımını tespit eder, Apple Silicon MLX yeteneklerini
ve bellek durumunu analiz eder.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from typing import Any

import psutil

logger = logging.getLogger(__name__)


def detect_hardware_profile() -> dict[str, object]:
    """Kapsamlı donanım profili çıkar.

    Returns:
        Donanım profili sözlüğü
    """
    mem = psutil.virtual_memory()
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()

    profile: dict[str, object] = {
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": cpu_count,
        "cpu_freq_mhz": round(cpu_freq.current, 2) if cpu_freq else None,
        "acceleration_backend": _detect_acceleration(),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_total_gb": round(mem.total / (1024**3), 2),
        "ram_used_gb": round(mem.used / (1024**3), 2),
        "ram_percent": mem.percent,
        "capabilities": _detect_capabilities(),
    }

    return profile


def _detect_acceleration() -> str:
    """Hızlandırma backend'ini tespit et.

    Öncelik sırası: MLX > MPS > CPU
    """
    # Apple Silicon kontrolü
    is_apple_silicon = (
        platform.machine() == "arm64"
        and platform.system() == "Darwin"
    )

    if is_apple_silicon:
        # MLX kontrolü
        try:
            import mlx.core  # noqa: F401
            return "mlx"
        except ImportError:
            pass

        # MPS (Metal Performance Shaders) kontrolü
        try:
            import torch
            if torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass

        return "apple_silicon_cpu"

    # CUDA kontrolü
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass

    # ROCm kontrolü
    if platform.system() == "Linux":
        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return "rocm"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return "cpu"


def _detect_capabilities() -> dict[str, bool | str]:
    """Sistem yeteneklerini tespit et.

    Returns:
        Yetenekler sözlüğü
    """
    capabilities: dict[str, bool | str] = {
        "mlx_available": False,
        "mps_available": False,
        "cuda_available": False,
        "metal_support": False,
        "apple_silicon": False,
        "unified_memory": False,
        "optimized_backend": "cpu",
    }

    is_apple_silicon = (
        platform.machine() == "arm64"
        and platform.system() == "Darwin"
    )

    if is_apple_silicon:
        capabilities["apple_silicon"] = True
        capabilities["metal_support"] = True
        capabilities["unified_memory"] = True

        # Apple Silicon modelini tespit et
        chip_info = _get_apple_chip_info()
        if chip_info:
            capabilities["chip"] = chip_info

        # MLX
        try:
            import mlx.core  # noqa: F401
            capabilities["mlx_available"] = True
            capabilities["optimized_backend"] = "mlx"
        except ImportError:
            pass

        # MPS
        try:
            import torch
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                capabilities["mps_available"] = True
                if capabilities["optimized_backend"] == "cpu":
                    capabilities["optimized_backend"] = "mps"
        except ImportError:
            pass

    else:
        # CUDA
        try:
            import torch
            if torch.cuda.is_available():
                capabilities["cuda_available"] = True
                capabilities["cuda_device"] = torch.cuda.get_device_name(0)
                capabilities["cuda_version"] = torch.version.cuda
                capabilities["optimized_backend"] = "cuda"
        except ImportError:
            pass

    return capabilities


def _get_apple_chip_info() -> str | None:
    """Apple Silicon çip modelini tespit et."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            brand = result.stdout.strip()
            if "Apple" in brand:
                return brand
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: platform.processor()
    proc = platform.processor()
    if proc and "Apple" in proc:
        return proc

    return None


def get_optimized_config() -> dict[str, Any]:
    """Donanıma göre optimize edilmiş yapılandırma döndür.

    M1 Pro 16 GB için varsayılan optimize değerler.

    Returns:
        Optimize edilmiş yapılandırma
    """
    profile = detect_hardware_profile()
    ram_gb = profile.get("ram_total_gb", 16)
    if isinstance(ram_gb, int | float):
        ram_gb = float(ram_gb)
    else:
        ram_gb = 16.0

    backend = profile.get("capabilities", {})
    if isinstance(backend, dict):
        optimized = backend.get("optimized_backend", "cpu")
    else:
        optimized = "cpu"

    # RAM'e göre ölçeklendir
    if ram_gb >= 64:
        model_sizes = {"fast": "7b", "smart": "34b"}
        max_loaded_models = 3
    elif ram_gb >= 32:
        model_sizes = {"fast": "3b", "smart": "14b"}
        max_loaded_models = 2
    elif ram_gb >= 16:
        model_sizes = {"fast": "1.3b", "smart": "7b"}
        max_loaded_models = 2
    else:
        model_sizes = {"fast": "1b", "smart": "3b"}
        max_loaded_models = 1

    return {
        "model_sizes": model_sizes,
        "max_loaded_models": max_loaded_models,
        "preferred_backend": str(optimized),
        "batch_size": 1,
        "max_tokens_fast": 2048,
        "max_tokens_smart": 4096,
        "recommended_quantization": "q4" if ram_gb <= 16 else "q8",
        "system_ram_gb": ram_gb,
        "acceleration": str(profile.get("acceleration_backend", "cpu")),
    }