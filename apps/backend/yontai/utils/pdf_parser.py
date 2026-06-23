"""PDF text extraction utilities."""

from pathlib import Path
from typing import BinaryIO

try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


def extract_text_from_pdf(file: BinaryIO | Path) -> str:
    """
    Extract text content from a PDF file.
    
    Args:
        file: File-like object or path to PDF file
        
    Returns:
        Extracted text content
        
    Raises:
        ImportError: If pypdf is not installed
        Exception: If PDF cannot be read
    """
    if not PDF_AVAILABLE:
        raise ImportError(
            "pypdf is not installed. Install with: pip install pypdf"
        )
    
    try:
        reader = PdfReader(file)
        text_parts = []
        
        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            if text.strip():
                text_parts.append(f"--- Page {page_num} ---\n{text}")
        
        return "\n\n".join(text_parts)
    
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF: {str(e)}") from e


def get_pdf_metadata(file: BinaryIO | Path) -> dict[str, str | int]:
    """
    Extract metadata from a PDF file.
    
    Args:
        file: File-like object or path to PDF file
        
    Returns:
        Dictionary with metadata (title, author, pages, etc.)
    """
    if not PDF_AVAILABLE:
        raise ImportError("pypdf is not installed")
    
    try:
        reader = PdfReader(file)
        metadata = reader.metadata or {}
        
        return {
            "title": metadata.get("/Title", ""),
            "author": metadata.get("/Author", ""),
            "subject": metadata.get("/Subject", ""),
            "creator": metadata.get("/Creator", ""),
            "producer": metadata.get("/Producer", ""),
            "pages": len(reader.pages),
        }
    
    except Exception as e:
        raise Exception(f"Failed to extract PDF metadata: {str(e)}") from e
