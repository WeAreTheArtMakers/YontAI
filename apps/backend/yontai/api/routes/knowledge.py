"""API routes for web knowledge ingestion and search.

Provides endpoints for:
- POST /knowledge/ingest - Ingest knowledge from a URL (GitHub, npm, PyPI, web)
- POST /knowledge/search - Search ingested knowledge via vector DB
- GET  /knowledge/stats  - Get knowledge base statistics

Architecture (from ARCHITECTURE.md §5):
    URL → WebFetcher → Code Extraction → Chunking → Embedding → Vector DB
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from yontai.rag.context_engine import ContextEngine, VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class IngestRequest(BaseModel):
    """Request body for knowledge ingestion."""

    url: str = Field(..., description="URL to ingest knowledge from")
    source_type: str | None = Field(
        default=None,
        description="Override source type: github, npm, pypi, web",
    )
    max_files: int = Field(default=50, ge=1, le=500, description="Max files to fetch")
    project_id: str | None = Field(default=None, description="Optional project ID to associate")


class IngestResponse(BaseModel):
    """Response from a knowledge ingestion request."""

    success: bool
    source_url: str
    source_type: str
    files_fetched: int
    chunks_indexed: int
    errors: list[str] = Field(default_factory=list)
    summary: str = ""


class SearchRequest(BaseModel):
    """Request body for knowledge base search."""

    query: str = Field(..., min_length=3, description="Search query (code or natural language)")
    n_results: int = Field(default=5, ge=1, le=50, description="Number of results")
    language: str | None = Field(default=None, description="Filter by language (python, ts, etc.)")
    source_type: str | None = Field(default=None, description="Filter by source type")


class SearchResultItem(BaseModel):
    """A single search result item."""

    file_path: str
    symbol_name: str
    symbol_type: str
    content: str
    language: str
    score: float = 0.0
    source_url: str | None = None


class SearchResponse(BaseModel):
    """Response from a knowledge search request."""

    results: list[SearchResultItem]
    total_results: int
    query: str


class KnowledgeStats(BaseModel):
    """Knowledge base statistics."""

    total_chunks: int
    total_sources: int
    languages: dict[str, int] = Field(default_factory=dict)
    source_types: dict[str, int] = Field(default_factory=dict)

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def _get_context_engine() -> ContextEngine:
    """Get or create the ContextEngine singleton."""
    try:
        engine = ContextEngine()
        return engine
    except Exception as exc:
        logger.error("Failed to initialize ContextEngine: %s", exc)
        raise HTTPException(status_code=503, detail="Knowledge base not available")


def _get_vector_store() -> VectorStore:
    """Get or create the VectorStore singleton for knowledge base."""
    try:
        from yontai.core.paths import storage_path

        store = VectorStore(
            collection_name="yontai_knowledge_base",
            persist_dir=str(storage_path("knowledge_db")),
        )
        return store
    except Exception as exc:
        logger.error("Failed to initialize VectorStore: %s", exc)
        raise HTTPException(status_code=503, detail="Vector store not available")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/ingest", response_model=IngestResponse)
async def ingest_knowledge(
    request: IngestRequest,
    engine: ContextEngine = Depends(_get_context_engine),
    vector_store: VectorStore = Depends(_get_vector_store),
) -> IngestResponse:
    """Ingest knowledge from a URL into the vector database.

    Supports GitHub repos, npm packages, PyPI packages, and general web pages.
    The content is fetched, cleaned, chunked, embedded, and stored in the
    knowledge base vector collection.
    """
    try:
        # Import the web fetcher
        from yontai.knowledge.web_fetcher import WebFetcher

        fetcher = WebFetcher()
    except ImportError:
        return IngestResponse(
            success=False,
            source_url=request.url,
            source_type=request.source_type or "unknown",
            files_fetched=0,
            chunks_indexed=0,
            errors=["WebFetcher module not available. Install httpx and beautifulsoup4."],
            summary="Ingestion failed: WebFetcher not available",
        )

    try:
        # Fetch code from URL
        fetched_files = await fetcher.fetch_from_url(request.url)

        if not fetched_files:
            # Fallback: try search-based approach
            logger.info("Direct fetch returned 0 files, trying search...")
            fetched_files = await fetcher.search_and_fetch(request.url, max_results=5)

        source_type = request.source_type or "web"
        if "github.com" in request.url:
            source_type = "github"
        elif "npmjs.com" in request.url or "npm" in request.url.lower():
            source_type = "npm"
        elif "pypi.org" in request.url or "pypi" in request.url.lower():
            source_type = "pypi"

        # Limit files
        fetched_files = fetched_files[: request.max_files]

        # Convert to CodeSnippets and index
        from yontai.rag.context_engine import CodeSnippet

        snippets: list[CodeSnippet] = []
        for ff in fetched_files:
            snippet = CodeSnippet(
                file_path=ff.file_path,
                symbol_name=ff.file_path.split("/")[-1],
                symbol_type="file",
                start_line=1,
                end_line=len(ff.content.split("\n")),
                content=ff.content[:5000],  # Limit content size
                language=ff.language,
                metadata={
                    "source_url": ff.source_url,
                    "source_type": source_type,
                    "hash": ff.hash,
                    "license": ff.license_info or "",
                },
            )
            snippets.append(snippet)

        # Index into vector store
        indexed_count = 0
        errors: list[str] = []
        if snippets:
            try:
                indexed_count = vector_store.index_snippets(snippets)
            except Exception as exc:
                errors.append(f"Vector store indexing error: {exc}")
                logger.error("Vector store indexing failed: %s", exc)

        # Build summary
        if indexed_count > 0:
            summary = f"Successfully ingested {len(fetched_files)} files ({indexed_count} chunks) from {request.url}"
        else:
            summary = f"No content was indexed from {request.url}"

        return IngestResponse(
            success=indexed_count > 0 or len(fetched_files) == 0,
            source_url=request.url,
            source_type=source_type,
            files_fetched=len(fetched_files),
            chunks_indexed=indexed_count,
            errors=errors,
            summary=summary,
        )

    except Exception as exc:
        logger.exception("Knowledge ingestion failed for URL: %s", request.url)
        return IngestResponse(
            success=False,
            source_url=request.url,
            source_type=request.source_type or "unknown",
            files_fetched=0,
            chunks_indexed=0,
            errors=[str(exc)],
            summary=f"Ingestion failed: {exc}",
        )
    finally:
        await fetcher.close()


@router.post("/search", response_model=SearchResponse)
async def search_knowledge(
    request: SearchRequest,
    vector_store: VectorStore = Depends(_get_vector_store),
) -> SearchResponse:
    """Search the knowledge base for relevant code snippets.

    Uses vector similarity search to find code related to the query.
    Optionally filter by language or source type.
    """
    try:
        # Build metadata filter
        filter_meta: dict[str, str] | None = None
        if request.language or request.source_type:
            filter_meta = {}
            if request.language:
                filter_meta["language"] = request.language
            if request.source_type:
                filter_meta["source_type"] = request.source_type

        # Search vector store
        results = vector_store.search(
            query=request.query,
            n_results=request.n_results,
            filter_metadata=filter_meta,
        )

        # Convert to response items
        items: list[SearchResultItem] = []
        for snippet in results:
            distance = snippet.metadata.get("distance", 0.0) if snippet.metadata else 0.0
            score = 1.0 - distance  # Convert distance to similarity score

            items.append(
                SearchResultItem(
                    file_path=snippet.file_path,
                    symbol_name=snippet.symbol_name,
                    symbol_type=snippet.symbol_type,
                    content=snippet.content[:1000],  # Truncate long content
                    language=snippet.language,
                    score=round(score, 4),
                    source_url=snippet.metadata.get("source_url") if snippet.metadata else None,
                )
            )

        return SearchResponse(
            results=items,
            total_results=len(items),
            query=request.query,
        )

    except Exception as exc:
        logger.exception("Knowledge search failed")
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}")


@router.get("/stats", response_model=KnowledgeStats)
async def knowledge_stats(
    vector_store: VectorStore = Depends(_get_vector_store),
) -> KnowledgeStats:
    """Get statistics about the knowledge base."""
    try:
        stats = vector_store.get_stats()
        total_chunks = stats.get("total_snippets", 0)

        # We can't easily get language/source type distribution from
        # ChromaDB without scanning all records. Return what we have.
        return KnowledgeStats(
            total_chunks=total_chunks,
            total_sources=0,
            languages={},
            source_types={},
        )
    except Exception as exc:
        logger.exception("Failed to get knowledge stats")
        raise HTTPException(status_code=500, detail=f"Stats failed: {exc}")


@router.delete("/clear", status_code=200)
async def clear_knowledge_base(
    vector_store: VectorStore = Depends(_get_vector_store),
) -> dict[str, Any]:
    """Clear all knowledge from the vector database.

    This deletes all records from the knowledge base collection.
    Each source will need to be re-ingested.
    """
    try:
        # ChromaDB doesn't have a bulk delete, so we use delete with no filter
        # which deletes all records in the collection
        collection_name = "yontai_knowledge_base"
        import chromadb
        from chromadb.config import Settings

        from yontai.core.paths import storage_path

        client = chromadb.PersistentClient(
            path=str(storage_path("knowledge_db")),
            settings=Settings(anonymized_telemetry=False),
        )

        deleted_count = 0
        try:
            collection = client.get_collection(name=collection_name)
            all_ids = collection.get()["ids"]
            if all_ids:
                # Delete in batches
                batch_size = 500
                for i in range(0, len(all_ids), batch_size):
                    batch = all_ids[i : i + batch_size]
                    collection.delete(ids=batch)
                    deleted_count += len(batch)
        except Exception:
            pass

        return {
            "success": True,
            "deleted_chunks": deleted_count,
            "message": f"Cleared {deleted_count} chunks from knowledge base",
        }

    except Exception as exc:
        logger.exception("Failed to clear knowledge base")
        raise HTTPException(status_code=500, detail=f"Clear failed: {exc}")
