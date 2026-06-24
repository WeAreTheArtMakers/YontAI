"""API routes for RAG (Retrieval-Augmented Generation) operations.

Provides endpoints for:
- POST /rag/index    - Index a project directory for RAG
- POST /rag/search   - Search indexed code via vector similarity
- POST /rag/context  - Build context for a prompt
- GET  /rag/stats    - Get RAG indexing statistics

Architecture (from ARCHITECTURE.md §4):
    Project → CodeIndexer → VectorStore → ContextEngine → Prompt Assembly
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from yontai.rag.context_engine import CodeIndexer, ContextEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class IndexRequest(BaseModel):
    """Request body for indexing a project."""

    project_id: str = Field(..., description="Unique project identifier")
    project_path: str = Field(..., description="Absolute path to the project directory")
    exclude_dirs: list[str] | None = Field(
        default=None,
        description="Additional directories to exclude from indexing",
    )


class IndexResponse(BaseModel):
    """Response from a project indexing request."""

    success: bool
    project_id: str
    project_path: str
    total_files: int
    total_snippets: int
    indexed_files: int
    skipped_files: int
    by_language: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    summary: str = ""


class SearchRequest(BaseModel):
    """Request body for searching indexed code."""

    query: str = Field(..., min_length=2, description="Search query (code or natural language)")
    n_results: int = Field(default=5, ge=1, le=50, description="Number of results to return")
    project_id: str | None = Field(default=None, description="Filter by project")
    language: str | None = Field(default=None, description="Filter by language")


class SearchResultItem(BaseModel):
    """A single search result item."""

    file_path: str
    symbol_name: str
    symbol_type: str
    start_line: int
    end_line: int
    content: str
    language: str
    score: float = 0.0


class SearchResponse(BaseModel):
    """Response from a code search request."""

    results: list[SearchResultItem]
    total_results: int
    query: str


class ContextRequest(BaseModel):
    """Request body for building a prompt context."""

    query: str = Field(..., description="The user query to build context for")
    current_file: str | None = Field(default=None, description="Path to the currently open file")
    max_tokens: int = Field(default=2048, ge=256, le=8192, description="Maximum context token budget")  # noqa: E501
    project_id: str | None = Field(default=None, description="Filter context to a specific project")


class ContextResponse(BaseModel):
    """Response containing assembled context."""

    context: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    estimated_tokens: int = 0
    truncated: bool = False


class RAGStats(BaseModel):
    """RAG system statistics."""

    indexed_projects: int = 0
    project_paths: dict[str, str] = Field(default_factory=dict)
    vector_store: dict[str, Any] = Field(default_factory=dict)
    languages: dict[str, int] = Field(default_factory=dict)

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def _get_context_engine() -> ContextEngine:
    """Get or create the ContextEngine singleton."""
    try:
        return ContextEngine()
    except Exception as exc:
        logger.error("Failed to initialize ContextEngine: %s", exc)
        raise HTTPException(status_code=503, detail="RAG engine not available") from exc


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/index", response_model=IndexResponse)
async def index_project(
    request: IndexRequest,
    engine: ContextEngine = Depends(_get_context_engine),
) -> IndexResponse:
    """Index a project directory for RAG-based code retrieval.

    Scans all supported source files, extracts functions/classes/imports
    via tree-sitter (or regex fallback), embeds them, and stores in the
    vector database for similarity search.

    Supported languages: Python, JavaScript, TypeScript, Rust, Go,
    Java, C/C++, Ruby, Swift, Kotlin, Scala, PHP.
    """
    from pathlib import Path

    project_path = Path(request.project_path)
    if not project_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project path does not exist: {request.project_path}",
        )
    if not project_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Project path is not a directory: {request.project_path}",
        )

    try:
        # Build exclude set from defaults + user overrides
        exclude_dirs: set[str] = {
            "node_modules", ".git", "__pycache__", ".venv", "venv",
            "dist", "build", ".next", ".nuxt", "target", "vendor",
            ".DS_Store", "env", ".env", "migrations", ".pytest_cache",
            "coverage", ".coverage", ".mypy_cache", ".ruff_cache",
        }
        if request.exclude_dirs:
            exclude_dirs.update(request.exclude_dirs)

        # Index using the code indexer directly for fine-grained control
        indexer = CodeIndexer()
        stats = indexer.index_project(project_path, exclude_dirs=exclude_dirs)

        # Also make context engine aware of this project
        engine.index_project(request.project_id, project_path)

        # Build summary
        if stats.total_snippets > 0:
            summary = (
                f"Indexed {stats.indexed_files} files ({stats.total_snippets} snippets) "
                f"from {request.project_id}. "
                f"Skipped {stats.skipped_files} files."
            )
        else:
            summary = (
                f"No supported source files found in {request.project_path}. "
                "Supported extensions: .py, .js, .ts, .rs, .go, .java, .cpp, etc."
            )

        return IndexResponse(
            success=stats.total_snippets > 0 or stats.skipped_files > 0,
            project_id=request.project_id,
            project_path=str(project_path),
            total_files=stats.total_files,
            total_snippets=stats.total_snippets,
            indexed_files=stats.indexed_files,
            skipped_files=stats.skipped_files,
            by_language=dict(stats.by_language),
            errors=list(stats.errors),
            summary=summary,
        )

    except Exception as exc:
        logger.exception("Project indexing failed for: %s", request.project_path)
        raise HTTPException(status_code=500, detail=f"Indexing failed: {exc}") from exc


@router.post("/search", response_model=SearchResponse)
async def search_code(
    request: SearchRequest,
    engine: ContextEngine = Depends(_get_context_engine),
) -> SearchResponse:
    """Search indexed project code using vector similarity.

    Finds relevant functions, classes, and code snippets matching the
    query. Results are ordered by semantic similarity score.

    Use this endpoint to find relevant code context before asking
    the model a question about a specific codebase.
    """
    try:
        snippets = engine.search_context(
            query=request.query,
            n_results=request.n_results,
            project_id=request.project_id,
        )

        # Optionally filter by language
        if request.language and snippets:
            snippets = [s for s in snippets if s.language == request.language]

        items: list[SearchResultItem] = []
        for snippet in snippets:
            # Extract distance from metadata if available
            distance = snippet.metadata.get("distance", 0.0) if snippet.metadata else 0.0
            score = 1.0 - distance

            items.append(
                SearchResultItem(
                    file_path=snippet.file_path,
                    symbol_name=snippet.symbol_name,
                    symbol_type=snippet.symbol_type,
                    start_line=snippet.start_line,
                    end_line=snippet.end_line,
                    content=snippet.content[:2000],  # Truncate long content
                    language=snippet.language,
                    score=round(score, 4),
                )
            )

        # Sort by score descending
        items.sort(key=lambda x: x.score, reverse=True)

        return SearchResponse(
            results=items,
            total_results=len(items),
            query=request.query,
        )

    except Exception as exc:
        logger.exception("Code search failed")
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc


@router.post("/context", response_model=ContextResponse)
async def build_context(
    request: ContextRequest,
    engine: ContextEngine = Depends(_get_context_engine),
) -> ContextResponse:
    """Build an optimised context string for LLM prompt injection.

    Assembles context from:
    1. Vector DB search results (top 10 snippets)
    2. Current file imports and headers (if provided)
    3. Project dependency graph context (if available)

    The context is token-budget aware and will be truncated to
    fit within `max_tokens`.

    Use this endpoint to enrich prompts with relevant code context
    before sending them to the chat/completion API.
    """
    try:
        # Build prompt context
        context_text = engine.build_prompt_context(
            query=request.query,
            current_file=request.current_file,
            max_tokens=request.max_tokens,
        )

        # Get source details
        snippets = engine.search_context(
            query=request.query,
            n_results=5,
            project_id=request.project_id,
        )

        sources: list[dict[str, Any]] = []
        for snippet in snippets:
            sources.append({
                "file_path": snippet.file_path,
                "symbol_name": snippet.symbol_name,
                "symbol_type": snippet.symbol_type,
                "start_line": snippet.start_line,
                "end_line": snippet.end_line,
                "language": snippet.language,
            })

        # Estimate tokens (rough heuristic: chars / 4)
        estimated_tokens = len(context_text) // 4
        truncated = estimated_tokens > request.max_tokens

        return ContextResponse(
            context=context_text,
            sources=sources,
            estimated_tokens=estimated_tokens,
            truncated=truncated,
        )

    except Exception as exc:
        logger.exception("Context building failed")
        raise HTTPException(status_code=500, detail=f"Context building failed: {exc}") from exc


@router.get("/stats", response_model=RAGStats)
async def rag_stats(
    engine: ContextEngine = Depends(_get_context_engine),
) -> RAGStats:
    """Get RAG system statistics.

    Returns information about indexed projects, vector store status,
    and language distribution.
    """
    try:
        stats = engine.get_project_stats()

        return RAGStats(
            indexed_projects=stats.get("indexed_projects", 0),
            project_paths=stats.get("project_paths", {}),
            vector_store=stats.get("vector_store", {}),
            languages={},  # Could be enriched from vector store metadata
        )

    except Exception as exc:
        logger.exception("Failed to get RAG stats")
        raise HTTPException(status_code=500, detail=f"Stats failed: {exc}") from exc


@router.delete("/project/{project_id}", status_code=200)
async def delete_project_index(
    project_id: str,
    engine: ContextEngine = Depends(_get_context_engine),
) -> dict[str, Any]:
    """Delete a project's index from the vector database.

    This removes all indexed snippets associated with the project.
    The project will need to be re-indexed before RAG context is available.
    """
    try:
        # Get the project path
        project_stats = engine.get_project_stats()
        project_paths = project_stats.get("project_paths", {})

        if project_id not in project_paths:
            raise HTTPException(
                status_code=404,
                detail=f"Project not found: {project_id}",
            )

        # Delete from vector store
        deleted = 0
        if engine.vector_store:
            deleted = engine.vector_store.delete_project(project_paths[project_id])

        return {
            "success": True,
            "project_id": project_id,
            "deleted_snippets": deleted,
            "message": f"Deleted index for project {project_id} ({deleted} snippets removed)",
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to delete project index")
        raise HTTPException(status_code=500, detail=f"Delete failed: {exc}") from exc
