"""
Context Agent for OTTO OS
=========================

A specialized agent that analyzes import dependencies and relationships
between files, depositing CONTEXT trails to help navigation.

ThinkingMachines [He2025] Compliance:
- Uses deterministic AST parsing
- Deposits trails in sorted order
- Fixed dependency resolution algorithm

Usage:
    agent = ContextAgent()
    result = await agent.analyze_file("src/otto/example.py")
    result = await agent.analyze_directory("src/otto/")
    graph = await agent.build_dependency_graph("src/otto/")
"""

import ast
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..trails import Trail, TrailStore, TrailType, get_store


@dataclass
class ImportInfo:
    """Information about a single import."""
    module: str               # Full module path (e.g., "otto.trails")
    names: list[str]         # Imported names (empty for 'import X')
    is_relative: bool        # True for relative imports
    level: int               # Number of dots for relative imports
    line: int                # Line number in source


@dataclass
class FileContext:
    """Context analysis result for a single file."""
    path: str
    imports: list[ImportInfo] = field(default_factory=list)
    exported_names: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    used_by: list[str] = field(default_factory=list)
    trails_deposited: int = 0
    analysis_time: datetime = field(default_factory=datetime.now)


@dataclass
class DependencyGraph:
    """Dependency graph for a codebase."""
    files: dict[str, FileContext] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)  # (from, to)

    @property
    def node_count(self) -> int:
        return len(self.files)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def get_dependents(self, path: str) -> list[str]:
        """Get files that depend on the given path."""
        return sorted([src for src, dst in self.edges if dst == path])

    def get_dependencies(self, path: str) -> list[str]:
        """Get files that the given path depends on."""
        return sorted([dst for src, dst in self.edges if src == path])


