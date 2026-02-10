#!/usr/bin/env python3
"""
Seed Initial Trails for OTTO OS
================================

Analyzes existing OTTO OS source files and deposits initial trails:
- QUALITY trails for determinism
- CONTEXT trails for import dependencies
- PATTERN trails for recurring code patterns

Determinism:
- Deposits in deterministic order (sorted paths)
- Uses batch-invariant operations
- Fixed signal patterns

Usage:
    python scripts/seed_trails.py [--dry-run] [--verbose]
"""

import argparse
import ast
import re
import sys
from pathlib import Path

# Add OTTO_OS to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from otto.trails import Trail, TrailType, TrailStore


def analyze_file_he2025(path: Path, content: str) -> tuple[list[str], list[str]]:
    """
    Analyze Python file for determinism.

    Returns:
        (violations, compliances) - lists of signal strings
    """
    violations = []
    compliances = []

    # Check for max() on dict.items()
    if re.search(r'max\s*\(\s*\w+\.items\s*\(\s*\)', content):
        violations.append("max_on_dict_items")

    # Check for iterating over set without sorting
    if re.search(r'for\s+\w+\s+in\s+set\s*\(', content):
        violations.append("unsorted_set_iteration")

    # Check for unseeded random
    if 'import random' in content or 'from random' in content:
        if not re.search(r'random\.seed\s*\(', content):
            if re.search(r'random\.(choice|sample|shuffle|randint|random)\s*\(', content):
                violations.append("unseeded_random")

    # Check for sum() without sorting (potential batch variance)
    if re.search(r'sum\s*\(\s*\[', content):
        if 'kahan_sum' not in content:
            violations.append("sum_without_kahan")

    # Check for determinism compliance patterns
    if 'sorted_max' in content or 'from otto.determinism import' in content:
        compliances.append("uses_determinism_module")

    if 'kahan_sum' in content:
        compliances.append("uses_kahan_sum")

    if re.search(r'sorted\s*\(\s*(set|dict)', content):
        compliances.append("sorts_collections")

    if re.search(r'random\.seed\s*\(\s*DETERMINISM_SEED', content):
        compliances.append("uses_fixed_seed")

    if 'ORDER BY' in content.upper() and ('ASC' in content.upper() or 'DESC' in content.upper()):
        compliances.append("sql_ordered")

    return violations, compliances


def extract_imports(path: Path, content: str) -> list[str]:
    """
    Extract import dependencies from Python file.

    Returns:
        List of imported module paths (otto.* only)
    """
    imports = []

    try:
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith('otto.'):
                        imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith('otto'):
                    imports.append(node.module)
    except SyntaxError:
        pass  # Skip files with syntax errors

    return sorted(set(imports))


def detect_patterns(path: Path, content: str) -> list[str]:
    """
    Detect recurring code patterns.

    Returns:
        List of pattern signals
    """
    patterns = []

    # Singleton pattern
    if re.search(r'_default_\w+\s*=\s*None', content) and 'def get_' in content:
        patterns.append("singleton_pattern")

    # Dataclass pattern
    if '@dataclass' in content:
        patterns.append("dataclass_pattern")

    # Context manager pattern
    if '@contextmanager' in content or '__enter__' in content:
        patterns.append("context_manager_pattern")

    # ABC pattern
    if 'ABC' in content and '@abstractmethod' in content:
        patterns.append("abc_pattern")

    # Enum pattern
    if '(Enum)' in content or 'from enum import' in content:
        patterns.append("enum_pattern")

    # SQLite pattern
    if 'sqlite3' in content and 'CREATE TABLE' in content:
        patterns.append("sqlite_pattern")

    # MCP server pattern
    if 'mcp.server' in content or '@server.list_tools' in content:
        patterns.append("mcp_server_pattern")

    return sorted(patterns)


