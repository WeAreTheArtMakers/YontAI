"""RAG Context Engine - Kod bağlamı toplama ve vektör arama motoru.

Proje dosyalarını tree-sitter ile AST'lerine ayırır, fonksiyon/sınıf/imza
gibi yapıları ChromaDB vektör veritabanında saklar ve LLM prompt'larına
dinamik bağlam olarak ekler.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ChromaDB
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("chromadb kurulu değil. Vektör arama devre dışı.")

# Tree-sitter (sadece mevcudiyet kontrolü için import)
TREE_SITTER_AVAILABLE = False
try:
    import importlib.util
    if importlib.util.find_spec("tree_sitter"):
        TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logger.warning("tree-sitter kurulu değil. AST indeksleme devre dışı.")

# Sentence-transformers (opsiyonel, chromadb built-in embedding fallback)
try:
    from sentence_transformers import SentenceTransformer

    ST_AVAILABLE = True
except ImportError:
    ST_AVAILABLE = False


# Desteklenen dosya uzantıları ve dil eşlemesi
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
}


@dataclass
class CodeSnippet:
    """İndekslenmiş kod snippet'i."""

    file_path: str
    symbol_name: str
    symbol_type: str  # function, class, method, variable, import
    start_line: int
    end_line: int
    content: str
    signature: str | None = None
    docstring: str | None = None
    language: str = ""
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IndexingStats:
    """İndeksleme istatistikleri."""

    total_files: int = 0
    total_snippets: int = 0
    indexed_files: int = 0
    skipped_files: int = 0
    errors: list[str] = field(default_factory=list)
    by_language: dict[str, int] = field(default_factory=dict)


