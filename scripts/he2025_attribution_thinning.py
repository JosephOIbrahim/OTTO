#!/usr/bin/env python3
"""
He2025 Attribution Thinning Script (Pass 2)

After the compliance->inspired cleanup (Pass 1), this script:
1. Strips [He2025] from misattributed patterns everywhere (Kahan, frozen,
   atomic, sort_keys -- none of these originate from the paper)
2. Thins general [He2025] boilerplate from non-canonical files

The [He2025] paper addresses GPU kernel-level batch-invariant operations
(RMSNorm, MatMul, Attention) in vLLM inference engines. It does NOT describe
Kahan summation, frozen dataclasses, atomic writes, JSON sort_keys, or any
other application-layer technique.

Goal: ~876 refs -> ~80 high-value annotations in architecturally significant files.

Usage:
    python scripts/he2025_attribution_thinning.py          # dry-run
    python scripts/he2025_attribution_thinning.py --apply   # write changes
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── Files where [He2025] is architecturally significant ───────────────
# Only UNIVERSAL rules apply here (strip misattributed patterns).
# Thinning rules do NOT apply -- these files keep their [He2025] annotations.
CANONICAL_FILES = {
    # Core determinism implementation
    ROOT / "src" / "otto" / "inference" / "kernel.py",
    ROOT / "src" / "otto" / "determinism.py",
    ROOT / "src" / "otto" / "core" / "livrps.py",
    ROOT / "src" / "otto" / "cognitive_orchestrator.py",
    ROOT / "src" / "otto" / "trails" / "store.py",
    ROOT / "src" / "otto" / "__init__.py",
    ROOT / "src" / "otto" / "decision_engine.py",
    ROOT / "src" / "otto" / "expert_router.py",
    ROOT / "src" / "otto" / "parameter_locker.py",
    ROOT / "src" / "otto" / "prism_detector.py",
    ROOT / "src" / "otto" / "framework_orchestrator.py",
    ROOT / "src" / "otto" / "voice_core" / "determinism.py",
    ROOT / "src" / "otto" / "inference" / "config.py",
    # Validation tooling (checks [He2025] patterns)
    ROOT / "src" / "otto" / "hooks" / "auto_validate.py",
    ROOT / "src" / "otto" / "agents" / "validation_agent.py",
    # Documentation
    ROOT / "CLAUDE.md",
    ROOT / "README.md",
    ROOT / "docs" / "DETERMINISM_SPECIFICATION.md",
    # Schemas
    ROOT / "src" / "otto" / "schema" / "constitutional.usda",
    ROOT / "src" / "otto" / "schema" / "cognitive.usda",
    # Determinism tests
    ROOT / "tests" / "test_determinism.py",
    ROOT / "tests" / "test_voice_core" / "test_determinism.py",
}

# ── Files to NEVER modify ─────────────────────────────────────────────
EXCLUDED_FILES = {
    ROOT / "docs" / "HE2025_DEEP_CONSISTENCY_AUDIT.md",
    ROOT / "docs" / "HE2025_KERNEL_COMPLIANCE_STRATEGY.md",
    ROOT / "docs" / "HE2025_DETERMINISM_ADDENDUM.md",
    ROOT / "CHANGELOG.md",
    ROOT / "THINKINGMACHINES_COMPLIANCE.md",
    ROOT / ".semgrep" / "orchestra-determinism.yaml",
    ROOT / "scripts" / "he2025_attribution_cleanup.py",
    ROOT / "scripts" / "he2025_attribution_thinning.py",
}

EXCLUDED_DIRS = {
    ROOT / ".git",
    ROOT / ".github",
    ROOT / "dist",
    ROOT / "node_modules",
}

EXTENSIONS = {
    ".py", ".md", ".jsx", ".tsx", ".js", ".ts", ".css",
    ".yaml", ".yml", ".toml", ".cfg", ".ini", ".usda",
}

# ═══════════════════════════════════════════════════════════════════════
# UNIVERSAL RULES — apply everywhere including canonical files.
# These strip [He2025] from things the paper did NOT describe.
# ═══════════════════════════════════════════════════════════════════════
UNIVERSAL_RULES: list[tuple[re.Pattern, str]] = [
    # ── Kahan summation (1965 technique, not from [He2025]) ───────────
    (re.compile(r"\[He2025\] (Uses? [Kk]ahan)"), r"\1"),
    (re.compile(r"\[He2025\] ([Kk]ahan summation)"), r"\1"),
    (re.compile(r"# \[He2025\] ([Kk]ahan summation)"), r"# \1"),
    (re.compile(r"# \[He2025\] (Use kahan_sum)"), r"# \1"),
    (re.compile(
        r"\[He2025\] (Uses deterministic iteration and Kahan summation)"
    ), r"\1"),
    (re.compile(
        r"\[He2025\] (Uses Kahan summation and sorted iteration for determinism)"
    ), r"\1"),
    (re.compile(
        r"# \[He2025\] (Use kahan_sum for batch-invariant accumulation)"
    ), r"# \1"),

    # ── FROZEN / immutable (standard SE, not from [He2025]) ──────────
    (re.compile(r"\[He2025\] FROZEN:"), "Immutable:"),
    (re.compile(
        r"\[He2025\]-inspired determinism: (frozen=True)"
    ), r"Immutable: \1"),
    (re.compile(r"\[He2025\]: (Frozen dataclasses prevent mutation)"), r"\1"),

    # ── Atomic writes (standard SE, not from [He2025]) ───────────────
    (re.compile(
        r"\[He2025\]-inspired determinism: (Atomic write)"
    ), r"\1"),
    (re.compile(r"\[He2025\] (Secure atomic)"), r"\1"),
    (re.compile(r"# \[He2025\] (FIXED Lua script)"), r"# \1"),

    # ── sort_keys (standard Python, not from [He2025]) ───────────────
    (re.compile(
        r"\[He2025\]-inspired determinism: (sort_keys=True)"
    ), r"Deterministic: \1"),
    (re.compile(
        r"\[He2025\]: (Deterministic key ordering via sort_keys)"
    ), r"\1"),
    (re.compile(
        r"# \[He2025\]-inspired determinism: (sort_keys=True)"
    ), r"# Deterministic: \1"),

    # ── Fixed non-evaluation-order constants (standard SE) ───────────
    (re.compile(r"\[He2025\] (DETERMINISTIC:)"), r"\1"),
    (re.compile(r"\[He2025\] (Uses fixed hash)"), r"\1"),
    (re.compile(r"# \[He2025\] (Fixed output format)"), r"# \1"),
    (re.compile(r"\[He2025\] (FIXED: No runtime)"), r"\1"),
    (re.compile(
        r"\[He2025\]-inspired determinism: (FIXED schemas)"
    ), r"\1"),
]

# ═══════════════════════════════════════════════════════════════════════
# THINNING RULES — apply only in non-canonical files.
# These strip general [He2025] boilerplate to reduce annotation density.
# Applied in order, most specific first.
# ═══════════════════════════════════════════════════════════════════════
THIN_RULES: list[tuple[re.Pattern, str]] = [
    # ── Module docstring headers ─────────────────────────────────────
    # "Determinism (inspired by [He2025]):" → "Determinism:"
    (re.compile(r"Determinism \(inspired by \[He2025\]\):"), "Determinism:"),
    # "[He2025]-inspired determinism:" → "Determinism:"
    (re.compile(r"\[He2025\]-inspired determinism:"), "Determinism:"),
    # "[He2025]-inspired determinism" (no colon) → "Determinism"
    (re.compile(r"\[He2025\]-inspired determinism"), "Determinism"),
    # "[He2025]-inspired batch-invariance" → "Batch-invariance"
    (re.compile(r"\[He2025\]-inspired (batch-invariance)"), r"\1"),

    # ── ThinkingMachines prefixes ────────────────────────────────────
    # "ThinkingMachines [He2025]-inspired determinism" → "Determinism"
    (re.compile(r"ThinkingMachines \[He2025\]-inspired determinism"), "Determinism"),
    # "ThinkingMachines [He2025]-inspired" → "Deterministic"
    (re.compile(r"ThinkingMachines \[He2025\]-inspired"), "Deterministic"),
    # "ThinkingMachines [He2025]: <text>" → "<text>"
    (re.compile(r"ThinkingMachines \[He2025\]: "), ""),
    (re.compile(r"ThinkingMachines \[He2025\]:"), ""),

    # ── Inline comment citations ─────────────────────────────────────
    # "# [He2025]: <text>" → "# <text>"
    (re.compile(r"# \[He2025\]: "), "# "),
    # "# [He2025] <text>" → "# <text>"
    (re.compile(r"# \[He2025\] "), "# "),

    # ── Parenthetical citations ──────────────────────────────────────
    # "(inspired by [He2025])" → ""
    (re.compile(r" \(inspired by \[He2025\]\)"), ""),
    # "Per [He2025]: <text>" (capital, start of statement) → "<text>"
    (re.compile(r"Per \[He2025\]:\s+"), ""),
    # " per [He2025]:" (lowercase, mid-sentence introducing list) → ":"
    (re.compile(r" per \[He2025\]:"), ":"),
    # " per [He2025]" / " Per [He2025]" (bare, no colon) → ""
    (re.compile(r" [Pp]er \[He2025\]"), ""),

    # ── Remaining patterns ───────────────────────────────────────────
    # "[He2025]-inspired" → "Deterministic"
    (re.compile(r"\[He2025\]-inspired"), "Deterministic"),
    # "[He2025]: <text>" (colon prefix) → "<text>"
    (re.compile(r"\[He2025\]:\s+"), ""),
    # "[He2025] " (bare prefix with trailing space) → ""
    (re.compile(r"\[He2025\] "), ""),
    # " [He2025]" (bare suffix with leading space) → ""
    (re.compile(r" \[He2025\]"), ""),
]


def _is_excluded(path: Path) -> bool:
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


def _is_canonical(path: Path) -> bool:
    return path.resolve() in CANONICAL_FILES


def _collect_files() -> list[Path]:
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


def _apply_rules(
    text: str, rules: list[tuple[re.Pattern, str]]
) -> tuple[str, list[tuple[int, str, str]]]:
    changes: list[tuple[int, str, str]] = []
    lines = text.split("\n")
    new_lines = []

    for line_idx, line in enumerate(lines, start=1):
        original = line
        for pattern, replacement in rules:
            if pattern.search(line):
                line = pattern.sub(replacement, line)
        if line != original:
            changes.append((line_idx, original.strip(), line.strip()))
        new_lines.append(line)

    return "\n".join(new_lines), changes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="He2025 attribution thinning (Pass 2)"
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Write changes (default: dry-run)",
    )
    args = parser.parse_args()

    files = _collect_files()
    total_changes = 0
    files_changed = 0
    canonical_changes = 0
    thin_changes = 0

    mode = "APPLYING" if args.apply else "DRY RUN"
    print(f"{mode}: Scanning {len(files)} files...\n")

    for fpath in files:
        try:
            text = fpath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue

        # Skip files with no [He2025] references at all
        if "[He2025]" not in text:
            continue

        canonical = _is_canonical(fpath)

        # Phase 1: Universal rules (apply everywhere)
        new_text, uni_changes = _apply_rules(text, UNIVERSAL_RULES)

        # Phase 2: Thinning rules (non-canonical only)
        thin_ch = []
        if not canonical:
            new_text, thin_ch = _apply_rules(new_text, THIN_RULES)

        all_changes = uni_changes + thin_ch
        if not all_changes:
            continue

        files_changed += 1
        canonical_changes += len(uni_changes)
        thin_changes += len(thin_ch)

        rel = fpath.relative_to(ROOT)
        tag = " [CANONICAL]" if canonical else ""
        print(f"  {rel}{tag}  ({len(all_changes)} changes)")
        for line_no, old, new in all_changes[:5]:  # Show first 5
            old_safe = old[:80].encode("ascii", "replace").decode()
            new_safe = new[:80].encode("ascii", "replace").decode()
            print(f"    L{line_no}: {old_safe}")
            print(f"        -> {new_safe}")
        if len(all_changes) > 5:
            print(f"    ... and {len(all_changes) - 5} more")

        total_changes += len(all_changes)

        if args.apply:
            fpath.write_text(new_text, encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"{'APPLIED' if args.apply else 'WOULD APPLY'}: "
          f"{total_changes} changes across {files_changed} files")
    print(f"  Universal (misattributed): {canonical_changes}")
    print(f"  Thinning (boilerplate):    {thin_changes}")

    if not args.apply and total_changes > 0:
        print("\nRe-run with --apply to write changes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