class ContextAgent:
    """
    Agent for analyzing file dependencies and relationships.

    Provides:
    - Single file import analysis
    - Directory-wide dependency mapping
    - Dependency graph construction
    - Trail deposition for relationships
    """

    def __init__(
        self,
        store: Optional[TrailStore] = None,
        agent_id: str = "context_agent",
        auto_deposit: bool = True,
        base_path: Optional[Path] = None,
    ):
        """
        Initialize the ContextAgent.

        Args:
            store: TrailStore to use (defaults to global store)
            agent_id: Identifier for trail deposits
            auto_deposit: Whether to automatically deposit trails
            base_path: Base path for resolving relative imports
        """
        self.store = store or get_store()
        self.agent_id = agent_id
        self.auto_deposit = auto_deposit
        self.base_path = base_path or Path.cwd()

    async def analyze_file(self, file_path: str | Path) -> FileContext:
        """
        Analyze a single file for imports and exports.

        Args:
            file_path: Path to the Python file

        Returns:
            FileContext with import/export information
        """
        path = Path(file_path)
        if not path.exists():
            return FileContext(path=str(path))

        if path.suffix != ".py":
            return FileContext(path=str(path))

        content = path.read_text(encoding="utf-8", errors="ignore")

        # Parse AST
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return FileContext(path=str(path))

        # Extract imports
        imports = self._extract_imports(tree)

        # Extract exports (__all__ or top-level definitions)
        exported_names, classes, functions = self._extract_definitions(tree, content)

        # Resolve dependencies to file paths
        depends_on = self._resolve_imports(imports, path)

        # Build result
        result = FileContext(
            path=str(path),
            imports=imports,
            exported_names=exported_names,
            classes=classes,
            functions=functions,
            depends_on=depends_on,
        )

        # Deposit trails if enabled
        if self.auto_deposit:
            result.trails_deposited = self._deposit_trails(str(path), result)

        return result

    async def analyze_directory(
        self,
        dir_path: str | Path,
        recursive: bool = True,
    ) -> list[FileContext]:
        """
        Analyze all Python files in a directory.

        Args:
            dir_path: Path to the directory
            recursive: Whether to search recursively

        Returns:
            List of FileContext results (sorted by path for determinism)
        """
        path = Path(dir_path)
        if not path.exists() or not path.is_dir():
            return []

        # Find all Python files
        if recursive:
            files = sorted(path.rglob("*.py"))
        else:
            files = sorted(path.glob("*.py"))

        # Filter out __pycache__
        files = [f for f in files if "__pycache__" not in str(f)]

        # Analyze each file
        results = []
        for py_file in files:
            result = await self.analyze_file(py_file)
            results.append(result)

        return results

    async def build_dependency_graph(
        self,
        dir_path: str | Path,
        recursive: bool = True,
    ) -> DependencyGraph:
        """
        Build a complete dependency graph for a directory.

        Args:
            dir_path: Path to the directory
            recursive: Whether to search recursively

        Returns:
            DependencyGraph with all files and edges
        """
        contexts = await self.analyze_directory(dir_path, recursive)

        graph = DependencyGraph()

        # Add all files as nodes
        for ctx in contexts:
            graph.files[ctx.path] = ctx

        # Build edges and used_by relationships
        all_paths = set(graph.files.keys())

        for ctx in contexts:
            for dep in ctx.depends_on:
                # Normalize the dependency path
                norm_dep = self._normalize_path(dep)

                # Find matching file in our graph
                for graph_path in all_paths:
                    if self._paths_match(graph_path, norm_dep):
                        # Add edge (ctx.path depends on graph_path)
                        edge = (ctx.path, graph_path)
                        if edge not in graph.edges:
                            graph.edges.append(edge)

                        # Update used_by on the dependency
                        if ctx.path not in graph.files[graph_path].used_by:
                            graph.files[graph_path].used_by.append(ctx.path)
                        break

        # Sort edges for determinism
        graph.edges.sort()

        # Sort used_by lists for determinism
        for ctx in graph.files.values():
            ctx.used_by.sort()

        return graph

    def _extract_imports(self, tree: ast.AST) -> list[ImportInfo]:
        """Extract import statements from AST."""
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportInfo(
                        module=alias.name,
                        names=[],
                        is_relative=False,
                        level=0,
                        line=node.lineno,
                    ))

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]

                imports.append(ImportInfo(
                    module=module,
                    names=names,
                    is_relative=node.level > 0,
                    level=node.level,
                    line=node.lineno,
                ))

        # Sort by line number for determinism
        return sorted(imports, key=lambda x: x.line)

    def _extract_definitions(
        self,
        tree: ast.AST,
        content: str,
    ) -> tuple[list[str], list[str], list[str]]:
        """Extract __all__, class names, and function names."""
        exported_names: list[str] = []
        classes: list[str] = []
        functions: list[str] = []

        for node in ast.iter_child_nodes(tree):
            # Look for __all__ assignment
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    exported_names.append(elt.value)

            # Top-level class definitions
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)

            # Top-level function definitions
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                # Skip private functions for exports
                if not node.name.startswith("_"):
                    functions.append(node.name)

        # Sort for determinism
        return sorted(exported_names), sorted(classes), sorted(functions)

    def _resolve_imports(
        self,
        imports: list[ImportInfo],
        source_path: Path,
    ) -> list[str]:
        """
        Resolve imports to file paths.

        Only returns otto.* imports for internal dependency tracking.
        """
        depends_on = []

        for imp in imports:
            if imp.is_relative:
                # Resolve relative import
                resolved = self._resolve_relative_import(imp, source_path)
                if resolved:
                    depends_on.append(resolved)
            elif imp.module.startswith("otto"):
                # Absolute otto.* import
                module_path = imp.module.replace(".", "/") + ".py"
                depends_on.append(module_path)

        # Sort and deduplicate for determinism
        return sorted(set(depends_on))

    def _resolve_relative_import(
        self,
        imp: ImportInfo,
        source_path: Path,
    ) -> Optional[str]:
        """Resolve a relative import to a file path."""
        # Calculate base directory based on level
        base = source_path.parent
        for _ in range(imp.level - 1):
            base = base.parent

        if imp.module:
            # from ..foo import bar
            module_path = imp.module.replace(".", "/")
            resolved = base / module_path

            # Try as package (__init__.py)
            package_init = resolved / "__init__.py"
            if package_init.exists():
                return str(package_init)

            # Try as module (.py)
            module_file = resolved.with_suffix(".py")
            if module_file.exists():
                return str(module_file)

            # Return the likely path even if not found
            return str(module_file)
        else:
            # from . import foo - importing from current package
            init_file = base / "__init__.py"
            if init_file.exists():
                return str(init_file)

        return None

    def _normalize_path(self, path: str) -> str:
        """Normalize a path for comparison."""
        return path.replace("\\", "/").lower()

    def _paths_match(self, path1: str, path2: str) -> bool:
        """Check if two paths refer to the same file."""
        norm1 = self._normalize_path(path1)
        norm2 = self._normalize_path(path2)

        # Exact match
        if norm1 == norm2:
            return True

        # One ends with the other
        if norm1.endswith(norm2) or norm2.endswith(norm1):
            return True

        return False

    def _deposit_trails(self, file_path: str, ctx: FileContext) -> int:
        """
        Deposit CONTEXT trails for file relationships.

        Returns:
            Number of trails deposited
        """
        count = 0

        # Deposit depends_on trails
        for dep in sorted(ctx.depends_on):
            trail = Trail(
                path=file_path,
                signal=f"depends_on:{dep}",
                trail_type=TrailType.CONTEXT,
                deposited_by=self.agent_id,
                strength=0.8,
            )
            self.store.deposit(trail)
            count += 1

        # Deposit class trails
        for cls in sorted(ctx.classes):
            trail = Trail(
                path=file_path,
                signal=f"defines_class:{cls}",
                trail_type=TrailType.CONTEXT,
                deposited_by=self.agent_id,
                strength=0.7,
            )
            self.store.deposit(trail)
            count += 1

        # Deposit function trails (top 10 only to avoid noise)
        for func in sorted(ctx.functions)[:10]:
            trail = Trail(
                path=file_path,
                signal=f"defines_function:{func}",
                trail_type=TrailType.CONTEXT,
                deposited_by=self.agent_id,
                strength=0.5,
            )
            self.store.deposit(trail)
            count += 1

        return count

    def get_summary(self, contexts: list[FileContext]) -> dict:
        """
        Generate summary statistics from analysis results.

        Returns:
            Summary dict with counts
        """
        total_files = len(contexts)
        total_imports = sum(len(c.imports) for c in contexts)
        total_classes = sum(len(c.classes) for c in contexts)
        total_functions = sum(len(c.functions) for c in contexts)
        total_trails = sum(c.trails_deposited for c in contexts)

        return {
            "total_files": total_files,
            "total_imports": total_imports,
            "total_classes": total_classes,
            "total_functions": total_functions,
            "total_trails_deposited": total_trails,
        }

    def format_graph(self, graph: DependencyGraph) -> str:
        """
        Format dependency graph as a readable report.

        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 60)
        lines.append("Dependency Graph Report")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Files:  {graph.node_count}")
        lines.append(f"Edges:  {graph.edge_count}")
        lines.append("")

        # Show most depended-upon files
        dependency_counts = {}
        for src, dst in graph.edges:
            dependency_counts[dst] = dependency_counts.get(dst, 0) + 1

        if dependency_counts:
            lines.append("-" * 60)
            lines.append("Most Used Files (by import count):")
            lines.append("-" * 60)

            for path, count in sorted(
                dependency_counts.items(),
                key=lambda x: (-x[1], x[0]),
            )[:10]:
                # Shorten path for display
                short = Path(path).name
                lines.append(f"  {count:3d}  {short}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)


# Module-level convenience functions
async def analyze_file(file_path: str | Path) -> FileContext:
    """Analyze a single file using default agent."""
    agent = ContextAgent()
    return await agent.analyze_file(file_path)


async def analyze_directory(dir_path: str | Path, recursive: bool = True) -> list[FileContext]:
    """Analyze a directory using default agent."""
    agent = ContextAgent()
    return await agent.analyze_directory(dir_path, recursive)


async def build_dependency_graph(dir_path: str | Path, recursive: bool = True) -> DependencyGraph:
    """Build dependency graph using default agent."""
    agent = ContextAgent()
    return await agent.build_dependency_graph(dir_path, recursive)


__all__ = [
    "ContextAgent",
    "FileContext",
    "ImportInfo",
    "DependencyGraph",
    "analyze_file",
    "analyze_directory",
    "build_dependency_graph",
]