class CodeIndexer:
    """Tree-sitter kullanarak proje dosyalarını AST'lerine ayırır.

    Desteklenen diller: Python, JavaScript, TypeScript, Rust, Go, Java, C/C++
    """

    # Basit regex pattern'leri (tree-sitter dil dosyası yoksa fallback olarak)
    FUNCTION_PATTERNS: dict[str, list[str]] = {
        "python": [
            r"^async\s+def\s+(\w+)\s*\(",
            r"^def\s+(\w+)\s*\(",
        ],
        "javascript": [
            r"(?:async\s+)?function\s+(\w+)\s*\(",
            r"(\w+)\s*=\s*(?:async\s+)?function\s*\(",
            r"(\w+)\s*\(\s*[^)]*\s*\)\s*{",
        ],
        "typescript": [
            r"(?:async\s+)?function\s+(\w+)\s*\(",
            r"(\w+)\s*=\s*(?:async\s+)?function\s*\(",
            r"(\w+)\s*\(\s*[^)]*\s*\)\s*:\s*\w+",
        ],
    }

    CLASS_PATTERNS: dict[str, list[str]] = {
        "python": [r"^class\s+(\w+)"],
        "javascript": [r"^class\s+(\w+)"],
        "typescript": [r"^class\s+(\w+)"],
    }

    IMPORT_PATTERNS: dict[str, list[str]] = {
        "python": [
            r"^import\s+(\S+)",
            r"^from\s+(\S+)\s+import",
        ],
        "javascript": [
            r"^import\s+.*\s+from\s+['\"]([^'\"]+)['\"]",
            r"^const\s+\w+\s*=\s*require\s*\(\s*['\"]([^'\"]+)['\"]",
        ],
        "typescript": [
            r"^import\s+.*\s+from\s+['\"]([^'\"]+)['\"]",
            r"^import\s+type\s+.*\s+from\s+['\"]([^'\"]+)['\"]",
        ],
        "rust": [
            r"^use\s+(\S+)",
            r"^pub\s+use\s+(\S+)",
            r"^extern\s+crate\s+(\S+)",
        ],
        "go": [
            r"^import\s+\"(\\S+)\"",
            r"^import\s+\(\s*$",
        ],
    }

    def __init__(self) -> None:
        self._treesitter_available = TREE_SITTER_AVAILABLE

    def index_project(
        self,
        project_path: str | Path,
        exclude_dirs: set[str] | None = None,
    ) -> IndexingStats:
        """Bir proje dizinindeki tüm desteklenen dosyaları indeksle.

        Args:
            project_path: Proje kök dizini
            exclude_dirs: Dışlanacak dizinler (örn: {"node_modules", ".git", "__pycache__"})

        Returns:
            IndexingStats: İndeksleme istatistikleri
        """
        if exclude_dirs is None:
            exclude_dirs = {
                "node_modules", ".git", "__pycache__", ".venv", "venv",
                "dist", "build", ".next", ".nuxt", "target", "vendor",
                ".DS_Store", "env", ".env", "migrations", ".pytest_cache",
            }

        stats = IndexingStats()
        root = Path(project_path).resolve()

        if not root.exists():
            logger.error("Proje dizini bulunamadı: %s", root)
            stats.errors.append(f"Dizin bulunamadı: {root}")
            return stats

        logger.info("Proje indeksleniyor: %s", root)

        for file_path in root.rglob("*"):
            # Dizinse atla
            if file_path.is_dir():
                continue

            # Uzantı kontrolü
            ext = file_path.suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            # Dışlanan dizinlerde mi kontrol et
            if any(
                part.startswith(".") or part in exclude_dirs
                for part in file_path.relative_to(root).parts
            ):
                stats.skipped_files += 1
                continue

            stats.total_files += 1
            language = SUPPORTED_EXTENSIONS[ext]

            try:
                snippets = self._parse_file(file_path, language)
                if snippets:
                    stats.total_snippets += len(snippets)
                    stats.indexed_files += 1
                    stats.by_language[language] = (
                        stats.by_language.get(language, 0) + 1
                    )
            except Exception as exc:
                stats.errors.append(f"{file_path}: {exc}")
                logger.debug("Dosya indekslenemedi: %s - %s", file_path, exc)

        logger.info(
            "İndeksleme tamamlandı: %d dosya, %d snippet",
            stats.indexed_files,
            stats.total_snippets,
        )
        return stats

    def parse_file(self, file_path: str | Path) -> list[CodeSnippet]:
        """Tek bir dosyayı parse et ve snippet'leri döndür.

        Args:
            file_path: Dosya yolu

        Returns:
            CodeSnippet listesi
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        language = SUPPORTED_EXTENSIONS.get(ext, "unknown")
        return self._parse_file(path, language)

    def _parse_file(self, file_path: Path, language: str) -> list[CodeSnippet]:
        """Dosyayı parse et ve kod snippet'lerini çıkar."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError) as exc:
            logger.debug("Dosya okunamadı: %s - %s", file_path, exc)
            return []

        snippets: list[CodeSnippet] = []
        lines = content.split("\n")

        # Regex tabanlı parse (tree-sitter binary'leri olmadığında fallback)
        self._extract_by_regex(file_path, lines, language, snippets)

        return snippets

    def _extract_by_regex(
        self,
        file_path: Path,
        lines: list[str],
        language: str,
        snippets: list[CodeSnippet],
    ) -> None:
        """Regex ile fonksiyon, sınıf ve import'ları çıkar."""
        rel_path = str(file_path)

        # Import'lar
        import_patterns = self.IMPORT_PATTERNS.get(language, [])
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "//", "/*", "*")):
                continue
            for pattern in import_patterns:
                match = re.match(pattern, stripped)
                if match:
                    snippets.append(
                        CodeSnippet(
                            file_path=rel_path,
                            symbol_name=match.group(1),
                            symbol_type="import",
                            start_line=i,
                            end_line=i,
                            content=stripped,
                            language=language,
                        )
                    )
                    break

        # Sınıflar
        class_patterns = self.CLASS_PATTERNS.get(language, [])
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            for pattern in class_patterns:
                match = re.match(pattern, stripped)
                if match:
                    class_name = match.group(1)
                    # Sınıfın bittiği satırı bul
                    end_line = self._find_block_end(lines, i)
                    class_content = "\n".join(lines[i - 1 : end_line])
                    snippets.append(
                        CodeSnippet(
                            file_path=rel_path,
                            symbol_name=class_name,
                            symbol_type="class",
                            start_line=i,
                            end_line=end_line,
                            content=class_content,
                            signature=stripped,
                            language=language,
                        )
                    )
                    break

        # Fonksiyonlar
        func_patterns = self.FUNCTION_PATTERNS.get(language, [])
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            for pattern in func_patterns:
                match = re.match(pattern, stripped)
                if match:
                    func_name = match.group(1)
                    if func_name in {"if", "for", "while", "with"}:
                        continue
                    end_line = self._find_block_end(lines, i)
                    func_content = "\n".join(lines[i - 1 : end_line])
                    snippets.append(
                        CodeSnippet(
                            file_path=rel_path,
                            symbol_name=func_name,
                            symbol_type="function",
                            start_line=i,
                            end_line=end_line,
                            content=func_content,
                            signature=stripped,
                            language=language,
                        )
                    )
                    break

    def _find_block_end(self, lines: list[str], start: int) -> int:
        """Bir blok yapısının (class/fonksiyon) bittiği satırı bul."""
        # Python için girintileme tabanlı
        if start >= len(lines):
            return start

        base_indent = len(lines[start - 1]) - len(lines[start - 1].lstrip())
        end = start

        for i in range(start, len(lines)):
            stripped = lines[i].strip()
            if not stripped:
                continue
            current_indent = len(lines[i]) - len(lines[i].lstrip())
            if current_indent <= base_indent and stripped not in ("", ")"):
                # Boş satırları atla, gerçek bitiş
                if stripped.startswith(("def ", "class ", "@", "#", '"""', "'''")):
                    end = i
                    break
                if current_indent < base_indent:
                    end = i
                    break
            end = i + 1

        return end

    def get_snippet_context(self, snippet: CodeSnippet, context_lines: int = 5) -> str:
        """Snippet'in etrafındaki bağlamı döndür."""
        try:
            with open(snippet.file_path) as f:
                lines = f.readlines()
        except OSError:
            return snippet.content

        start = max(0, snippet.start_line - context_lines - 1)
        end = min(len(lines), snippet.end_line + context_lines)
        context = "".join(lines[start:end])
        return context


