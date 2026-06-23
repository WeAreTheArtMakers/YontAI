import json
import re
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any


class MetadataRecoveryEngine:
    @staticmethod
    def recover_ollama(name: str) -> dict[str, Any]:
        """
        Runs `ollama show MODEL_NAME` and parses the output for metadata.
        Extracts: family, parameter_size, quantization, context_length, template, license
        """
        metadata: dict[str, Any] = {}
        try:
            completed = subprocess.run(
                ["ollama", "show", name],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = completed.stdout
            for line in output.splitlines():
                if not line.strip():
                    continue
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    key = parts[0].strip().lower()
                    val = parts[1].strip()
                    if "family" in key:
                        metadata["family"] = val
                    elif "parameter size" in key.replace("_", " ") or "parameters" in key:
                        metadata["parameter_size"] = val
                    elif "quantization" in key:
                        metadata["quantization"] = val
                    elif "context length" in key.replace("_", " ") or "context" in key:
                        metadata["context_length"] = val
                    elif "license" in key:
                        metadata["license"] = val
            license_run = subprocess.run(
                ["ollama", "show", "--license", name],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if license_run.returncode == 0 and license_run.stdout.strip():
                metadata["license"] = license_run.stdout.strip().splitlines()[0][:160]

            template_run = subprocess.run(
                ["ollama", "show", "--template", name],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if template_run.returncode == 0 and template_run.stdout.strip():
                metadata["template"] = template_run.stdout.strip()[:4000]

        except Exception:
            pass
        return metadata

    @staticmethod
    def recover_huggingface(repo_id: str) -> dict[str, Any]:
        """
        Fetches metadata from HuggingFace.
        config.json, tokenizer_config.json, generation_config.json
        """
        metadata: dict[str, Any] = {}
        base_url = f"https://huggingface.co/{repo_id}/resolve/main"

        files_to_check = ["config.json", "tokenizer_config.json", "generation_config.json"]
        for file_name in files_to_check:
            try:
                url = f"{base_url}/{file_name}"
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    if isinstance(data, dict):
                        for k, v in data.items():
                            metadata[f"{file_name}_{k}"] = v
                            # Combine common ones
                            if k in ["architectures", "model_type"]:
                                metadata["architecture"] = v[0] if isinstance(v, list) else v
                            if k == "max_position_embeddings":
                                metadata["context_length"] = v
                            if k == "tokenizer_class":
                                metadata["tokenizer"] = v
            except Exception:
                pass

        # Readme for license/parameter size
        try:
            url = f"https://huggingface.co/api/models/{repo_id}"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
                if isinstance(data, dict):
                    metadata.update(data)
        except Exception:
            pass

        return metadata

    @staticmethod
    def parse_gguf(path: Path) -> dict[str, Any]:
        """
        Reads GGUF header to extract metadata.
        """
        metadata: dict[str, Any] = {}
        try:
            # Simple binary read or pip install gguf. For now, doing a basic binary scan
            with path.open("rb") as f:
                magic = f.read(4)
                if magic in [b"GGUF", b"gguf"]:
                    metadata["format"] = "gguf"
                    # Read rest of file for strings like "llama", "context_length", etc.
                    # As a fallback, we will just use regex on the first 1MB
                    content = f.read(1024 * 1024)

                    # Look for architecture
                    if b"llama" in content.lower():
                        metadata["architecture"] = "llama"
                    elif b"mistral" in content.lower():
                        metadata["architecture"] = "mistral"

                    # Context length hint in gguf
                    match = re.search(
                        b"llama\\.context_length\x00\x04\x00\x00\x00([0-9]+)\x00",
                        content,
                    )
                    if match:
                        metadata["context_length"] = int(match.group(1).decode("ascii"))
        except Exception:
            pass
        return metadata

    @staticmethod
    def recover_local(path: Path) -> dict[str, Any]:
        metadata: dict[str, Any] = {}

        # File stats
        if path.is_file():
            stat = path.stat()
            metadata["creation_date"] = datetime.fromtimestamp(stat.st_ctime).isoformat()

            # Compute hash (SHA256) - read in chunks
            digest = sha256()
            try:
                with path.open("rb") as f:
                    # To avoid freezing on huge files, we can just hash first 100MB or do it fully.
                    # Task requested hash. We will compute fully but with large chunks.
                    for byte_block in iter(lambda: f.read(4096 * 1024), b""):
                        digest.update(byte_block)
                metadata["file_hash"] = digest.hexdigest()
            except Exception:
                pass

        if path.suffix.lower() == ".gguf":
            metadata.update(MetadataRecoveryEngine.parse_gguf(path))

        elif path.is_dir() or path.suffix.lower() in [".safetensors", ".bin"]:
            # Check for config.json in directory
            target_dir = path if path.is_dir() else path.parent
            config_path = target_dir / "config.json"
            if config_path.exists():
                try:
                    with config_path.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                        metadata.update(data)
                except Exception:
                    pass
        return metadata
