"""Dynamic prompt builder with context injection and framework detection.

Builds prompts for chat, FIM, and code actions by injecting project-aware
context including:
- Framework/language detection (React, Node, Python, Rust)
- Coding style preferences
- RAG context from the context engine
- Project-specific system messages

Architecture (from ARCHITECTURE.md §9):
    System Message → Context Injection → RAG Formatting → User Query → Constraints
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from yontai.rag.context_engine import ContextEngine

logger = logging.getLogger(__name__)

# Default system message for general use
DEFAULT_SYSTEM_MESSAGE = """You are YontAI, an expert coding assistant running locally on Apple Silicon.
You help users write, debug, and understand code.

Guidelines:
- Write clean, idiomatic code following best practices
- Explain your reasoning concisely
- When providing code, always specify the language in markdown code blocks
- If you're unsure about something, say so rather than guessing
- Consider the project's framework and coding style when making suggestions"""

# DeepSeek-optimized system message
DEEPSEEK_SYSTEM_MESSAGE = """You are an AI coding assistant specialized in software development.
You provide accurate, efficient, and well-documented code solutions.

Key capabilities:
- Code generation and completion
- Bug detection and fixing
- Code refactoring and optimization
- Test generation
- Architecture design advice

Always respond with clear, production-quality code when coding tasks are requested."""