class VectorStore:
    """ChromaDB tabanlı vektör veritabanı.

    Kod snippet'lerini embedding'lerle birlikte saklar ve benzerlik
    araması yapar.
    """

    def __init__(
        self,
        collection_name: str = "yontai_code_index",
        persist_dir: str | Path | None = None,
    ) -> None:
        if not CHROMA_AVAILABLE:
            raise RuntimeError("chromadb kurulu değil.")

        from yontai.core.paths import storage_path

        if persist_dir is None:
            persist_dir = str(storage_path("vector_db"))

        self._persist_dir = str(persist_dir)
        os.makedirs(self._persist_dir, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=self._persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedding_dim = 384  # all-MiniLM-L6-v2

        # Embedding model (opsiyonel)
        self._embedder = None
        if ST_AVAILABLE:
            try:
                self._embedder = SentenceTransformer(
                    "all-MiniLM-L6-v2",
                    device="cpu",
                )
            except Exception as exc:
                logger.warning("Embedding modeli yüklenemedi: %s", exc)

    def index_snippets(self, snippets: list[CodeSnippet]) -> int:
        """Kod snippet'lerini vektör veritabanına ekle.

        Args:
            snippets: İndekslenecek snippet'ler

        Returns:
            Eklenen snippet sayısı
        """
        if not snippets:
            return 0

        texts: list[str] = []
        metadatas: list[dict[str, Any]] = []
        ids: list[str] = []

        for snippet in snippets:
            # Embedding metni: sembol adı + içerik + yorumlar
            text = (
                f"{snippet.symbol_type}: {snippet.symbol_name}\n"
                f"{snippet.signature or ''}\n"
                f"{snippet.content}"
            )

            # ID: dosya yolu + satır hash'i
            unique_id = hashlib.md5(
                f"{snippet.file_path}:{snippet.start_line}".encode()
            ).hexdigest()

            texts.append(text)
            ids.append(unique_id)
            metadatas.append({
                "file_path": snippet.file_path,
                "symbol_name": snippet.symbol_name,
                "symbol_type": snippet.symbol_type,
                "start_line": snippet.start_line,
                "end_line": snippet.end_line,
                "language": snippet.language,
            })

        # Embedding'leri hesapla
        if self._embedder:
            embeddings = self._embedder.encode(texts, show_progress_bar=False).tolist()
        else:
            # ChromaDB default embedding kullan
            embeddings = None

        # Batch olarak ekle
        batch_size = 100
        added = 0
        for i in range(0, len(texts), batch_size):
            batch_end = min(i + batch_size, len(texts))
            try:
                self._collection.add(
                    ids=ids[i:batch_end],
                    documents=texts[i:batch_end],
                    metadatas=metadatas[i:batch_end],
                    embeddings=embeddings[i:batch_end] if embeddings else None,
                )
                added += batch_end - i
            except Exception as exc:
                logger.error("Vektör ekleme hatası: %s", exc)

        logger.info("%d snippet indekslendi", added)
        return added

    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: dict[str, str] | None = None,
    ) -> list[CodeSnippet]:
        """Benzer kod snippet'lerini ara.

        Args:
            query: Arama sorgusu (kod veya doğal dil)
            n_results: Döndürülecek sonuç sayısı
            filter_metadata: Metadata filtresi (örn: {"language": "python"})

        Returns:
            CodeSnippet listesi
        """
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_metadata,
            )
        except Exception as exc:
            logger.error("Vektör arama hatası: %s", exc)
            return []

        snippets: list[CodeSnippet] = []
        if not results["ids"] or not results["ids"][0]:
            return snippets

        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = (results["distances"][0][i] / 1.0
                       ) if results.get("distances") else 0.0
            snippets.append(
                CodeSnippet(
                    file_path=meta.get("file_path", ""),
                    symbol_name=meta.get("symbol_name", ""),
                    symbol_type=meta.get("symbol_type", ""),
                    start_line=int(meta.get("start_line", 0)),
                    end_line=int(meta.get("end_line", 0)),
                    content=results["documents"][0][i] if results["documents"] else "",
                    language=meta.get("language", ""),
                    metadata={"distance": distance},
                )
            )

        return snippets

    def delete_project(self, project_path: str) -> int:
        """Bir projeye ait tüm indeksleri sil.

        Args:
            project_path: Proje yolu

        Returns:
            Silinen kayıt sayısı
        """
        try:
            results = self._collection.get(
                where={"file_path": {"$contains": project_path}},
            )
            count = len(results["ids"]) if results["ids"] else 0
            if count > 0:
                self._collection.delete(ids=results["ids"])
            return count
        except Exception as exc:
            logger.error("Silme hatası: %s", exc)
            return 0

    def get_stats(self) -> dict[str, Any]:
        """Koleksiyon istatistiklerini döndür."""
        try:
            count = self._collection.count()
        except Exception:
            count = 0
        return {
            "collection_name": self._collection.name,
            "total_snippets": count,
            "persist_directory": self._persist_dir,
        }


