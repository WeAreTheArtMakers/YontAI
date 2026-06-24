"""Project memory graph for dependency-aware context retrieval.

Tracks forward/reverse dependencies between project files to enable
intelligent context assembly. When a file is queried, the graph returns
not just the file itself but its related files based on dependency chains.

Architecture (from ARCHITECTURE.md §4):
    File Index → Import Resolution → Dependency Graph → Context Assembly
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DependencyNode:
    """A node in the project dependency graph representing a file."""

    file_path: str  # Absolute path
    imports: list[str] = field(default_factory=list)  # Module names imported by this file
    exported_symbols: list[str] = field(default_factory=list)  # Symbols this file exports
    used_by: list[str] = field(default_factory=list)  # Files that import this file (reverse deps)
    depends_on: list[str] = field(default_factory=list)  # Files this file imports (forward deps)
    last_modified: float = 0.0
    size_bytes: int = 0
    language: str = ""
    module_name: str = ""  # Python module name, e.g. "yontai.models.router"


@dataclass
class DependencyGraphStats:
    """Statistics about the dependency graph."""

    total_files: int = 0
    file_types: dict[str, int] = field(default_factory=dict)
    total_dependencies: int = 0
    total_reverse_dependencies: int = 0
    max_depth: int = 0
    orphan_files: int = 0  # Files with no imports and no dependents


class ProjectMemoryGraph:
    """Project dependency graph for context-aware retrieval.

    Tracks which files import which other files. When a query targets
    a specific file, the graph provides:
    1. Direct dependencies (files it imports)
    2. Reverse dependencies (files that import it)
    3. Sibling files (same directory)
    4. Related files via symbol lookup

    The graph is built incrementally as files are indexed.
    Resolution order for context:
        1st: Direct dependencies (files the target imports)
        2nd: Reverse dependencies (files that import the target)
        3rd: Sibling files (same parent directory)
        4th: Symbol-based relationships
    """

    def __init__(self) -> None:
        self._nodes: dict[str, DependencyNode] = {}
        self._symbol_index: dict[str, list[str]] = defaultdict(list)  # symbol -> [file_paths]
        self._module_index: dict[str, str] = {}  # module_name -> file_path
        self._stats = DependencyGraphStats()

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------

    def add_file(
        self,
        file_path: str,
        imports: list[str] | None = None,
        exports: list[str] | None = None,
        language: str = "",
        module_name: str = "",
    ) -> DependencyNode:
        """Add or update a file in the dependency graph.

        Args:
            file_path: Absolute path to the file.
            imports: List of module names that this file imports.
            exports: List of symbols exported/defined by this file.
            language: Programming language of the file.
            module_name: Module name for import resolution (e.g. 'yontai.models').

        Returns:
            The DependencyNode for the added file.
        """
        path = Path(file_path).resolve()
        rel_path = str(path)

        imports = imports or []
        exports = exports or []

        # Resolve imports to concrete file paths
        resolved_deps: list[str] = []
        for imp in imports:
            resolved = self._resolve_import(rel_path, imp, language)
            if resolved:
                resolved_deps.append(resolved)

        # Create or update node
        node = DependencyNode(
            file_path=rel_path,
            imports=imports,
            exported_symbols=exports,
            depends_on=resolved_deps,
            last_modified=path.stat().st_mtime if path.exists() else 0.0,
            size_bytes=path.stat().st_size if path.exists() else 0,
            language=language,
            module_name=module_name,
        )

        # Update reverse dependencies
        for dep_path in resolved_deps:
            if dep_path in self._nodes:
                if rel_path not in self._nodes[dep_path].used_by:
                    self._nodes[dep_path].used_by.append(rel_path)
            else:
                # Create placeholder node for unresolvable imports
                placeholder = DependencyNode(file_path=dep_path)
                placeholder.used_by.append(rel_path)
                self._nodes[dep_path] = placeholder

        self._nodes[rel_path] = node

        # Update symbol index
        for symbol in exports:
            if rel_path not in self._symbol_index[symbol]:
                self._symbol_index[symbol].append(rel_path)

        # Update module index
        if module_name:
            self._module_index[module_name] = rel_path

        return node

    def add_import_relationship(self, from_file: str, to_file: str) -> None:
        """Manually add an import relationship between two files.

        Args:
            from_file: The file that does the importing.
            to_file: The file that is being imported.
        """
        from_path = str(Path(from_file).resolve())
        to_path = str(Path(to_file).resolve())

        for path in (from_path, to_path):
            if path not in self._nodes:
                self._nodes[path] = DependencyNode(file_path=path)

        # Forward dep
        if to_path not in self._nodes[from_path].depends_on:
            self._nodes[from_path].depends_on.append(to_path)

        # Reverse dep
        if from_path not in self._nodes[to_path].used_by:
            self._nodes[to_path].used_by.append(from_path)

    def remove_file(self, file_path: str) -> None:
        """Remove a file and its relationships from the graph.

        Args:
            file_path: Absolute path to the file to remove.
        """
        path = str(Path(file_path).resolve())

        if path not in self._nodes:
            return

        node = self._nodes[path]

        # Remove this file from reverse deps of its dependencies
        for dep in node.depends_on:
            if dep in self._nodes and path in self._nodes[dep].used_by:
                self._nodes[dep].used_by.remove(path)

        # Remove this file from forward deps of its dependents
        for dependent in node.used_by:
            if dependent in self._nodes and path in self._nodes[dependent].depends_on:
                self._nodes[dependent].depends_on.remove(path)

        # Remove from symbol index
        for symbol in node.exported_symbols:
            if path in self._symbol_index[symbol]:
                self._symbol_index[symbol].remove(path)

        # Remove from module index
        if node.module_name and node.module_name in self._module_index:
            del self._module_index[node.module_name]

        # Remove node
        del self._nodes[path]

    # ------------------------------------------------------------------
    # Context retrieval
    # ------------------------------------------------------------------

    def get_context_for_file(
        self,
        file_path: str,
        max_files: int = 5,
        include_self: bool = False,
    ) -> list[str]:
        """Get context files relevant to the given file.

        Priority order:
        1. Direct dependencies (files this file imports) [highest]
        2. Reverse dependencies (files that import this file)
        3. Sibling files (same parent directory)
        4. Files that share exported symbols

        Args:
            file_path: Path to the target file.
            max_files: Maximum number of context files to return.
            include_self: Whether to include the target file itself.

        Returns:
            Ordered list of file paths relevant for context, most relevant first.
        """
        path = str(Path(file_path).resolve())

        if path not in self._nodes:
            return [path] if include_self else []

        node = self._nodes[path]
        context_files: list[str] = []
        seen: set[str] = set()

        if include_self:
            context_files.append(path)
            seen.add(path)

        # 1. Direct dependencies (forward)
        for dep in node.depends_on:
            if dep not in seen and len(context_files) < max_files:
                context_files.append(dep)
                seen.add(dep)

        # 2. Reverse dependencies (backward)
        for dep in node.used_by:
            if dep not in seen and len(context_files) < max_files:
                context_files.append(dep)
                seen.add(dep)

        # 3. Sibling files (same directory)
        parent = Path(path).parent
        if parent.exists():
            for sibling in parent.iterdir():
                if not sibling.is_file():
                    continue
                sib_path = str(sibling.resolve())
                if sib_path not in seen and len(context_files) < max_files:
                    # Skip common non-code files
                    if sibling.suffix.lower() in (".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go"):
                        context_files.append(sib_path)
                        seen.add(sib_path)

        # 4. Symbol-based: files that export symbols this file imports
        for imp in node.imports:
            if len(context_files) >= max_files:
                break
            if imp in self._module_index:
                mod_path = self._module_index[imp]
                if mod_path not in seen:
                    context_files.append(mod_path)
                    seen.add(mod_path)

        return context_files[:max_files]

    def search_by_symbol(self, symbol: str) -> list[str]:
        """Find files that export a given symbol.

        Args:
            symbol: The symbol name to search for (function, class, variable).

        Returns:
            List of file paths that define/export the symbol.
        """
        return list(self._symbol_index.get(symbol, []))

    def get_dependency_chain(
        self,
        file_path: str,
        direction: str = "forward",
        max_depth: int = 3,
    ) -> list[list[str]]:
        """Get the full dependency chain for a file.

        Args:
            file_path: Starting file path.
            direction: 'forward' (what this file imports) or
                      'reverse' (what imports this file).
            max_depth: Maximum depth to traverse.

        Returns:
            List of lists, where each inner list is a level in the chain
            (breadth-first). E.g. [[file], [dep1, dep2], [dep1_of_dep1, ...]].
        """
        path = str(Path(file_path).resolve())
        if path not in self._nodes:
            return [[path]]

        chain: list[list[str]] = [[path]]
        visited: set[str] = {path}
        current_level = [path]

        for _depth in range(max_depth):
            next_level: list[str] = []
            for current in current_level:
                if current not in self._nodes:
                    continue
                node = self._nodes[current]
                deps = node.depends_on if direction == "forward" else node.used_by
                for dep in deps:
                    if dep not in visited and dep in self._nodes:
                        visited.add(dep)
                        next_level.append(dep)

            if not next_level:
                break
            chain.append(next_level)
            current_level = next_level

        return chain

    def find_related_via_symbols(self, file_path: str) -> list[str]:
        """Find files related through shared symbol references.

        If file A imports symbol X, and file B also imports or exports X,
        they are related.

        Args:
            file_path: The target file path.

        Returns:
            List of related file paths.
        """
        path = str(Path(file_path).resolve())
        if path not in self._nodes:
            return []

        node = self._nodes[path]
        related: set[str] = set()

        for imp in node.imports:
            if imp in self._module_index:
                related.add(self._module_index[imp])

        for symbol in node.exported_symbols:
            related.update(self._symbol_index.get(symbol, []))

        related.discard(path)
        return list(related)

    # ------------------------------------------------------------------
    # Graph traversal and utilities
    # ------------------------------------------------------------------

    def get_node(self, file_path: str) -> DependencyNode | None:
        """Get the DependencyNode for a file path.

        Args:
            file_path: Path to look up.

        Returns:
            DependencyNode if found, None otherwise.
        """
        path = str(Path(file_path).resolve())
        return self._nodes.get(path)

    def has_file(self, file_path: str) -> bool:
        """Check if a file is in the graph.

        Args:
            file_path: Path to check.

        Returns:
            True if the file is tracked.
        """
        return str(Path(file_path).resolve()) in self._nodes

    def find_orbit_files(
        self,
        file_path: str,
        radius: int = 1,
    ) -> list[str]:
        """Find files within N degrees of separation.

        Degree 1: Direct dependencies + reverse dependencies + siblings
        Degree 2: Dependencies of dependencies, etc.

        Args:
            file_path: Center file.
            radius: Degrees of separation (1 or 2).

        Returns:
            List of file paths within the given radius, ordered by proximity.
        """
        path = str(Path(file_path).resolve())
        orbit: list[str] = []
        visited: set[str] = {path}

        if radius < 1:
            return orbit

        # Degree 1
        context = self.get_context_for_file(path, max_files=20)
        orbit.extend(context)
        visited.update(context)

        if radius < 2:
            return orbit

        # Degree 2: get context for each degree-1 file
        for fp in context:
            next_context = self.get_context_for_file(fp, max_files=5)
            for nf in next_context:
                if nf not in visited:
                    orbit.append(nf)
                    visited.add(nf)

        return orbit

    # ------------------------------------------------------------------
    # Statistics and introspection
    # ------------------------------------------------------------------

    def compute_stats(self) -> DependencyGraphStats:
        """Compute and cache statistics about the graph.

        Returns:
            DependencyGraphStats with counts and metadata.
        """
        stats = DependencyGraphStats()
        stats.total_files = len(self._nodes)

        file_types: dict[str, int] = {}
        total_forward = 0
        total_reverse = 0
        orphans = 0
        max_depth = 0

        for _path, node in self._nodes.items():
            ext = Path(_path).suffix.lower()
            file_types[ext] = file_types.get(ext, 0) + 1

            total_forward += len(node.depends_on)
            total_reverse += len(node.used_by)

            if not node.depends_on and not node.used_by:
                orphans += 1

            depth = len(self.get_dependency_chain(_path, max_depth=5))
            max_depth = max(max_depth, depth)

        stats.file_types = file_types
        stats.total_dependencies = total_forward
        stats.total_reverse_dependencies = total_reverse
        stats.orphan_files = orphans
        stats.max_depth = max_depth

        self._stats = stats
        return stats

    def get_stats(self) -> dict[str, Any]:
        """Get a dictionary of graph statistics for API responses."""
        stats = self._stats

        # Refresh stats if they seem stale
        if stats.total_files != len(self._nodes):
            stats = self.compute_stats()

        return {
            "total_files": stats.total_files,
            "file_types": dict(stats.file_types),
            "total_dependencies": stats.total_dependencies,
            "total_reverse_depdencies": stats.total_reverse_dependencies,
            "max_depth": stats.max_depth,
            "orphan_files": stats.orphan_files,
            "indexed_symbols": len(self._symbol_index),
            "indexed_modules": len(self._module_index),
        }

    def clear(self) -> None:
        """Clear all nodes, indices, and statistics."""
        self._nodes.clear()
        self._symbol_index.clear()
        self._module_index.clear()
        self._stats = DependencyGraphStats()

    # ------------------------------------------------------------------
    # Internal resolution
    # ------------------------------------------------------------------

    def _resolve_import(self, current_file: str, import_stmt: str, language: str) -> str | None:
        """Resolve an import statement to an absolute file path.

        Supports Python, TypeScript/JavaScript, and Rust import syntax.

        Args:
            current_file: The file that contains the import statement.
            import_stmt: The raw import string (e.g. "os", "./utils", "react").
            language: Programming language for resolution strategy.

        Returns:
            Resolved absolute file path, or None if unresolvable.
        """
        current = Path(current_file)
        project_root = self._find_project_root(current)

        if language == "python":
            return self._resolve_python_import(current, import_stmt, project_root)
        elif language in ("typescript", "javascript", "tsx", "jsx"):
            return self._resolve_ts_import(current, import_stmt, project_root)
        elif language == "rust":
            return self._resolve_rust_import(current, import_stmt, project_root)

        # Generic fallback: check if it's in the module index already
        return self._module_index.get(import_stmt)

    def _resolve_python_import(
        self,
        current: Path,
        import_stmt: str,
        project_root: Path | None,
    ) -> str | None:
        """Resolve a Python import statement."""
        # Relative import: from .module import X
        if import_stmt.startswith("."):
            parts = import_stmt.split(".")
            depth = len(parts) - 1  # Number of dots
            base = current.parent
            for _ in range(depth):
                base = base.parent
            module_name = parts[-1] if parts[-1] else ""
            if module_name:
                for ext in (".py",):
                    candidate = base / f"{module_name}{ext}"
                    if candidate.exists():
                        return str(candidate.resolve())
                # Check as package
                pkg_dir = base / module_name
                if pkg_dir.is_dir() and (pkg_dir / "__init__.py").exists():
                    return str((pkg_dir / "__init__.py").resolve())
            return None

        # Absolute import: import yontai.models.router
        # Convert module path to file path
        parts = import_stmt.split(".")
        if project_root:
            # Check various resolutions
            for i in range(len(parts), 0, -1):
                sub_parts = parts[:i]
                rel_path = Path(*sub_parts)
                # Try as .py
                candidate_py = project_root / rel_path.with_suffix(".py")
                if candidate_py.exists():
                    return str(candidate_py.resolve())
                # Try as __init__.py
                candidate_init = project_root / rel_path / "__init__.py"
                if candidate_init.exists():
                    return str(candidate_init.resolve())

        # Check module index
        return self._module_index.get(import_stmt)

    def _resolve_ts_import(
        self,
        current: Path,
        import_stmt: str,
        project_root: Path | None,
    ) -> str | None:
        """Resolve a TypeScript/JavaScript import statement."""
        # Relative import: ./utils, ../helpers
        if import_stmt.startswith("."):
            base = current.parent
            if import_stmt.startswith(".."):
                parts = import_stmt.split("/")
                for part in parts[:-1]:
                    if part == "..":
                        base = base.parent
                    elif part == ".":
                        continue
                module_name = parts[-1]
            else:
                module_name = import_stmt.lstrip("./")

            # Try different extensions
            for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
                candidate = base / f"{module_name}{ext}"
                if candidate.exists():
                    return str(candidate.resolve())

            # Try as index file in directory
            for ext in (".ts", ".tsx", ".js", ".jsx"):
                candidate = base / module_name / f"index{ext}"
                if candidate.exists():
                    return str(candidate.resolve())

            return None

        # Absolute import (npm package or project module)
        if project_root:
            node_modules = project_root / "node_modules"
            pkg_path = node_modules / import_stmt
            if pkg_path.exists():
                # Find main entry
                pkg_json = pkg_path / "package.json"
                if pkg_json.exists():
                    try:
                        import json
                        with open(pkg_json) as f:
                            data = json.load(f)
                        main_field = data.get("main") or data.get("module") or "index.js"
                        main_path = pkg_path / main_field
                        if main_path.exists():
                            return str(main_path.resolve())
                    except Exception:
                        pass

        # Check src directory
        if project_root:
            src_dir = project_root / "src"
            for ext in (".ts", ".tsx", ".js", ".jsx"):
                candidate = src_dir / f"{import_stmt}{ext}"
                if candidate.exists():
                    return str(candidate.resolve())
                index_candidate = src_dir / import_stmt / f"index{ext}"
                if index_candidate.exists():
                    return str(index_candidate.resolve())

        return self._module_index.get(import_stmt)

    def _resolve_rust_import(
        self,
        current: Path,
        import_stmt: str,
        project_root: Path | None,
    ) -> str | None:
        """Resolve a Rust use/import statement."""
        # Rust uses: use crate::module::Item;
        #           use std::collections::HashMap;
        #           use super::module;

        parts = import_stmt.split("::")
        if not parts:
            return None

        if parts[0] == "crate" and project_root:
            # Crate-relative: maps to src/ directory
            src_dir = project_root / "src"
            rel_parts = parts[1:]  # Remove "crate"
            if rel_parts:
                # Last part might be an item name, not a module
                # Try with .rs first
                for i in range(len(rel_parts), 0, -1):
                    mod_path = src_dir.joinpath(*rel_parts[:i]).with_suffix(".rs")
                    if mod_path.exists():
                        return str(mod_path.resolve())
                    # Try as directory with mod.rs
                    mod_dir = src_dir.joinpath(*rel_parts[:i])
                    if mod_dir.is_dir() and (mod_dir / "mod.rs").exists():
                        return str((mod_dir / "mod.rs").resolve())
            return None

        if parts[0] == "super" and project_root:
            # Parent module
            parent = current.parent
            rel_parts = parts[1:]
            if rel_parts:
                for candidate_ext in (".rs",):
                    candidate = parent.joinpath(*rel_parts).with_suffix(candidate_ext)
                    if candidate.exists():
                        return str(candidate.resolve())
            return None

        # External crate or std - not resolvable locally
        return None

    @staticmethod
    def _find_project_root(path: Path) -> Path | None:
        """Walk up from the file to find the project root."""
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
