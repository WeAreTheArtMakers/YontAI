import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from yontai.datasets.service import DatasetRegistryService
from yontai.db.models import Dataset
from yontai.db.session import get_db
from yontai.schemas.datasets import (
    DatasetCreate,
    DatasetRead,
    PublicDatasetCatalogItem,
    PublicDatasetImport,
)

router = APIRouter()


@router.get("", response_model=list[DatasetRead])
def list_datasets(db: Session = Depends(get_db)) -> list[Dataset]:
    return DatasetRegistryService(db).list_datasets()


@router.post("", response_model=DatasetRead, status_code=201)
def register_dataset(payload: DatasetCreate, db: Session = Depends(get_db)) -> Dataset:
    try:
        return DatasetRegistryService(db).register_from_path(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/upload", response_model=DatasetRead, status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    project_id: str | None = Form(default=None),
    task_type: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> Dataset:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Yüklenen dosya boş.")
    try:
        return DatasetRegistryService(db).register_upload(
            filename=file.filename or "dataset",
            content=content,
            name=name,
            project_id=project_id,
            task_type=task_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/from-documents", response_model=DatasetRead, status_code=201)
async def create_dataset_from_documents(
    files: list[UploadFile] = File(...),
    name: str = Form(...),
    project_id: str | None = Form(default=None),
    task_type: str = Form(default="instruction"),
    db: Session = Depends(get_db),
) -> Dataset:
    """Create a dataset from multiple document files (TXT, PDF, MD)."""
    import io
    import json

    from yontai.utils.pdf_parser import extract_text_from_pdf
    
    if not files:
        raise HTTPException(status_code=400, detail="En az bir döküman yüklemelisiniz.")
    
    # Extract text from all documents
    documents = []
    for file in files:
        content = await file.read()
        filename = file.filename or "document"
        
        try:
            # PDF files
            if filename.lower().endswith('.pdf'):
                text = extract_text_from_pdf(io.BytesIO(content))
            # Text files
            else:
                text = content.decode('utf-8')
            
            if text.strip():
                documents.append({
                    "filename": filename,
                    "content": text.strip()
                })
        except Exception:
            # Skip files that can't be processed
            continue
    
    if not documents:
        raise HTTPException(
            status_code=400,
            detail="Hiçbir döküman işlenemedi. Lütfen geçerli TXT veya PDF dosyaları yükleyin."
        )
    
    # Convert documents to supervised JSONL format.
    jsonl_lines = []
    for doc in documents:
        # Split into chunks (simple paragraph-based splitting)
        paragraphs = [p.strip() for p in doc["content"].split("\n\n") if p.strip()]
        
        for i, paragraph in enumerate(paragraphs[:50]):  # Limit to 50 chunks per document
            if len(paragraph) > 100:  # Only meaningful paragraphs
                jsonl_lines.append(json.dumps({
                    "instruction": (
                        "Aşağıdaki kaynak metindeki bilgiyi doğru, kısa ve Türkçe olarak açıkla."
                    ),
                    "input": f"Kaynak: {doc['filename']}\n\n{paragraph[:1200]}",
                    "output": paragraph[:1200],
                    "source": doc["filename"],
                    "chunk": i + 1
                }, ensure_ascii=False))
    
    if not jsonl_lines:
        raise HTTPException(
            status_code=400,
            detail="Dökümanlardan yeterli veri oluşturulamadı."
        )
    
    # Create JSONL content
    jsonl_content = "\n".join(jsonl_lines).encode('utf-8')
    
    # Register as dataset
    try:
        service = DatasetRegistryService(db)
        dataset = service.register_upload(
            filename=f"{name}.jsonl",
            content=jsonl_content,
            name=name,
            project_id=project_id,
            task_type=task_type,
        )
        dataset.source_type = "documents"
        dataset.statistics = {
            **(dataset.statistics or {}),
            "source_documents": [
                {"filename": doc["filename"], "characters": len(doc["content"])}
                for doc in documents
            ],
            "knowledge_injection_ready": True,
        }
        dataset.report = {
            **(dataset.report or {}),
            "summary_tr": (
                f"{len(documents)} dokümandan {dataset.row_count} eğitim parçası üretildi. "
                "Bu veri seti bilgi paketi veya fine-tuning için kullanılabilir."
            ),
        }
        return service.repo.save(dataset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/public/catalog", response_model=list[PublicDatasetCatalogItem])
def public_dataset_catalog(db: Session = Depends(get_db)) -> list[PublicDatasetCatalogItem]:
    return DatasetRegistryService(db).public_catalog()


@router.get("/huggingface/search")
async def search_huggingface_datasets(
    query: str,
    limit: int = 10,
) -> list[dict[str, str | int]]:
    """Search HuggingFace datasets by query."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://huggingface.co/api/datasets",
                params={"search": query, "limit": limit, "sort": "downloads", "direction": -1},
                timeout=10.0,
            )
            response.raise_for_status()
            datasets = response.json()
            
            return [
                {
                    "id": ds.get("id", ""),
                    "name": ds.get("id", "").split("/")[-1],
                    "author": ds.get("author", ""),
                    "downloads": ds.get("downloads", 0),
                    "likes": ds.get("likes", 0),
                    "description": ds.get("description", "")[:200],
                }
                for ds in datasets[:limit]
            ]
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=500,
            detail="HuggingFace API'ye erişilemedi.",
        ) from exc


@router.post("/public/import", response_model=DatasetRead, status_code=201)
async def import_public_dataset(
    payload: PublicDatasetImport,
    db: Session = Depends(get_db),
) -> Dataset:
    try:
        return await DatasetRegistryService(db).import_public_dataset(payload)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Hugging Face veri seti okunamadı: HTTP {exc.response.status_code}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Hugging Face bağlantısı kurulamadı. İnternet/DNS erişimini kontrol edin "
                f"veya daha küçük JSON/JSONL/CSV/Parquet dosyası olan bir dataset seçin. ({exc})"
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{dataset_id}", response_model=DatasetRead)
def get_dataset(dataset_id: str, db: Session = Depends(get_db)) -> Dataset:
    dataset = DatasetRegistryService(db).get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Veri seti bulunamadı.")
    return dataset


@router.post("/{dataset_id}/analyze", response_model=DatasetRead)
def analyze_dataset(dataset_id: str, db: Session = Depends(get_db)) -> Dataset:
    try:
        dataset = DatasetRegistryService(db).analyze(dataset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if dataset is None:
        raise HTTPException(status_code=404, detail="Veri seti bulunamadı.")
    return dataset


@router.delete("/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: str, db: Session = Depends(get_db)) -> Response:
    service = DatasetRegistryService(db)
    dataset = service.get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Veri seti bulunamadı.")
    service.repo.delete(dataset)
    return Response(status_code=204)


@router.post("/{dataset_id}/augment", response_model=DatasetRead)
async def augment_dataset(dataset_id: str, db: Session = Depends(get_db)) -> Dataset:
    service = DatasetRegistryService(db)
    dataset = service.get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Veri seti bulunamadı.")

    try:
        return await service.import_public_dataset(
            PublicDatasetImport(
                repository_id="cgulse/alpaca-cleaned-tr",
                name=f"{dataset.name} - Public Turkish Enrichment",
                project_id=dataset.project_id,
                task_type=dataset.task_type or "instruction",
                max_rows=1000,
            )
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=400,
            detail="Public veri seti indirilemedi. İnternet bağlantısını kontrol edin.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
