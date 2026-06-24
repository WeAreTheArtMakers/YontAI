"""
Dataset Builder for code instruction / FIM / chat datasets.
Extracts functions from code files and builds JSONL-formatted training data.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Regex patterns to extract function definitions per language
_FUNCTION_PATTERNS: dict[str, list[re.Pattern]] = {
    "python": [
        re.compile(
            r"^(?P<decorators>(?:@\w+(?:\(.*?\))?\s*)*)def\s+"
            r"(?P<name>\w+)\s*\((?P<args>.*?)\)\s*"
            r"(?:->\s*(?P<return_type>[^:]+))?\s*:"
            r"(?P<body>(?:[^\n]*\n(?:[ \t]+.*(?:\n|$))*)*)",
            re.MULTILINE,
        ),
    ],
    "javascript": [
        re.compile(
            r"(?:async\s+)?function\s+(?P<name>\w+)\s*"
            r"\((?P<args>.*?)\)\s*"
            r"(?P<body>\{(?:[^{}]|\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})*\})",
            re.DOTALL,
        ),
        re.compile(
            r"(?P<name>\w+)\s*=\s*(?:async\s+)?function\s*"
            r"\((?P<args>.*?)\)\s*"
            r"(?P<body>\{(?:[^{}]|\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})*\})",
            re.DOTALL,
        ),
        re.compile(
            r"(?:const|let|var)\s+(?P<name>\w+)\s*=\s*(?:async\s+)?"
            r"\((?P<args>.*?)\)\s*(?:=>\s*)(?P<body>\{(?:[^{}]|\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})*\})",
            re.DOTALL,
        ),
    ],
    "typescript": [],  # Falls back to javascript patterns
    "go": [
        re.compile(
            r"func\s+(?P<name>\w+)\s*\((?P<args>[^)]*)\)\s*"
            r"(?:\((?P<return_type>[^)]*)\)|\s*(?P<return_type_simple>\w+))?\s*"
            r"(?P<body>\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})",
            re.DOTALL,
        ),
    ],
    "rust": [
        re.compile(
            r"(?:pub\s+)?(?:unsafe\s+)?fn\s+(?P<name>\w+)\s*"
            r"<(?P<generics>[^>]*)>\s*\((?P<args>[^)]*)\)\s*"
            r"(?:->\s*(?P<return_type>[^{]+))?\s*"
            r"(?P<body>\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})",
            re.DOTALL,
        ),
        re.compile(
            r"(?:pub\s+)?(?:unsafe\s+)?fn\s+(?P<name>\w+)\s*"
            r"\((?P<args>[^)]*)\)\s*"
            r"(?:->\s*(?P<return_type>[^{]+))?\s*"
            r"(?P<body>\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})",
            re.DOTALL,
        ),
    ],
    "java": [
        re.compile(
            r"(?:public|private|protected|static|final|abstract|synchronized)\s+"
            r"(?:\w+\[\]|\w+(?:<[^>]*>)?)\s+(?P<name>\w+)\s*"
            r"\((?P<args>[^)]*)\)\s*"
            r"(?:throws\s+\w+(?:,\s*\w+)*)?\s*"
            r"(?P<body>\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})",
            re.DOTALL,
        ),
    ],
    "ruby": [
        re.compile(
            r"(?:def\s+(?P<name>\w+(?:[?!])?)\s*"
            r"\(?(?P<args>[^)]*)?\)?\s*"
            r"(?P<body>(?:\n[ \t]+.*)*)\nend)",
            re.MULTILINE,
        ),
    ],
}


@dataclass
class ExtractedFunction:
    """A single function extracted from a code file."""

    name: str
    language: str
    args: str
    return_type: str | None
    body: str
    source_file: str | None = None
    decorators: str = ""

    @property
    def full_signature(self) -> str:
        ret = f" -> {self.return_type}" if self.return_type else ""
        return f"{self.name}({self.args}){ret}"

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.body.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Dataset formats
# ---------------------------------------------------------------------------


@dataclass
class InstructionExample:
    """An instruction-following example for supervised fine-tuning."""

    instruction: str
    input: str = ""
    output: str = ""

    def to_dict(self) -> dict[str, str]:
        result: dict[str, str] = {"instruction": self.instruction, "output": self.output}
        if self.input:
            result["input"] = self.input
        return result


@dataclass
class FIMExample:
    """Fill-in-the-Middle example for causal LM training."""

    prefix: str
    middle: str
    suffix: str

    def to_dict(self) -> dict[str, str]:
        return {"prefix": self.prefix, "middle": self.middle, "suffix": self.suffix}


@dataclass
class ChatExample:
    """Multi-turn chat example."""

    messages: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"messages": self.messages}


# ---------------------------------------------------------------------------
# DatasetBuilder
# ---------------------------------------------------------------------------


class DatasetBuilder:
    """Builds instruction / FIM / chat datasets from code files and outputs JSONL."""

    def __init__(
        self,
        max_examples_per_file: int = 200,
        max_total_examples: int = 50_000,
        min_body_length: int = 10,
    ) -> None:
        self._max_examples_per_file = max_examples_per_file
        self._max_total = max_total_examples
        self._min_body = min_body_length
        self._examples: list[dict[str, Any]] = []
        self._seen_checksums: set[str] = set()

    # -- public API --------------------------------------------------------

    def build_instruction_dataset(
        self,
        functions: list[ExtractedFunction],
        prompt_template: str | None = None,
    ) -> list[InstructionExample]:
        """Build instruction-following examples from extracted functions."""
        examples: list[InstructionExample] = []
        template = prompt_template or _DEFAULT_INSTRUCTION_TEMPLATE
        for fn in functions:
            instruction = template.format(
                name=fn.name,
                signature=fn.full_signature,
                args=fn.args,
                return_type=fn.return_type or "",
                language=fn.language,
            )
            ex = InstructionExample(
                instruction=instruction,
                input=f"Implement {fn.name} in {fn.language}",
                output=fn.body,
            )
            examples.append(ex)
            if len(examples) >= self._max_total:
                break
        return examples

    def build_fim_dataset(
        self,
        functions: list[ExtractedFunction],
        context_lines: int = 3,
    ) -> list[FIMExample]:
        """Build Fill-in-the-Middle examples by hiding the function body."""
        examples: list[FIMExample] = []
        for fn in functions:
            lines = fn.body.split("\n")
            if len(lines) < context_lines * 2 + 1:
                middle = fn.body
                prefix = ""
                suffix = ""
            else:
                split_idx = len(lines) // 2
                prefix = "\n".join(lines[:split_idx])
                middle = "\n".join(lines[split_idx : split_idx + context_lines])
                suffix = "\n".join(lines[split_idx + context_lines :])

            ex = FIMExample(prefix=prefix, middle=middle, suffix=suffix)
            examples.append(ex)
            if len(examples) >= self._max_total:
                break
        return examples

    def build_chat_dataset(
        self,
        functions: list[ExtractedFunction],
        system_prompt: str | None = None,
    ) -> list[ChatExample]:
        """Build multi-turn chat examples explaining the function."""
        sys_msg = system_prompt or _DEFAULT_SYSTEM_PROMPT
        examples: list[ChatExample] = []
        for fn in functions[: self._max_total]:
            messages: list[dict[str, str]] = [
                {"role": "system", "content": sys_msg},
                {
                    "role": "user",
                    "content": f"Explain the {fn.language} function `{fn.name}` that takes "
                    f"parameters ({fn.args}){f' and returns {fn.return_type}' if fn.return_type else ''}.",
                },
                {"role": "assistant", "content": fn.body},
            ]
            examples.append(ChatExample(messages=messages))
        return examples

    # -- file-level processing ---------------------------------------------

    def process_code_file(
        self,
        file_path: str | Path,
        language: str | None = None,
    ) -> list[ExtractedFunction]:
        """Read a single code file and extract functions."""
        path = Path(file_path)
        if not path.is_file():
            logger.warning("File not found: %s", file_path)
            return []

        code = path.read_text(encoding="utf-8", errors="replace")
        lang = language or self._infer_language(path)
        return self._extract_functions(code, lang, source_file=str(path))

    def process_code_files(
        self,
        file_paths: list[str | Path],
    ) -> list[ExtractedFunction]:
        """Process multiple code files and collect unique functions."""
        all_fns: list[ExtractedFunction] = []
        for fp in file_paths:
            fns = self.process_code_file(fp)
            for fn in fns:
                if fn.checksum not in self._seen_checksums:
                    self._seen_checksums.add(fn.checksum)
                    all_fns.append(fn)
            if len(all_fns) >= self._max_total:
                break
        return all_fns

    def generate_instruction_prompts(
        self,
        functions: list[ExtractedFunction],
        output_path: str | Path | None = None,
    ) -> list[dict[str, str]]:
        """Wrapper that builds instruction dataset and returns dicts."""
        examples = self.build_instruction_dataset(functions)
        dicts = [ex.to_dict() for ex in examples]
        if output_path:
            self._write_jsonl(dicts, output_path)
        return dicts

    def generate_fim_prompts(
        self,
        functions: list[ExtractedFunction],
        output_path: str | Path | None = None,
    ) -> list[dict[str, str]]:
        """Wrapper that builds FIM dataset and returns dicts."""
        examples = self.build_fim_dataset(functions)
        dicts = [ex.to_dict() for ex in examples]
        if output_path:
            self._write_jsonl(dicts, output_path)
        return dicts

    def generate_chat_prompts(
        self,
        functions: list[ExtractedFunction],
        output_path: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        """Wrapper that builds chat dataset and returns dicts."""
        examples = self.build_chat_dataset(functions)
        dicts = [ex.to_dict() for ex in examples]
        if output_path:
            self._write_jsonl(dicts, output_path)
        return dicts

    # -- internal helpers --------------------------------------------------

    def _extract_functions(
        self,
        code: str,
        language: str,
        source_file: str | None = None,
    ) -> list[ExtractedFunction]:
        """Extract function definitions from code using language-specific patterns."""
        patterns = _FUNCTION_PATTERNS.get(language, [])
        # Fallback for typescript -> javascript
        if not patterns and language == "typescript":
            patterns = _FUNCTION_PATTERNS.get("javascript", [])
        if not patterns:
            # Generic fallback: line with `def ` or `function ` or `fn `
            patterns = [
                re.compile(
                    r"^(?:def|function|fn)\s+(?P<name>\w+)\s*\((?P<args>.*?)\)",
                    re.MULTILINE,
                )
            ]

        functions: list[ExtractedFunction] = []
        for pattern in patterns:
            for match in pattern.finditer(code):
                name = match.group("name")
                args = match.group("args") or ""
                body = match.group("body") or ""
                decorators = match.group("decorators") or ""
                return_type = match.group("return_type") or match.group("return_type_simple") or None

                body = body.strip()
                if len(body) < self._min_body:
                    continue

                fn = ExtractedFunction(
                    name=name.strip(),
                    language=language,
                    args=args.strip(),
                    return_type=return_type.strip() if return_type else None,
                    body=body,
                    source_file=source_file,
                    decorators=decorators.strip(),
                )
                functions.append(fn)

                if len(functions) >= self._max_examples_per_file:
                    return functions

        return functions

    @staticmethod
    def _infer_language(path: Path) -> str:
        ext = path.suffix.lower()
        ext_map: dict[str, str] = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
        }
        return ext_map.get(ext, "text")

    @staticmethod
    def _write_jsonl(records: list[dict[str, Any]], path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info("Wrote %d records to %s", len(records), path)
        return path

    def iter_jsonl(self, path: str | Path) -> Iterator[dict[str, Any]]:
        """Yield parsed JSON objects from a JSONL file."""
        with Path(path).open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)


# ---------------------------------------------------------------------------
# Default prompts
# ---------------------------------------------------------------------------

_DEFAULT_INSTRUCTION_TEMPLATE = (
    "Write a {language} function named `{name}` with signature `{signature}`."
)

_DEFAULT_SYSTEM_PROMPT = (
    "You are an expert software engineer. Explain the given function clearly."
)
