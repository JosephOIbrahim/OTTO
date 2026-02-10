"""
Auto-Validation Hook for [He2025]-inspired determinism
=============================================

Runs after Edit/Write operations on OTTO OS files and checks for
determinism (inspired by [He2025]).

Detects and deposits trails for:
- sorted_max() vs max() on dict items
- kahan_sum() vs sum() for float aggregation
- sorted(set(...)) vs raw set iteration
- Seeded random operations

Determinism (inspired by [He2025]):
- Fixed pattern matching order
- Deterministic trail deposits
- Same code → same validation result
"""

import re
from typing import List, Optional, Tuple

from .base import Hook, HookContext, HookEvent, HookResult
from ..trails import Trail, TrailStore, TrailType, get_store


# =============================================================================
# Pattern Definitions
# =============================================================================

# Patterns that indicate potential [He2025] violations
VIOLATION_PATTERNS = [
    # max() on dict items without sorted_max
    (
        r"max\s*\(\s*\w+\.items\(\)\s*,",
        "max_on_dict_items",
        "Use sorted_max() from otto.determinism instead of max(dict.items())",
    ),
    # max() on dict values
    (
        r"max\s*\(\s*\w+\.values\(\)\s*\)",
        "max_on_dict_values",
        "Use sorted_max_value() from otto.determinism for deterministic max",
    ),
    # sum() on float values (might need kahan_sum)
    # [He2025] Match standalone sum() calls on lists, not kahan_sum
    (
        r"(?<![a-z_])sum\s*\(\s*\[",
        "sum_on_floats",
        "Consider kahan_sum() from otto.determinism for batch-invariant summation",
    ),
    # Iterating over set directly
    (
        r"for\s+\w+\s+in\s+set\s*\(",
        "iterate_set",
        "Use sorted(set(...)) for deterministic iteration order",
    ),
    # Iterating over dict.keys() without sorting
    (
        r"for\s+\w+\s+in\s+\w+\.keys\(\)\s*:",
        "iterate_dict_keys",
        "Use sorted(dict.keys()) or deterministic_dict_iter() for determinism",
    ),
    # random without seed
    (
        r"random\.(choice|shuffle|sample|randint|random)\s*\(",
        "unseeded_random",
        "Use DETERMINISM_SEED from otto.determinism before random operations",
    ),
]

# Patterns that indicate good [He2025]-inspired determinism
COMPLIANCE_PATTERNS = [
    (r"sorted_max\s*\(", "uses_sorted_max"),
    (r"sorted_max_value\s*\(", "uses_sorted_max_value"),
    (r"sorted_max_key\s*\(", "uses_sorted_max_key"),
    (r"kahan_sum\s*\(", "uses_kahan_sum"),
    (r"kahan_weighted_sum\s*\(", "uses_kahan_weighted_sum"),
    (r"sorted\s*\(\s*set\s*\(", "uses_sorted_set"),
    (r"deterministic_dict_iter\s*\(", "uses_deterministic_dict_iter"),
    (r"deterministic_dict_values\s*\(", "uses_deterministic_dict_values"),
    (r"DETERMINISM_SEED", "uses_determinism_seed"),
    (r"COGNITIVE_TILE_SIZE", "uses_cognitive_tile_size"),
    (r"from\s+otto\.determinism\s+import", "imports_determinism"),
]


# =============================================================================
# Validation Logic
# =============================================================================

def check_determinism_patterns(content: str) -> Tuple[List[dict], List[dict]]:
    """
    Check code content for determinism (inspired by [He2025]).

    Args:
        content: Python source code to check

    Returns:
        Tuple of (violations, compliances)
        Each is a list of dicts with pattern info
    """
    violations = []
    compliances = []

    # Check for violations
    for pattern, violation_type, message in VIOLATION_PATTERNS:
        matches = list(re.finditer(pattern, content, re.MULTILINE))
        for match in matches:
            # Find line number
            line_num = content[:match.start()].count('\n') + 1
            violations.append({
                "type": violation_type,
                "line": line_num,
                "match": match.group(),
                "message": message,
            })

    # Check for compliance patterns
    for pattern, compliance_type in COMPLIANCE_PATTERNS:
        if re.search(pattern, content):
            compliances.append({
                "type": compliance_type,
            })

    return violations, compliances


# Backward-compat alias (renamed from check_he2025_compliance)
check_he2025_compliance = check_determinism_patterns


def extract_new_content(tool_output: str) -> Optional[str]:
    """
    Extract the new file content from an Edit/Write tool output.

    Args:
        tool_output: Output from Edit or Write tool

    Returns:
        The new file content, or None if not found
    """
    # The tool output format varies, try to extract content
    if not tool_output:
        return None

    # For Write tool, the content is typically echoed back
    # For Edit tool, we might need to read the file again
    # This is a simplified extraction - real implementation would be more robust

    if isinstance(tool_output, str):
        return tool_output
    elif isinstance(tool_output, dict):
        return tool_output.get("content") or tool_output.get("new_content")

    return None


