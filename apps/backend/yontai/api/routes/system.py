import asyncio
import json

import psutil
from fastapi import APIRouter
from sqlalchemy import text
from sse_starlette.sse import EventSourceResponse

from yontai.core.config import get_settings
from yontai.core.hardware import detect_hardware_profile
from yontai.db.session import SessionLocal
from yontai.integrations.ollama import OllamaClient

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Backend health check"""
    return {"status": "ok", "service": "yontai-backend"}


@router.get("/info")
def info() -> dict[str, str]:
    settings = get_settings()
    return {"name": "YontAI", "version": "0.1.0", "env": settings.env}


@router.get("/hardware")
def hardware() -> dict[str, object]:
    return detect_hardware_profile()


@router.get("/capabilities")
async def capabilities() -> dict[str, object]:
    """System capabilities including Ollama status"""
    # Check Ollama connection
    ollama_status = "error"
    try:
        async with OllamaClient() as client:
            if await client.health_check():
                ollama_status = "ok"
    except Exception:
        pass

    database_status = "error"
    try:
        with SessionLocal() as db:
            db.execute(text("select 1"))
            database_status = "ok"
    except Exception:
        database_status = "error"

    return {
        "database": "sqlite",
        "database_status": database_status,
        "events": ["server-sent-events"],
        "ai_runtimes": ["transformers", "peft", "trl", "unsloth", "ollama", "mlflow"],
        "ollama_status": ollama_status,
        "metadata_engine_status": "ok",
        "benchmark_engine_status": "ok",
        "job_worker_status": "ok",
    }


@router.get("/metrics/stream")
async def stream_system_metrics() -> EventSourceResponse:
    """
    Real-time system metrics stream
    Provides CPU, RAM, disk usage updates every 2 seconds
    """

    async def metric_generator():
        while True:
            try:
                # CPU metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                cpu_count = psutil.cpu_count()

                # Memory metrics
                memory = psutil.virtual_memory()
                memory_used_gb = memory.used / (1024**3)
                memory_total_gb = memory.total / (1024**3)
                memory_percent = memory.percent

                # Disk metrics
                disk = psutil.disk_usage("/")
                disk_used_gb = disk.used / (1024**3)
                disk_total_gb = disk.total / (1024**3)
                disk_percent = disk.percent

                # Network metrics (optional)
                net_io = psutil.net_io_counters()
                bytes_sent_mb = net_io.bytes_sent / (1024**2)
                bytes_recv_mb = net_io.bytes_recv / (1024**2)

                # GPU metrics (if available)
                gpu_metrics = {}
                try:
                    import GPUtil

                    gpus = GPUtil.getGPUs()
                    if gpus:
                        gpu = gpus[0]
                        gpu_metrics = {
                            "gpu_name": gpu.name,
                            "gpu_load": gpu.load * 100,
                            "gpu_memory_used": gpu.memoryUsed,
                            "gpu_memory_total": gpu.memoryTotal,
                            "gpu_memory_percent": (gpu.memoryUsed / gpu.memoryTotal * 100),
                            "gpu_temperature": gpu.temperature,
                        }
                except Exception:
                    # GPU monitoring not available
                    pass

                metrics = {
                    "timestamp": asyncio.get_event_loop().time(),
                    "cpu": {
                        "percent": round(cpu_percent, 1),
                        "count": cpu_count,
                    },
                    "memory": {
                        "used_gb": round(memory_used_gb, 2),
                        "total_gb": round(memory_total_gb, 2),
                        "percent": round(memory_percent, 1),
                    },
                    "disk": {
                        "used_gb": round(disk_used_gb, 2),
                        "total_gb": round(disk_total_gb, 2),
                        "percent": round(disk_percent, 1),
                    },
                    "network": {
                        "sent_mb": round(bytes_sent_mb, 2),
                        "recv_mb": round(bytes_recv_mb, 2),
                    },
                }

                if gpu_metrics:
                    metrics["gpu"] = gpu_metrics

                yield {
                    "event": "metrics",
                    "data": json.dumps(metrics, ensure_ascii=False),
                }

                await asyncio.sleep(2)

            except Exception as e:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(e)}, ensure_ascii=False),
                }
                await asyncio.sleep(5)

    return EventSourceResponse(metric_generator())
