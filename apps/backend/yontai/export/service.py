"""
Model Export Service
Handles exporting models to different formats (GGUF, SafeTensors, ONNX)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from yontai.core.paths import storage_path
from yontai.db.models import Job
from yontai.repositories.jobs import JobRepository


class ModelExportService:
    """Service for exporting models to various formats"""

    def write_knowledge_manifest(
        self,
        export_dir: Path,
        output_name: str,
        knowledge_packs: list[dict[str, Any]],
    ) -> Path | None:
        if not knowledge_packs:
            return None
        export_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = export_dir / f"{output_name}.knowledge_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "output_name": output_name,
                    "knowledge_packs": knowledge_packs,
                    "statement_tr": (
                        "Bu dosya YontAI tarafından modele bağlanan doküman/dataset bilgi "
                        "paketlerini taşır. Ağırlıklara işlenmiş bilgi için adapter veya "
                        "fine-tuned model çıktısı ile birlikte dağıtılmalıdır."
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return manifest_path

    async def export_to_gguf(
        self, model_path: str, output_name: str, quantization: str = "Q4_K_M"
    ) -> Path:
        """
        Export model to GGUF format
        
        Args:
            model_path: Path to source model
            output_name: Name for output file
            quantization: Quantization level (Q4_K_M, Q5_K_M, Q8_0, etc.)
        
        Returns:
            Path to exported GGUF file
        """
        export_dir = storage_path("exports") / "gguf"
        export_dir.mkdir(parents=True, exist_ok=True)

        output_path = export_dir / f"{output_name}.{quantization}.gguf"

        # Real implementation would use llama.cpp conversion tools
        # For now, create a placeholder
        output_path.write_text(
            f"GGUF export placeholder\nModel: {model_path}\nQuant: {quantization}"
        )

        return output_path

    async def export_to_safetensors(self, model_path: str, output_name: str) -> Path:
        """
        Export model to SafeTensors format
        
        Args:
            model_path: Path to source model
            output_name: Name for output directory
        
        Returns:
            Path to exported SafeTensors directory
        """
        export_dir = storage_path("exports") / "safetensors" / output_name
        export_dir.mkdir(parents=True, exist_ok=True)

        # Real implementation would use transformers library
        # For now, create placeholder files
        (export_dir / "model.safetensors").write_text("SafeTensors placeholder")
        (export_dir / "config.json").write_text(
            json.dumps({"model_type": "causal_lm", "source": model_path}, indent=2)
        )

        return export_dir

    async def export_to_onnx(self, model_path: str, output_name: str) -> Path:
        """
        Export model to ONNX format
        
        Args:
            model_path: Path to source model
            output_name: Name for output file
        
        Returns:
            Path to exported ONNX file
        """
        export_dir = storage_path("exports") / "onnx"
        export_dir.mkdir(parents=True, exist_ok=True)

        output_path = export_dir / f"{output_name}.onnx"

        # Real implementation would use optimum library
        # For now, create a placeholder
        output_path.write_text(f"ONNX export placeholder\nModel: {model_path}")

        return output_path

    async def export_for_ollama(self, model_path: str, model_name: str) -> dict[str, Any]:
        """
        Prepare model for Ollama import
        
        Args:
            model_path: Path to source model
            model_name: Name for Ollama model
        
        Returns:
            Dict with Ollama import instructions
        """
        export_dir = storage_path("exports") / "ollama" / model_name
        export_dir.mkdir(parents=True, exist_ok=True)

        # Create Modelfile
        modelfile_content = f"""FROM {model_path}

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40

TEMPLATE \"\"\"{{{{ .System }}}}
{{{{ .Prompt }}}}\"\"\"

SYSTEM \"\"\"You are a helpful AI assistant.\"\"\"
"""

        modelfile_path = export_dir / "Modelfile"
        modelfile_path.write_text(modelfile_content)

        return {
            "modelfile_path": str(modelfile_path),
            "import_command": f"ollama create {model_name} -f {modelfile_path}",
            "instructions": [
                f"1. GGUF modelini şu dizine kopyalayın: {export_dir}",
                f"2. Şu komutu çalıştırın: ollama create {model_name} -f {modelfile_path}",
                f"3. Test edin: ollama run {model_name}",
            ],
        }


async def export_model_job(job: Job, repo: JobRepository) -> None:
    """
    Background job handler for model export
    """
    import asyncio

    payload_data = job.payload or {}
    model_path = payload_data.get("model_path")
    output_name = payload_data.get("output_name")
    export_format = payload_data.get("format", "gguf")
    quantization = payload_data.get("quantization", "Q4_K_M")
    knowledge_packs = payload_data.get("knowledge_packs") or []

    if not model_path or not output_name:
        raise ValueError("model_path ve output_name gerekli")

    service = ModelExportService()

    # Update progress
    job.progress = 10
    job.current_step = f"{export_format.upper()} formatına dönüştürülüyor..."
    repo.save(job)

    await asyncio.sleep(1)  # Simulate processing

    # Export based on format
    if export_format == "gguf":
        output_path = await service.export_to_gguf(model_path, output_name, quantization)
        manifest_path = service.write_knowledge_manifest(
            output_path.parent, output_name, knowledge_packs
        )
        result = {"format": "gguf", "path": str(output_path), "quantization": quantization}
        if manifest_path:
            result["knowledge_manifest_path"] = str(manifest_path)
    elif export_format == "safetensors":
        output_path = await service.export_to_safetensors(model_path, output_name)
        manifest_path = service.write_knowledge_manifest(output_path, output_name, knowledge_packs)
        result = {"format": "safetensors", "path": str(output_path)}
        if manifest_path:
            result["knowledge_manifest_path"] = str(manifest_path)
    elif export_format == "onnx":
        output_path = await service.export_to_onnx(model_path, output_name)
        manifest_path = service.write_knowledge_manifest(
            output_path.parent, output_name, knowledge_packs
        )
        result = {"format": "onnx", "path": str(output_path)}
        if manifest_path:
            result["knowledge_manifest_path"] = str(manifest_path)
    elif export_format == "ollama":
        result = await service.export_for_ollama(model_path, output_name)
        manifest_path = service.write_knowledge_manifest(
            Path(result["modelfile_path"]).parent, output_name, knowledge_packs
        )
        if manifest_path:
            result["knowledge_manifest_path"] = str(manifest_path)
    else:
        raise ValueError(f"Desteklenmeyen format: {export_format}")

    # Update job with results
    job.progress = 90
    job.current_step = "Export tamamlandı"
    job.result = result
    repo.save(job)

    await asyncio.sleep(0.5)


# Real GGUF conversion would use llama.cpp:
"""
import subprocess

def convert_to_gguf(model_path: str, output_path: str, quantization: str):
    # Convert HF model to GGUF
    subprocess.run([
        "python", "convert-hf-to-gguf.py",
        model_path,
        "--outfile", output_path,
        "--outtype", quantization
    ], check=True)
"""

# Real SafeTensors conversion:
"""
from transformers import AutoModelForCausalLM

def convert_to_safetensors(model_path: str, output_dir: str):
    model = AutoModelForCausalLM.from_pretrained(model_path)
    model.save_pretrained(output_dir, safe_serialization=True)
"""

# Real ONNX conversion:
"""
from optimum.onnxruntime import ORTModelForCausalLM

def convert_to_onnx(model_path: str, output_path: str):
    model = ORTModelForCausalLM.from_pretrained(model_path, export=True)
    model.save_pretrained(output_path)
"""
