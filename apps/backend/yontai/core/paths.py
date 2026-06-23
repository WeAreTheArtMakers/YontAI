from pathlib import Path

from yontai.core.config import get_settings


def backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def project_root() -> Path:
    return backend_dir().parents[1]


def app_data_dir() -> Path:
    configured_dir = get_settings().app_data_dir
    if configured_dir.is_absolute():
        return configured_dir.resolve()
    return (backend_dir() / configured_dir).resolve()


def storage_path(name: str) -> Path:
    return app_data_dir() / name
