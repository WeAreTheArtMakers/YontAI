import platform

import psutil


def detect_hardware_profile() -> dict[str, object]:
    mem = psutil.virtual_memory()
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "acceleration_backend": "unknown",
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_total_gb": round(mem.total / (1024**3), 2),
        "ram_used_gb": round(mem.used / (1024**3), 2),
        "ram_percent": mem.percent,
        "capabilities": {},
    }
