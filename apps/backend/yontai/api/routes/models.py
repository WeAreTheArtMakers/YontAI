from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from yontai.core.exceptions import OllamaConnectionError, OllamaModelError
from yontai.db.models import Model
from yontai.db.session import get_db
from yontai.integrations.ollama import OllamaClient
from yontai.models.service import ModelRegistryService
from yontai.schemas.models import (
    ChatRequest,
    ChatResponse,
    FolderScanRequest,
    HuggingFaceRegistrationRequest,
    ModelAnalysisRead,
    ModelCreate,
    ModelDiscoveryResult,
    ModelRead,
    ModelUpdate,
)

router = APIRouter()


@router.get("", response_model=list[ModelRead])
def list_models(db: Session = Depends(get_db)) -> list[Model]:
    return ModelRegistryService(db).list_models()


@router.post("", response_model=ModelRead, status_code=201)
def register_model(payload: ModelCreate, db: Session = Depends(get_db)) -> Model:
    try:
        return ModelRegistryService(db).register(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import", response_model=ModelRead, status_code=201)
def import_model(payload: ModelCreate, db: Session = Depends(get_db)) -> Model:
    return register_model(payload, db)


@router.post("/import-file", response_model=ModelRead, status_code=201)
async def import_model_file(
    file: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> Model:
    try:
        return ModelRegistryService(db).import_uploaded_file(
            filename=file.filename or "model",
            file_object=file.file,
            project_id=project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scan-folder", response_model=ModelDiscoveryResult)
def scan_model_folder(
    payload: FolderScanRequest,
    db: Session = Depends(get_db),
) -> ModelDiscoveryResult:
    try:
        return ModelRegistryService(db).scan_folder(payload.folder_path, payload.project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/discover/ollama", response_model=ModelDiscoveryResult)
def discover_ollama_models(db: Session = Depends(get_db)) -> ModelDiscoveryResult:
    try:
        return ModelRegistryService(db).discover_ollama()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/huggingface", response_model=ModelRead, status_code=201)
def register_huggingface_model(
    payload: HuggingFaceRegistrationRequest,
    db: Session = Depends(get_db),
) -> Model:
    try:
        return ModelRegistryService(db).register_huggingface(
            payload.repository_id,
            payload.project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/chat", response_model=ChatResponse)
async def chat_model(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    model = ModelRegistryService(db).get_model(payload.model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model bulunamadı.")

    if model.source != "ollama":
        raise HTTPException(
            status_code=400,
            detail="Chat şu anda yalnızca Ollama modelleriyle destekleniyor.",
        )

    ollama_model_name = model.provider_id or model.name
    
    # Check if model supports vision (llava, bakllava, etc.)
    is_vision_model = any(
        vision_name in ollama_model_name.lower() 
        for vision_name in ["llava", "bakllava", "vision"]
    )
    
    try:
        async with OllamaClient() as client:
            if not await client.health_check():
                raise HTTPException(
                    status_code=503,
                    detail="Ollama servisi çalışmıyor. Lütfen Ollama'yı başlatın.",
                )

            # Prepare messages
            messages = [{"role": "user", "content": payload.prompt.strip()}]
            
            # Add images if vision model and images provided
            if is_vision_model and hasattr(payload, 'images') and payload.images:
                # Images should be base64 encoded
                messages[0]["images"] = payload.images

            result = await client.chat(
                model=ollama_model_name,
                messages=messages,
            )
    except OllamaConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OllamaModelError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    response_text = result.get("message", {}).get("content")
    if not isinstance(response_text, str) or not response_text.strip():
        raise HTTPException(status_code=502, detail="Ollama boş veya geçersiz yanıt döndürdü.")

    return ChatResponse(
        response=response_text,
        model_id=model.id,
        model_name=ollama_model_name,
    )


@router.get("/{model_id}", response_model=ModelRead)
def get_model(model_id: str, db: Session = Depends(get_db)) -> Model:
    model = ModelRegistryService(db).get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model bulunamadı.")
    return model


@router.post("/{model_id}/analyze", response_model=ModelAnalysisRead)
def analyze_model(model_id: str, db: Session = Depends(get_db)) -> ModelAnalysisRead:
    analysis = ModelRegistryService(db).analyze(model_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Model bulunamadı.")
    return analysis


@router.patch("/{model_id}", response_model=ModelRead)
def update_model(model_id: str, payload: ModelUpdate, db: Session = Depends(get_db)) -> Model:
    model = ModelRegistryService(db).update_model(model_id, payload)
    if model is None:
        raise HTTPException(status_code=404, detail="Model bulunamadı.")
    return model


@router.get("/{model_id}/analysis", response_model=ModelAnalysisRead)
def get_model_analysis(model_id: str, db: Session = Depends(get_db)) -> ModelAnalysisRead:
    return analyze_model(model_id, db)


@router.delete("/{model_id}", status_code=204)
def delete_model(model_id: str, db: Session = Depends(get_db)) -> Response:
    deleted = ModelRegistryService(db).delete(model_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Model bulunamadı.")
    return Response(status_code=204)
