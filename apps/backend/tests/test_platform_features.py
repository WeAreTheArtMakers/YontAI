from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from yontai.db.models import Dataset as DBDataset
from yontai.db.models import Model as DBModel
from yontai.db.session import SessionLocal
from yontai.diagnostics.service import DiagnosticService
from yontai.main import app
from yontai.models.metadata import MetadataRecoveryEngine


def test_benchmark_studio_mvp() -> None:
    with TestClient(app) as client:
        # Mock benchmark service to avoid calling actual ollama
        with patch("yontai.benchmarking.service.BenchmarkService.run_ollama_benchmark") as mock_run:
            mock_run.side_effect = [
                {
                    "model": "qwen2.5:7b",
                    "response": "Merhaba",
                    "latency_ms": 1500,
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "token_per_sec": 13.3,
                    "ttft_ms": 200,
                    "total_time_ms": 1500,
                },
                {
                    "model": "gemma:2b",
                    "response": "Selam",
                    "latency_ms": 1200,
                    "input_tokens": 10,
                    "output_tokens": 15,
                    "token_per_sec": 12.5,
                    "ttft_ms": 180,
                    "total_time_ms": 1200,
                },
            ]
            response = client.post(
                "/api/v1/benchmarks/execute",
                json={"models": ["qwen2.5:7b", "gemma:2b"], "prompt": "Selam!"},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["model"] == "qwen2.5:7b"
            assert data[0]["latency_ms"] == 1500
            assert data[1]["model"] == "gemma:2b"


def test_model_doctor_2b_model_100k_dataset_high_risk() -> None:
    # Use real DiagnosticService with mocked DB models
    db = SessionLocal()
    try:
        service = DiagnosticService(db)

        # We need to mock the repository gets
        with (
            patch("yontai.repositories.models.ModelRepository.get") as mock_model_get,
            patch("yontai.repositories.datasets.DatasetRepository.get") as mock_dataset_get,
        ):
            # Create 2B model
            model = DBModel(
                id="test-model-2b",
                name="Test 2B",
                parameter_count=2_000_000_000,
                context_length=4096,
                model_family="llama",
            )
            mock_model_get.return_value = model

            # Create 100k dataset
            dataset = DBDataset(
                id="test-dataset-100k",
                name="Large Dataset",
                row_count=150_000,
                average_tokens=500,
                duplicate_ratio=0.01,
                empty_ratio=0.01,
                statistics={"dominant_language": "en"},
            )
            mock_dataset_get.return_value = dataset

            diagnosis = service.diagnose_model_dataset("test-model-2b", "test-dataset-100k")
            assert diagnosis is not None
            assert "Underfitting riski yüksek" in diagnosis.reasons[0]
            assert diagnosis.risk_level in ["Yüksek", "Orta"]

    finally:
        db.close()


def test_metadata_recovery_gguf_context_length(tmp_path: Path) -> None:
    # Create fake GGUF with context length hint
    gguf_path = tmp_path / "test_model.gguf"
    gguf_path.write_bytes(b"GGUF\x00\x00\x00\x00llama.context_length\x00\x04\x00\x00\x002048\x00")

    metadata = MetadataRecoveryEngine.recover_local(gguf_path)
    assert metadata.get("context_length") == 2048
    assert metadata.get("format") == "gguf"
