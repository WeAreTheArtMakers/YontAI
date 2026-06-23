from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse

from yontai.utils.pdf_parser import extract_text_from_pdf

router = APIRouter()

READABLE_EXTENSIONS = {".txt", ".md", ".json", ".jsonl", ".csv", ".log", ".pdf"}
MAX_CONTEXT_FILE_SIZE = 20 * 1024 * 1024


def _validate_context_file(file_name: str, size: int) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix not in READABLE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Bu dosya türü chat bağlamı için desteklenmiyor.",
        )
    if size > MAX_CONTEXT_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Dosya çok büyük. Chat bağlamı için 20 MB altı dosya kullanın.",
        )
    return suffix


@router.get("/read", response_class=PlainTextResponse)
def read_context_file(path: str = Query(min_length=1)) -> str:
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Dosya bulunamadı.")

    size = file_path.stat().st_size
    suffix = _validate_context_file(file_path.name, size)

    try:
        if suffix == ".pdf":
            return extract_text_from_pdf(file_path)
        return file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Dosya okunamadı: {exc}") from exc


@router.post("/extract")
async def extract_context_upload(file: UploadFile = File(...)) -> dict[str, Any]:
    file_name = file.filename or "document"
    content = await file.read()
    suffix = _validate_context_file(file_name, len(content))
    if not content:
        raise HTTPException(status_code=400, detail="Dosya boş.")

    try:
        if suffix == ".pdf":
            import io

            text = extract_text_from_pdf(io.BytesIO(content))
            file_type = "pdf"
        else:
            text = content.decode("utf-8-sig", errors="replace")
            file_type = "text"
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Dosya işlenemedi: {exc}") from exc

    return {
        "name": file_name,
        "type": file_type,
        "size": len(content),
        "content": text[:80_000],
        "truncated": len(text) > 80_000,
    }