class FrameworkDetector:
    """Detects project framework from file paths and project configuration.

    Supported frameworks: React, Vue, Angular, Next.js, Express, Django,
    FastAPI, Flask, Spring, Rust (Cargo), Go Modules, Python packages.
    """

    # Framework signatures: config file + dependency key patterns
    _FRAMEWORK_SIGNATURES: dict[str, dict[str, Any]] = {
        "React": {
            "config_files": ["package.json"],
            "dependencies": ["react", "react-dom"],
            "extensions": {".jsx", ".tsx"},
        },
        "Next.js": {
            "config_files": ["next.config.js", "next.config.ts", "next.config.mjs"],
            "dependencies": ["next"],
            "extensions": {".jsx", ".tsx"},
        },
        "Vue": {
            "config_files": ["package.json"],
            "dependencies": ["vue"],
            "extensions": {".vue"},
        },
        "Node.js": {
            "config_files": ["package.json"],
            "dependencies": ["express", "fastify", "koa"],
            "extensions": {".js", ".mjs", ".cjs"},
        },
        "Python": {
            "config_files": ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"],
            "dependencies": [],
            "extensions": {".py"},
        },
        "Django": {
            "config_files": ["manage.py", "settings.py"],
            "dependencies": ["django"],
            "extensions": {".py"},
        },
        "FastAPI": {
            "config_files": ["pyproject.toml", "requirements.txt"],
            "dependencies": ["fastapi"],
            "extensions": {".py"},
        },
        "Rust": {
            "config_files": ["Cargo.toml"],
            "dependencies": [],
            "extensions": {".rs"},
        },
        "Go": {
            "config_files": ["go.mod"],
            "dependencies": [],
            "extensions": {".go"},
        },
    }

    def __init__(self) -> None:
        self._cache: dict[str, str | None] = {}
        self._style_cache: dict[str, str | None] = {}

    def detect(self, file_path: str | None) -> str | None:
        """Detect the framework for a given file path.

        Args:
            file_path: Absolute or relative path to a source file.

        Returns:
            Framework name string (e.g. "React 18"), or None if undetected.
        """
        if not file_path:
            return None

        if file_path in self._cache:
            return self._cache[file_path]

        path = Path(file_path).resolve()
        project_root = self._find_project_root(path)

        if project_root is None:
            self._cache[file_path] = None
            return None

        # Check each framework signature
        for framework_name, sig in self._FRAMEWORK_SIGNATURES.items():
            # Check config files
            for config_name in sig["config_files"]:
                config_path = project_root / config_name
                if config_path.exists():
                    # For package.json based frameworks, check dependencies
                    if config_name == "package.json":
                        version = self._check_package_deps(config_path, sig["dependencies"])
                        if version:
                            result = f"{framework_name} {version}" if version else framework_name
                            self._cache[file_path] = result
                            return result
                    elif config_name == "Cargo.toml":
                        self._cache[file_path] = "Rust"
                        return "Rust"
                    elif config_name == "go.mod":
                        self._cache[file_path] = "Go"
                        return "Go"
                    elif config_name in ("pyproject.toml", "setup.py"):
                        # Check for specific Python framework
                        result = self._detect_python_framework(project_root)
                        if result:
                            self._cache[file_path] = result
                            return result
                        self._cache[file_path] = "Python"
                        return "Python"
                    else:
                        # Simple config file match
                        self._cache[file_path] = framework_name
                        return framework_name

            # Check file extension as fallback
            if path.suffix in sig.get("extensions", set()):
                self._cache[file_path] = framework_name
                return framework_name

        self._cache[file_path] = None
        return None

    def detect_coding_style(self, file_path: str | None) -> str | None:
        """Detect coding style/formatting conventions.

        Looks for ESLint, Prettier, Ruff, Black, and other config files.
        """
        if not file_path:
            return None

        if file_path in self._style_cache:
            return self._style_cache[file_path]

        path = Path(file_path).resolve()
        project_root = self._find_project_root(path)

        if project_root is None:
            self._style_cache[file_path] = None
            return None

        # ESLint
        for config in (".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yaml", ".eslintrc.yml"):
            if (project_root / config).exists():
                self._style_cache[file_path] = "ESLint"
                return "ESLint"

        # Prettier
        for config in (".prettierrc", ".prettierrc.js", ".prettierrc.json", ".prettierrc.yaml", ".prettierrc.toml"):
            if (project_root / config).exists():
                self._style_cache[file_path] = "Prettier"
                return "Prettier"

        # Ruff (Python)
        if (project_root / "pyproject.toml").exists():
            try:
                content = (project_root / "pyproject.toml").read_text()
                if "[tool.ruff]" in content:
                    self._style_cache[file_path] = "Ruff"
                    return "Ruff"
            except Exception:
                pass

        # Black (Python)
        if (project_root / "pyproject.toml").exists():
            try:
                content = (project_root / "pyproject.toml").read_text()
                if "[tool.black]" in content:
                    self._style_cache[file_path] = "Black"
                    return "Black"
            except Exception:
                pass
        if (project_root / ".black").exists():
            self._style_cache[file_path] = "Black"
            return "Black"

        # rustfmt
        if (project_root / "rustfmt.toml").exists() or (project_root / ".rustfmt.toml").exists():
            self._style_cache[file_path] = "rustfmt"
            return "rustfmt"

        self._style_cache[file_path] = None
        return None

    def _find_project_root(self, path: Path) -> Path | None:
        """Walk up from the file to find the project root.

        Project root markers: .git, package.json, Cargo.toml, pyproject.toml, go.mod
        """
        for parent in [path] + list(path.parents):
            markers = [
                parent / ".git",
                parent / "package.json",
                parent / "Cargo.toml",
                parent / "pyproject.toml",
                parent / "go.mod",
            ]
            for marker in markers:
                if marker.exists():
                    return parent
        return None

    def _check_package_deps(self, package_json: Path, deps: list[str]) -> str | None:
        """Check if a package.json contains specific dependencies.

        Returns the version string of the first matching dependency, or None.
        """
        try:
            with open(package_json) as f:
                data = json.load(f)
            all_deps = {
                **data.get("dependencies", {}),
                **data.get("devDependencies", {}),
                **data.get("peerDependencies", {}),
            }
            for dep in deps:
                if dep in all_deps:
                    return all_deps[dep].lstrip("^~>=<")
            return None
        except (json.JSONDecodeError, OSError):
            return None

    def _detect_python_framework(self, project_root: Path) -> str | None:
        """Detect specific Python framework from pyproject.toml or requirements."""
        # Check pyproject.toml
        pyproject = project_root / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                if "django" in content.lower():
                    return "Django"
                if "fastapi" in content.lower():
                    return "FastAPI"
                if "flask" in content.lower():
                    return "Flask"
            except Exception:
                pass

        # Check requirements.txt
        req_file = project_root / "requirements.txt"
        if req_file.exists():
            try:
                content = req_file.read_text().lower()
                if "django" in content:
                    return "Django"
                if "fastapi" in content:
                    return "FastAPI"
                if "flask" in content:
                    return "Flask"
            except Exception:
                pass

        return None

    def clear_cache(self) -> None:
        """Clear the framework and style detection caches."""
        self._cache.clear()
        self._style_cache.clear()


