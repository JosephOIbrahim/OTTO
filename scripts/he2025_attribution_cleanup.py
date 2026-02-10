#!/usr/bin/env python3
"""
He2025 Attribution Cleanup Script

Softens "[He2025] compliant/compliance" claims to "inspired by [He2025]"
across the OTTO_OS codebase. The [He2025] paper addresses GPU kernel-level
batch-invariant operations; OTTO applies these *principles* at the
application layer — this script corrects the attribution accordingly.

Usage:
    python scripts/he2025_attribution_cleanup.py          # dry-run (report only)
    python scripts/he2025_attribution_cleanup.py --apply   # write changes
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ── Project root ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent

# ── Files to NEVER modify ─────────────────────────────────────────────
EXCLUDED_FILES = {
    ROOT / "docs" / "HE2025_DEEP_CONSISTENCY_AUDIT.md",
    ROOT / "docs" / "HE2025_KERNEL_COMPLIANCE_STRATEGY.md",
    ROOT / "docs" / "HE2025_DETERMINISM_ADDENDUM.md",
    ROOT / "CHANGELOG.md",
    ROOT / ".semgrep" / "orchestra-determinism.yaml",
    ROOT / "scripts" / "he2025_attribution_cleanup.py",  # self-exclusion
}

EXCLUDED_DIRS = {
    ROOT / ".git",
    ROOT / ".github" / "workflows",
    ROOT / "dist",
    ROOT / "node_modules",
    ROOT / "__pycache__",
}

# ── Replacement rules (applied in order, most specific first) ─────────
# Each tuple: (compiled_regex, replacement_string)
RULES: list[tuple[re.Pattern, str]] = [
    # Rule 1: Full "ThinkingMachines [He2025] Compliant Execution" header
    (
        re.compile(r"ThinkingMachines \[He2025\] [Cc]ompliant [Ee]xecution"),
        "Deterministic Execution (inspired by [He2025])",
    ),
    # Rule 2: "ThinkingMachines [He2025] Compliance:" docstring headers
    (
        re.compile(r"ThinkingMachines \[He2025\] [Cc]ompliance:"),
        "Determinism (inspired by [He2025]):",
    ),
    # Rule 3: "[He2025] compliant deterministic"
    (
        re.compile(r"\[He2025\] compliant deterministic"),
        "deterministic (inspired by [He2025])",
    ),
    # Rule 4: "[He2025] batch-invariance compliance"
    (
        re.compile(r"\[He2025\] batch-invariance compliance"),
        "batch-invariance (inspired by [He2025])",
    ),
    # Rule 5: "CRITICAL for [He2025] compliance"
    (
        re.compile(r"CRITICAL for \[He2025\] compliance"),
        "Deterministic ordering (inspired by [He2025])",
    ),
    # Rule 6: "for [He2025] compliance" (generic)
    (
        re.compile(r"for \[He2025\] compliance"),
        "for determinism (inspired by [He2025])",
    ),
    # Rule 7: "[He2025] ThinkingMachines Compliance:" (reversed word order)
    (
        re.compile(r"\[He2025\] ThinkingMachines [Cc]ompliance:"),
        "Determinism (inspired by [He2025]):",
    ),
    # Rule 8: "[He2025]-compliant" (hyphenated form)
    (
        re.compile(r"\[He2025\]-[Cc]ompliant"),
        "[He2025]-inspired",
    ),
    # Rule 9: "[He2025] Batch-Invariance Compliance"
    (
        re.compile(r"\[He2025\] [Bb]atch-[Ii]nvariance [Cc]ompliance"),
        "[He2025]-inspired batch-invariance",
    ),
    # Rule 10: "[He2025] determinism compliance" / "[He2025] Determinism Compliance"
    (
        re.compile(r"\[He2025\] [Dd]eterminism [Cc]ompliance"),
        "[He2025]-inspired determinism",
    ),
    # Rule 11: "[He2025] Partial compliance"
    (
        re.compile(r"\[He2025\] [Pp]artial compliance"),
        "[He2025] partial conformance",
    ),
    # Rule 12: Catch-all remaining "[He2025] compliant/compliance/..." (space-separated)
    (
        re.compile(r"\[He2025\] [Cc]omplian\w*"),
        "[He2025]-inspired determinism",
    ),
    # Rule 13: Catch remaining "compliant" near [He2025] with intervening words
    (
        re.compile(r"\[He2025\]\S*[ -][Cc]omplian\w*"),
        "[He2025]-inspired determinism",
    ),
    # --- Reverse-order patterns (compliance BEFORE [He2025]) ---
    # Rule 14: "ThinkingMachines Batch-Invariance Compliance [He2025]:"
    (
        re.compile(r"ThinkingMachines Batch-Invariance [Cc]ompliance \[He2025\]:"),
        "Batch-Invariance (inspired by [He2025]):",
    ),
    # Rule 15: "ThinkingMachines Compliance [He2025]:"
    (
        re.compile(r"ThinkingMachines [Cc]ompliance \[He2025\]:"),
        "Determinism (inspired by [He2025]):",
    ),
    # Rule 16: "ThinkingMachines Compliance**: [He2025]" (markdown bold)
    (
        re.compile(r"ThinkingMachines [Cc]ompliance\*\*:? \[He2025\]"),
        "Determinism (inspired by [He2025])**",
    ),
    # Rule 17: "ThinkingMachines compliance [He2025]" (plain)
    (
        re.compile(r"ThinkingMachines [Cc]ompliance \[He2025\]"),
        "Determinism (inspired by [He2025])",
    ),
    # Rule 18: "determinism compliance per [He2025]"
    (
        re.compile(r"determinism compliance per (?:ThinkingMachines )?\[He2025\]"),
        "determinism (inspired by [He2025])",
    ),
    # Rule 19: "Determinism Compliance ([He2025])"
    (
        re.compile(r"[Dd]eterminism [Cc]ompliance \(\[He2025\]\)"),
        "Determinism (Inspired by [He2025])",
    ),
    # Rule 20: "compliance with [He2025]"
    (
        re.compile(r"[Cc]ompliance with \[He2025\]"),
        "alignment with [He2025]",
    ),
]

# ── File extensions to process ────────────────────────────────────────
EXTENSIONS = {
    ".py", ".md", ".jsx", ".tsx", ".js", ".ts", ".css",
    ".yaml", ".yml", ".toml", ".cfg", ".ini", ".usda",
}


def _is_excluded(path: Path) -> bool:
    """Check if a file should be skipped."""
    resolved = path.resolve()
    if resolved in EXCLUDED_FILES:
        return True
    for d in EXCLUDED_DIRS:
        try:
            resolved.relative_to(d)
            return True
        except ValueError:
            pass
    return False


def _collect_files() -> list[Path]:
    """Walk the project tree and collect eligible files."""
    files = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in EXTENSIONS:
            continue
        if _is_excluded(p):
            continue
        files.append(p)
    return sorted(files)


def _apply_rules(text: str) -> tuple[str, list[tuple[int, str, str, str]]]:
    """Apply all replacement rules to text, return (new_text, changes).

    Each change is (line_number, rule_description, old_fragment, new_fragment).
    """
    changes: list[tuple[int, str, str, str]] = []
    lines = text.split("\n")
    new_lines = []

    for line_idx, line in enumerate(lines, start=1):
        original_line = line
        for pattern, replacement in RULES:
            if pattern.search(line):
                match = pattern.search(line)
                if match:
                    old_frag = match.group(0)
                    line = pattern.sub(replacement, line)
                    changes.append((line_idx, pattern.pattern, old_frag, replacement))
        new_lines.append(line)

    return "\n".join(new_lines), changes


def main() -> int:
    parser = argparse.ArgumentParser(description="He2025 attribution cleanup")
    parser.add_argument(
        "--apply", action="store_true",
        help="Write changes to files (default: dry-run only)",
    )
    args = parser.parse_args()

    files = _collect_files()
    total_changes = 0
    files_changed = 0

    print(f"{'APPLYING' if args.apply else 'DRY RUN'}: Scanning {len(files)} files...\n")

    for fpath in files:
        try:
            text = fpath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue

        new_text, changes = _apply_rules(text)
        if not changes:
            continue

        files_changed += 1
        rel = fpath.relative_to(ROOT)
        print(f"  {rel}  ({len(changes)} replacement{'s' if len(changes) != 1 else ''})")
        for line_no, _rule, old, new in changes:
            print(f"    L{line_no}: {old!r} -> {new!r}")

        total_changes += len(changes)

        if args.apply:
            fpath.write_text(new_text, encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"{'APPLIED' if args.apply else 'WOULD APPLY'}: "
          f"{total_changes} replacements across {files_changed} files")

    if not args.apply and total_changes > 0:
        print("\nRe-run with --apply to write changes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