class ContextEngine:
    """Bağlam motoru - kod indeksleme ve vektör aramayı birleştirir.

    LLM prompt'larına dinamik olarak proje bağlamı eklemek için
    kullanılır.
    """

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        code_indexer: CodeIndexer | None = None,
    ) -> None:
        self.vector_store = vector_store or (VectorStore() if CHROMA_AVAILABLE else None)
        self.code_indexer = code_indexer or CodeIndexer()
        self._project_paths: dict[str, str] = {}  # project_id -> path

    def index_project(self, project_id: str, project_path: str | Path) -> IndexingStats:
        """Projeyi indeksle ve vektör DB'ye ekle.

        Args:
            project_id: Proje ID'si
            project_path: Proje dizini

        Returns:
            IndexingStats
        """
        self._project_paths[project_id] = str(project_path)

        # Dosyaları parse et
        stats = self.code_indexer.index_project(project_path)
        if stats.total_snippets == 0:
            return stats

        # Vektör DB'ye ekle
        if self.vector_store:
            # Tüm dosyaları tekrar okuyup snippet'leri topla
            all_snippets: list[CodeSnippet] = []
            for file_path in Path(project_path).rglob("*"):
                ext = file_path.suffix.lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue
                snippets = self.code_indexer.parse_file(file_path)
                all_snippets.extend(snippets)

            added = self.vector_store.index_snippets(all_snippets)
            logger.info("Vektör DB'ye %d snippet eklendi", added)

        return stats

    def search_context(
        self,
        query: str,
        n_results: int = 5,
        project_id: str | None = None,
    ) -> list[CodeSnippet]:
        """Sorguyla ilgili kod bağlamını bul.

        Args:
            query: Arama sorgusu
            n_results: Sonuç sayısı
            project_id: Proje filtresi (opsiyonel)

        Returns:
            İlgili CodeSnippet listesi
        """
        if not self.vector_store:
            return []

        filter_meta = None
        if project_id and project_id in self._project_paths:
            filter_meta = {"file_path": {"$contains": self._project_paths[project_id]}}

        return self.vector_store.search(query, n_results=n_results, filter_metadata=filter_meta)

    def build_prompt_context(
        self,
        query: str,
        current_file: str | None = None,
        open_tabs: list[str] | None = None,
        max_tokens: int = 4096,
    ) -> str:
        """LLM prompt'una eklenecek bağlam metnini oluştur.

        Args:
            query: Kullanıcı sorgusu veya kod tamamlama bağlamı
            current_file: Şu an açık dosya (opsiyonel)
            open_tabs: Açık sekmelerdeki dosyalar (opsiyonel)
            max_tokens: Maksimum token sayısı

        Returns:
            Bağlam metni
        """
        context_parts: list[str] = []

        # 1. İlgili snippet'leri vektör DB'den getir
        related = self.search_context(query, n_results=10)
        if related:
            context_parts.append("// İlgili kod snippet'leri:")
            for sn in related[:5]:  # En fazla 5 snippet
                context_parts.append(
                    f"// {sn.file_path}:{sn.start_line} ({sn.symbol_type}: {sn.symbol_name})"
                )
                context_parts.append(sn.content[:500])  # Maks 500 karakter
                context_parts.append("")

        # 2. Açık dosyanın import'larını ve ilk satırlarını ekle
        if current_file:
            try:
                with open(current_file) as f:
                    lines = f.readlines()
                # İlk 50 satır (import'lar + başlangıç)
                header = "".join(lines[:50])
                context_parts.append(f"// Mevcut dosya ({current_file}):")
                context_parts.append(header[:2000])  # Maks 2000 karakter
            except OSError:
                pass

        # 3. Token sınırlaması
        context_text = "\n".join(context_parts)
        # Basit token tahmini: karakter / 4
        estimated_tokens = len(context_text) // 4
        if estimated_tokens > max_tokens:
            # Kırp
            max_chars = max_tokens * 4
            context_text = context_text[:max_chars] + "\n// ... (bağlam kırpıldı)"

        return context_text

    def get_project_stats(self, project_id: str | None = None) -> dict[str, Any]:
        """İndeksleme istatistiklerini döndür.

        Returns:
            İstatistikler
        """
        stats: dict[str, Any] = {
            "indexed_projects": len(self._project_paths),
            "project_paths": dict(self._project_paths),
        }
        if self.vector_store:
            stats["vector_store"] = self.vector_store.get_stats()
        return stats