# Action templates for code operations (from ARCHITECTURE.md §9)
class CodeActionTemplates:
    """Templates for code action prompts."""

    @staticmethod
    def explain_code(code: str, language: str = "python") -> str:
        return f"""Explain the following {language} code in detail.
Describe what it does, its inputs/outputs, and any important patterns.

```{language}
{code}
```"""

    @staticmethod
    def generate_tests(code: str, language: str = "python") -> str:
        return f"""Write comprehensive unit tests for the following {language} code.
Include edge cases, error conditions, and normal cases.

```{language}
{code}
```"""

    @staticmethod
    def refactor_code(code: str, language: str = "python") -> str:
        return f"""Refactor the following {language} code to be more maintainable, readable, and efficient.
Apply best practices for the language/framework.

```{language}
{code}
```"""

    @staticmethod
    def add_type_hints(code: str, language: str = "python") -> str:
        return f"""Add type hints/type annotations to the following {language} code.
Follow the language's typing best practices.

```{language}
{code}
```"""

    @staticmethod
    def review_code(code: str, language: str = "python") -> str:
        return f"""Review the following {language} code for:
1. Potential bugs or edge cases
2. Performance issues
3. Security vulnerabilities
4. Code style and best practices
5. Suggestions for improvement

```{language}
{code}
```"""

    @staticmethod
    def find_bugs(code: str, language: str = "python") -> str:
        return f"""Analyze the following {language} code for bugs, logical errors, and potential runtime issues.
Be specific about line numbers and suggest fixes.

```{language}
{code}
```"""

    @staticmethod
    def optimize_imports(code: str, language: str = "python") -> str:
        return f"""Optimize the imports in the following {language} code:
- Remove unused imports
- Sort imports alphabetically
- Group standard library, third-party, and local imports
- Use specific imports instead of wildcards

```{language}
{code}
```"""

    @staticmethod
    def add_docstrings(code: str, language: str = "python") -> str:
        return f"""Add comprehensive documentation to the following {language} code.
Include docstrings for functions/classes describing parameters, return values, and behavior.

```{language}
{code}
```"""