def relative_path(base: Path, path: Path) -> str:
    """Convert to relative path string for trail storage."""
    try:
        return str(path.relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def seed_trails(
    base_path: Path,
    store: TrailStore,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, int]:
    """
    Seed trails for all Python files in the codebase.

    Returns:
        Stats dict with trail counts
    """
    stats = {
        "files_analyzed": 0,
        "quality_trails": 0,
        "context_trails": 0,
        "pattern_trails": 0,
        "violations_found": 0,
        "compliances_found": 0,
    }

    # Find all Python files in src/
    src_path = base_path / "src"
    if not src_path.exists():
        print(f"Error: {src_path} does not exist")
        return stats

    python_files = sorted(src_path.rglob("*.py"))

    for py_file in python_files:
        # Skip __pycache__
        if "__pycache__" in str(py_file):
            continue

        rel_path = relative_path(base_path, py_file)
        content = py_file.read_text(encoding="utf-8", errors="ignore")

        if verbose:
            print(f"Analyzing: {rel_path}")

        stats["files_analyzed"] += 1

        # Determinism analysis
        violations, compliances = analyze_file_he2025(py_file, content)

        for violation in violations:
            stats["violations_found"] += 1
            if not dry_run:
                trail = Trail(
                    path=rel_path,
                    signal=f"he2025_violation:{violation}",
                    trail_type=TrailType.QUALITY,
                    deposited_by="seed_trails",
                    strength=1.0,
                )
                store.deposit(trail)
                stats["quality_trails"] += 1

            if verbose:
                print(f"  [VIOLATION] {violation}")

        for compliance in compliances:
            stats["compliances_found"] += 1
            if not dry_run:
                trail = Trail(
                    path=rel_path,
                    signal=f"determinism_check_passed:{compliance}",
                    trail_type=TrailType.QUALITY,
                    deposited_by="seed_trails",
                    strength=1.0,
                )
                store.deposit(trail)
                stats["quality_trails"] += 1

            if verbose:
                print(f"  [COMPLIANT] {compliance}")

        # Import dependencies
        imports = extract_imports(py_file, content)

        for imp in imports:
            # Convert module path to file path
            imp_file = imp.replace(".", "/") + ".py"
            if not dry_run:
                trail = Trail(
                    path=rel_path,
                    signal=f"depends_on:{imp_file}",
                    trail_type=TrailType.CONTEXT,
                    deposited_by="seed_trails",
                    strength=0.8,
                )
                store.deposit(trail)
                stats["context_trails"] += 1

            if verbose:
                print(f"  [DEPENDS] {imp_file}")

        # Pattern detection
        patterns = detect_patterns(py_file, content)

        for pattern in patterns:
            if not dry_run:
                trail = Trail(
                    path=rel_path,
                    signal=pattern,
                    trail_type=TrailType.PATTERN,
                    deposited_by="seed_trails",
                    strength=0.9,
                )
                store.deposit(trail)
                stats["pattern_trails"] += 1

            if verbose:
                print(f"  [PATTERN] {pattern}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Seed initial trails for OTTO OS")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without depositing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    base_path = Path(__file__).parent.parent

    if args.dry_run:
        print("=== DRY RUN MODE ===")
        store = None
    else:
        store = TrailStore()
        # Decay old trails first
        pruned = store.decay_all()
        print(f"Decayed trails: {pruned} pruned")

    print(f"\nSeeding trails for: {base_path}")
    print("-" * 50)

    stats = seed_trails(
        base_path,
        store,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    print("-" * 50)
    print(f"Files analyzed:    {stats['files_analyzed']}")
    print(f"Quality trails:    {stats['quality_trails']}")
    print(f"Context trails:    {stats['context_trails']}")
    print(f"Pattern trails:    {stats['pattern_trails']}")
    print(f"Violations found:  {stats['violations_found']}")
    print(f"Compliances found: {stats['compliances_found']}")

    if not args.dry_run and store:
        total = store.count_trails()
        print(f"\nTotal trails in database: {total}")


if __name__ == "__main__":
    main()
