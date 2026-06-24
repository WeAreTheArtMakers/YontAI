"""YontAI Backend — AI Coding Lab API Server."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from yontai.api.router import api_router
from yontai.core.config import get_settings
from yontai.db.session import init_db
from yontai.deployment.service import deploy_model_job
from yontai.export.service import export_model_job
from yontai.jobs.worker import get_worker
from yontai.training.lora_trainer import train_lora_model


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    worker = get_worker()
    worker.register_handler("training", train_lora_model)
    worker.register_handler("fine_tuning", train_lora_model)
    worker.register_handler("lora_training", train_lora_model)
    worker.register_handler("model_export", export_model_job)
    worker.register_handler("model_deployment", deploy_model_job)
    import asyncio
    worker_task = asyncio.create_task(worker.start())
    yield
    await worker.stop()
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="YontAI Local API",
        version="0.1.0",
        docs_url="/docs" if settings.env == "development" else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(api_router, prefix="/api/v1")

    # Static files (officialWeb)
    _root = Path(__file__).resolve().parent.parent.parent.parent  # proje root
    _webui = _root / "officialWeb"
    if _webui.exists():
        app.mount("/app", StaticFiles(directory=str(_webui), html=True), name="webui")

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/app/index.html" if (_root / "officialWeb").exists() else "/api/v1/system/health")

    @app.get("/health", include_in_schema=False)
    async def health():
        return JSONResponse({"status": "ok", "service": "yontai-backend"})

    return app


app = create_app()