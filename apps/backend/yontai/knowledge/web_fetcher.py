"""
Web Fetcher for code ingestion.
Fetches code from GitHub repos, npm packages, PyPI packages,
and extracts code blocks from web pages with hash-based deduplication.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class FetchedCode:
    """Single code snippet fetched from a source."""

    source_url: str
    language: str
    code: str
    file_path: str | None = None
    checksum: str = ""

    def __post_init__(self) -> None:
        if not self.checksum:
            self.checksum = hashlib.sha256(self.code.encode("utf-8")).hexdigest()[:16]


@dataclass
class IngestionResult:
    """Result of a complete ingestion operation."""

    total_fetched: int = 0
    total_after_dedup: int = 0
    total_after_security: int = 0
    items: list[FetchedCode] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Security patterns — block sensitive / dangerous content
# ---------------------------------------------------------------------------

_SECURITY_BLOCK_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)(?:BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY)"),
    re.compile(r"(?i)(?:ghp_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{22,})"),
    re.compile(r"(?i)(?:sk-[a-zA-Z0-9]{20,})"),  # OpenAI-like API keys
    re.compile(r"(?i)(?:AKIA[0-9A-Z]{16})"),  # AWS access key IDs
    re.compile(r"(?i)password\s*=\s*['\"][^'\"]+['\"]"),
    re.compile(r"(?i)secret\s*=\s*['\"][^'\"]+['\"]"),
    re.compile(
        r"(?i)(?:api[_-]?key|apikey)\s*[:=]\s*['\"][^'\"]+['\"]"
    ),
]

_CODE_BLOCK_RE = re.compile(
    r"```(\w+)?\s*\n(.*?)```", re.DOTALL
)

# ---------------------------------------------------------------------------
# WebFetcher
# ---------------------------------------------------------------------------


class WebFetcher:
    """Fetches code from GitHub, npm, PyPI and arbitrary web pages."""

    GITHUB_API = "https://api.github.com"
    COMMON_CODE_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java",
        ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".swift", ".kt",
        ".scala", ".r", ".sql", ".sh", ".yaml", ".yml", ".json",
        ".toml", ".cfg", ".ini", ".md", ".css", ".scss", ".html",
        ".vue", ".svelte", ".lua", ".dart", ".zig", ".nim",
    }
    MAX_FILE_SIZE = 512 * 1024  # 512 KB
    MAX_PAGE_SIZE = 2 * 1024 * 1024  # 2 MB for HTML

    def __init__(
        self,
        github_token: str | None = None,
        client_timeout: float = 30.0,
        max_concurrent: int = 10,
    ) -> None:
        self._github_token = github_token
        self._client: httpx.AsyncClient | None = None
        self._timeout = client_timeout
        self._max_concurrent = max_concurrent
        self._seen_checksums: set[str] = set()

    # -- lifecycle ---------------------------------------------------------

    async def __aenter__(self) -> WebFetcher:
        headers: dict[str, str] = {
            "User-Agent": "YontAI/1.0",
            "Accept": "application/vnd.github.v3+json",
        }
        if self._github_token:
            headers["Authorization"] = f"Bearer {self._github_token}"
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(self._timeout),
            limits=httpx.Limits(max_keepalive_connections=self._max_concurrent),
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client is not None:
            await self._client.aclose()

    # -- public ingestion methods ------------------------------------------

    async def ingest_github_repo(
        self,
        owner: str,
        repo: str,
        path: str = "",
        branch: str = "main",
        max_files: int = 100,
    ) -> IngestionResult:
        """Fetch code files from a GitHub repository tree."""
        result = IngestionResult()
        assert self._client is not None

        try:
            contents_url = (
                f"{self.GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}"
                f"?recursive=1"
            )
            resp = await self._client.get(contents_url)
            resp.raise_for_status()
            tree = resp.json().get("tree", [])
        except httpx.HTTPError as exc:
            result.errors.append(f"GitHub tree fetch failed: {exc}")
            return result

        # Filter to blob entries under the desired path with valid extensions
        blobs = [
            entry
            for entry in tree
            if entry.get("type") == "blob"
            and entry["path"].startswith(path)
            and any(entry["path"].endswith(ext) for ext in self.COMMON_CODE_EXTENSIONS)
        ]

        blobs = blobs[:max_files]

        for blob in blobs:
            try:
                raw_url = (
                    f"https://raw.githubusercontent.com/{owner}/{repo}/"
                    f"{branch}/{blob['path']}"
                )
                resp = await self._client.get(raw_url)
                resp.raise_for_status()
                code = resp.text

                inner = self._process_snippet(
                    source_url=raw_url,
                    language=self._guess_language(blob["path"]),
                    code=code,
                    file_path=blob["path"],
                )
                if inner is not None:
                    result.items.append(inner)
                    result.total_fetched += 1
            except httpx.HTTPError as exc:
                result.errors.append(f"Failed to fetch {blob['path']}: {exc}")

        result.total_after_dedup = result.total_fetched
        result.total_after_security = len(result.items)
        return result

    async def ingest_npm_package(
        self,
        package_name: str,
        max_files: int = 50,
    ) -> IngestionResult:
        """Fetch source code from an npm package via unpkg CDN."""
        return await self._ingest_registry_package(
            registry_type="npm",
            package_name=package_name,
            base_cdn=f"https://unpkg.com/{package_name}/",
            max_files=max_files,
        )

    async def ingest_pypi_package(
        self,
        package_name: str,
        max_files: int = 50,
    ) -> IngestionResult:
        """Fetch source code from a PyPI package via files.pythonhosted.org."""
        return await self._ingest_registry_package(
            registry_type="pypi",
            package_name=package_name,
            base_cdn=f"https://files.pythonhosted.org/packages/source/{package_name[0]}/{package_name}/",
            max_files=max_files,
        )

    async def ingest_web_page(
        self,
        url: str,
        extract_code_blocks: bool = True,
    ) -> IngestionResult:
        """Fetch a web page and extract code blocks from its HTML."""
        result = IngestionResult()
        assert self._client is not None

        try:
            resp = await self._client.get(url, follow_redirects=True)
            resp.raise_for_status()
            html = resp.text
        except httpx.HTTPError as exc:
            result.errors.append(f"Page fetch failed: {exc}")
            return result

        if not extract_code_blocks:
            return result

        for match in _CODE_BLOCK_RE.finditer(html):
            lang = match.group(1) or "text"
            code = match.group(2).strip()
            if not code:
                continue

            inner = self._process_snippet(
                source_url=url,
                language=lang,
                code=code,
            )
            if inner is not None:
                result.items.append(inner)
                result.total_fetched += 1

        result.total_after_dedup = result.total_fetched
        result.total_after_security = len(result.items)
        return result

    # -- internal helpers --------------------------------------------------

    async def _ingest_registry_package(
        self,
        registry_type: str,
        package_name: str,
        base_cdn: str,
        max_files: int,
    ) -> IngestionResult:
        """Common logic for npm / PyPI ingestion."""
        result = IngestionResult()
        assert self._client is not None

        # Try to fetch a listing from the CDN root
        try:
            resp = await self._client.get(base_cdn)
            resp.raise_for_status()
            # CDNs often return directory listing as HTML or JSON; we try JSON first
            try:
                listing: list[dict[str, Any]] = resp.json()
            except Exception:
                result.errors.append(
                    f"Cannot parse directory listing for {package_name}"
                )
                return result
        except httpx.HTTPError as exc:
            result.errors.append(
                f"{registry_type} package fetch failed: {exc}"
            )
            return result

        # Filter to known code extensions
        files = [
            entry["name"]
            for entry in listing
            if isinstance(entry, dict) and "name" in entry
            and any(entry["name"].endswith(ext) for ext in self.COMMON_CODE_EXTENSIONS)
        ][:max_files]

        for filename in files:
            try:
                file_url = base_cdn.rstrip("/") + "/" + filename
                resp = await self._client.get(file_url)
                resp.raise_for_status()
                code = resp.text

                inner = self._process_snippet(
                    source_url=file_url,
                    language=self._guess_language(filename),
                    code=code,
                    file_path=filename,
                )
                if inner is not None:
                    result.items.append(inner)
                    result.total_fetched += 1
            except httpx.HTTPError as exc:
                result.errors.append(f"Failed to fetch {filename}: {exc}")

        result.total_after_dedup = result.total_fetched
        result.total_after_security = len(result.items)
        return result

    def _process_snippet(
        self,
        source_url: str,
        language: str,
        code: str,
        file_path: str | None = None,
    ) -> FetchedCode | None:
        """Deduplicate and security-filter a snippet; return FetchedCode or None."""
        if len(code.encode("utf-8")) > self.MAX_FILE_SIZE:
            logger.debug("Skipping oversized snippet from %s", source_url)
            return None

        # Hash-based dedup
        checksum = hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]
        if checksum in self._seen_checksums:
            logger.debug("Duplicate snippet skipped from %s", source_url)
            return None
        self._seen_checksums.add(checksum)

        # Security filtering
        if self._is_blocked(code):
            logger.info("Security-filtered snippet from %s", source_url)
            return None

        return FetchedCode(
            source_url=source_url,
            language=language,
            code=code,
            file_path=file_path,
            checksum=checksum,
        )

    def _is_blocked(self, code: str) -> bool:
        for pattern in _SECURITY_BLOCK_PATTERNS:
            if pattern.search(code):
                return True
        return False

    @staticmethod
    def _guess_language(file_path: str) -> str:
        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
        mapping = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "jsx": "jsx",
            "tsx": "tsx",
            "go": "go",
            "rs": "rust",
            "java": "java",
            "c": "c",
            "cpp": "cpp",
            "rb": "ruby",
            "php": "php",
            "swift": "swift",
            "kt": "kotlin",
            "r": "r",
            "sql": "sql",
            "sh": "bash",
            "yaml": "yaml",
            "yml": "yaml",
            "json": "json",
            "toml": "toml",
            "md": "markdown",
            "css": "css",
            "html": "html",
            "vue": "vue",
            "svelte": "svelte",
            "lua": "lua",
            "dart": "dart",
            "zig": "zig",
        }
        return mapping.get(ext, "text")