class DynamicPromptBuilder:
    """Builds dynamic prompts with project-aware context injection.

    Features:
    - Framework detection (React, Vue, Python, Rust, Go, etc.)
    - Coding style detection (ESLint, Prettier, Ruff, Black, rustfmt)
    - RAG context injection from ContextEngine
    - Multi-language support (Turkish/English)
    - Model-family-specific system messages
    - Code action templates for common operations

    Usage:
        builder = DynamicPromptBuilder(context_engine)
        prompt = await builder.build_chat_prompt(
            query="How do I use useEffect?",
            current_file="/project/src/App.tsx",
        )
    """

    def __init__(self, context_engine: ContextEngine | None = None) -> None:
        self.context_engine = context_engine
        self._framework_detector = FrameworkDetector()

    async def build_chat_prompt(
        self,
        query: str,
        current_file: str | None = None,
        language: str = "en",
        model_family: str = "deepseek",
        rag_context: str | None = None,
    ) -> str:
        """Build a chat prompt with full context injection.

        Args:
            query: The user's question or request.
            current_file: Path to the currently open file.
            language: Response language ('en' or 'tr').
            model_family: Model family for system message selection.
            rag_context: Pre-fetched RAG context (optional, will fetch if None).

        Returns:
            A fully assembled prompt string with system message, context, and query.
        """
        # 1. Detect framework and style
        framework = self._framework_detector.detect(current_file)
        style = self._framework_detector.detect_coding_style(current_file)

        # 2. Build system message
        sys_message = self._build_system_message(
            framework=framework,
            style=style,
            language=language,
            model_family=model_family,
        )

        # 3. Get or use provided RAG context
        if rag_context is None and self.context_engine:
            rag_context = self.context_engine.build_prompt_context(
                query=query,
                current_file=current_file,
                max_tokens=2048,
            )

        # 4. Build the final prompt
        parts: list[str] = []
        parts.append(f"<|system|>\n{sys_message}\n")

        user_parts: list[str] = []

        # Add framework/style info block
        context_hints: list[str] = []
        if framework:
            context_hints.append(f"Project: {framework}")
        if style:
            context_hints.append(f"Style: {style}")
        if context_hints:
            user_parts.append("// " + "\n// ".join(context_hints))

        # Add RAG context
        if rag_context:
            user_parts.append(rag_context)

        # Add the user query
        user_parts.append(query)

        user_content = "\n\n".join(user_parts)
        parts.append(f"<|user|>\n{user_content}\n")
        parts.append("<|assistant|>\n")

        return "".join(parts)

    async def build_fim_prompt(
        self,
        prefix: str,
        suffix: str,
        current_file: str | None = None,
    ) -> str:
        """Build a Fill-in-the-Middle prompt.

        FIM prompts don't use system messages; the model infers
        context from the prefix/suffix alone.

        Args:
            prefix: Code before cursor position.
            suffix: Code after cursor position.
            current_file: Path to current file (for logging only).

        Returns:
            A FIM-formatted prompt string.
        """
        return f"<|fim_begin|>{prefix}<|fim_hole|>{suffix}<|fim_end|>"

    async def build_code_action_prompt(
        self,
        action: str,
        code: str,
        language: str = "python",
        current_file: str | None = None,
        rag_context: str | None = None,
    ) -> str:
        """Build a prompt for a code action (explain, test, refactor, etc.).

        Args:
            action: Action type ('explain', 'test', 'refactor', 'typehints',
                   'review', 'bugs', 'imports', 'docstrings').
            code: The code to act upon.
            language: Programming language of the code.
            current_file: Path to the source file.
            rag_context: Pre-fetched RAG context (optional).

        Returns:
            A fully assembled code action prompt.
        """
        # Detect framework
        framework = self._framework_detector.detect(current_file)

        # Build system message (shorter for code actions)
        sys_message = self._build_system_message(
            framework=framework,
            style=None,
            language="en",
            model_family="deepseek",
            concise=True,
        )

        # Get RAG context if needed
        if rag_context is None and self.context_engine and code:
            rag_context = self.context_engine.build_prompt_context(
                query=code,
                current_file=current_file,
                max_tokens=1024,
            )

        # Select template
        action_templates = {
            "explain": CodeActionTemplates.explain_code,
            "test": CodeActionTemplates.generate_tests,
            "refactor": CodeActionTemplates.refactor_code,
            "typehints": CodeActionTemplates.add_type_hints,
            "review": CodeActionTemplates.review_code,
            "bugs": CodeActionTemplates.find_bugs,
            "imports": CodeActionTemplates.optimize_imports,
            "docstrings": CodeActionTemplates.add_docstrings,
        }

        template_fn = action_templates.get(action, CodeActionTemplates.explain_code)
        action_prompt = template_fn(code, language)

        # Build final prompt
        parts: list[str] = []
        parts.append(f"<|system|>\n{sys_message}\n")

        user_parts: list[str] = []
        if rag_context:
            user_parts.append(rag_context)
        user_parts.append(action_prompt)

        parts.append(f"<|user|>\n{''.join(user_parts)}\n")
        parts.append("<|assistant|>\n")

        return "".join(parts)

    def _build_system_message(
        self,
        framework: str | None = None,
        style: str | None = None,
        language: str = "en",
        model_family: str = "deepseek",
        concise: bool = False,
    ) -> str:
        """Build a context-aware system message.

        Args:
            framework: Detected project framework.
            style: Detected coding style.
            language: 'en' or 'tr' for response language preference.
            model_family: 'deepseek' or 'default' for message variant.
            concise: If True, returns a shorter system message.

        Returns:
            A system message string tailored to the detected context.
        """
        if concise:
            base = "You are YontAI, a coding assistant. Provide accurate, concise code solutions."
        elif model_family == "deepseek":
            base = DEEPSEEK_SYSTEM_MESSAGE
        else:
            base = DEFAULT_SYSTEM_MESSAGE

        # Append project context
        extras: list[str] = []
        if framework:
            extras.append(f"The current project uses {framework}.")
        if style:
            extras.append(f"The project uses {style} for code style / formatting.")

        if language == "tr":
            extras.append("Please respond in Turkish.")
        else:
            extras.append("Please respond in English.")

        if extras:
            return base + "\n\n" + "\n".join(extras)

        return base

    def clear_cache(self) -> None:
        """Clear framework/style detection caches."""
        self._framework_detector.clear_cache()