# =============================================================================
# Hook Implementation
# =============================================================================

class AutoValidateHook(Hook):
    """
    Validates OTTO OS code for determinism (inspired by [He2025]) after edits.

    Triggers: POST_TOOL_USE on Edit/Write for OTTO files
    Deposits:
        - QUALITY trails for determinism_check_passed or determinism_violation:lineN
        - Surfaces violations in context injection
    """

    def __init__(self, store: Optional[TrailStore] = None):
        """
        Initialize the auto-validate hook.

        Args:
            store: TrailStore instance (uses default if not provided)
        """
        self._store = store

    @property
    def store(self) -> TrailStore:
        """Get the trail store, creating default if needed."""
        if self._store is None:
            self._store = get_store()
        return self._store

    @property
    def name(self) -> str:
        return "auto_validate_determinism"

    @property
    def events(self) -> List[HookEvent]:
        return [HookEvent.POST_TOOL_USE]

    @property
    def priority(self) -> int:
        return 25  # Validation hooks run early

    def should_run(self, context: HookContext) -> bool:
        """Only run for Edit/Write on OTTO files."""
        if context.event != HookEvent.POST_TOOL_USE:
            return False

        if context.tool_name not in {"Edit", "Write"}:
            return False

        path = context.get_target_path()
        return self.is_otto_file(path)

    def process(self, context: HookContext) -> HookResult:
        """
        Validate edited code and deposit trails.

        Args:
            context: Hook context with tool information

        Returns:
            HookResult with validation outcome
        """
        path = context.get_target_path()
        if not path:
            return HookResult(
                hook_name=self.name,
                success=False,
                error="No file path found in context",
            )

        # Get the new content
        content = None

        # Try to extract from tool output
        if context.tool_output:
            content = extract_new_content(context.tool_output)

        # If we couldn't get content from output, try reading the file
        if not content:
            try:
                from pathlib import Path
                file_path = Path(path)
                if file_path.exists() and file_path.suffix == ".py":
                    content = file_path.read_text(encoding="utf-8")
            except Exception:
                pass

        if not content:
            return HookResult(
                hook_name=self.name,
                success=True,
                data={"skipped": True, "reason": "Could not read file content"},
            )

        # Check compliance
        violations, compliances = check_determinism_patterns(content)

        trails_deposited = 0
        context_lines = []

        # Deposit violation trails
        for violation in violations:
            signal = f"determinism_violation:{violation['type']}:line{violation['line']}"
            self.store.deposit(Trail(
                trail_type=TrailType.QUALITY,
                path=path,
                signal=signal,
                deposited_by=self.name,
                metadata={"message": violation["message"]},
            ))
            trails_deposited += 1

            context_lines.append(
                f"[He2025] Line {violation['line']}: {violation['message']}"
            )

        # Deposit compliance trails if any good patterns found
        if compliances and not violations:
            self.store.deposit(Trail(
                trail_type=TrailType.QUALITY,
                path=path,
                signal="determinism_check_passed",
                deposited_by=self.name,
                metadata={"patterns": [c["type"] for c in compliances]},
            ))
            trails_deposited += 1
        elif compliances:
            # Partial compliance - has good patterns but also violations
            self.store.deposit(Trail(
                trail_type=TrailType.QUALITY,
                path=path,
                signal="determinism_partial",
                deposited_by=self.name,
                metadata={
                    "good_patterns": [c["type"] for c in compliances],
                    "violation_count": len(violations),
                },
            ))
            trails_deposited += 1

        # Build context injection
        context_injection = None
        if context_lines:
            context_injection = (
                "\n[He2025 Validation]\n" +
                "\n".join(context_lines) +
                "\n[End Validation]\n"
            )

        return HookResult(
            hook_name=self.name,
            success=True,
            context_injection=context_injection,
            trails_deposited=trails_deposited,
            data={
                "violations": violations,
                "compliances": compliances,
                "file": path,
            },
        )


# =============================================================================
# Standalone Validation Function
# =============================================================================

def validate_file(file_path: str) -> dict:
    """
    Validate a file for determinism (inspired by [He2025]).

    Standalone function for use outside hook context.

    Args:
        file_path: Path to Python file

    Returns:
        Dict with violations, compliances, and is_compliant flag
    """
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    if path.suffix != ".py":
        return {"error": "Not a Python file"}

    content = path.read_text(encoding="utf-8")
    violations, compliances = check_determinism_patterns(content)

    return {
        "file": str(path),
        "violations": violations,
        "compliances": compliances,
        "is_compliant": len(violations) == 0,
        "compliance_score": len(compliances) / (len(violations) + len(compliances) + 0.001),
    }


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AutoValidateHook",
    "check_determinism_patterns",
    "validate_file",
    "VIOLATION_PATTERNS",
    "COMPLIANCE_PATTERNS",
]
