#!/usr/bin/env python3
"""
Seed Trails Using OTTO OS Agents
=================================

Uses ValidationAgent and ContextAgent to analyze the OTTO OS codebase
and deposit comprehensive trails:
- QUALITY trails for [He2025] compliance (ValidationAgent)
- CONTEXT trails for import dependencies (ContextAgent)

ThinkingMachines [He2025] Compliance:
- Processes files in sorted order
- Uses deterministic agents
- Fixed signal patterns

Usage:
    python scripts/seed_trails_agents.py [--dry-run] [--verbose]
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add OTTO_OS to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from otto.agents import ValidationAgent, ContextAgent
from otto.trails import TrailStore, get_store


async def seed_with_agents(
    base_path: Path,
    store: TrailStore,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Seed trails using ValidationAgent and ContextAgent.

    Returns:
        Stats dict with trail counts
    """
    stats = {
        "files_analyzed": 0,
        "validation_trails": 0,
        "context_trails": 0,
        "compliant_files": 0,
        "non_compliant_files": 0,
        "total_classes": 0,
        "total_functions": 0,
        "total_imports": 0,
    }

    src_path = base_path / "src"
    if not src_path.exists():
        print(f"Error: {src_path} does not exist")
        return stats

    # Create agents
    if dry_run:
        # Use None store for dry run - agents will skip trail deposition
        val_agent = ValidationAgent(store=None, agent_id="seed_validator", auto_deposit=False)
        ctx_agent = ContextAgent(store=None, agent_id="seed_context", auto_deposit=False, base_path=base_path)
    else:
        val_agent = ValidationAgent(store=store, agent_id="seed_validator", auto_deposit=True)
        ctx_agent = ContextAgent(store=store, agent_id="seed_context", auto_deposit=True, base_path=base_path)

    print(f"\n{'='*60}")
    print("Phase 1: Validation Analysis ([He2025] Compliance)")
    print(f"{'='*60}")

    # Run validation on entire src directory
    val_results = await val_agent.validate_directory(src_path, recursive=True)

    for result in val_results:
        stats["files_analyzed"] += 1
        stats["validation_trails"] += result.trails_deposited

        if result.is_compliant:
            stats["compliant_files"] += 1
        else:
            stats["non_compliant_files"] += 1

        if verbose:
            status = "OK" if result.is_compliant else f"VIOLATIONS: {result.error_count}"
            rel_path = Path(result.path).relative_to(base_path) if base_path in Path(result.path).parents else result.path
            print(f"  [{status:20}] {rel_path}")

            for finding in result.findings:
                print(f"      L{finding.line}: [{finding.code}] {finding.message}")

    # Print validation summary
    val_summary = val_agent.get_summary(val_results)
    print(f"\nValidation Summary:")
    print(f"  Files:      {val_summary['total_files']}")
    print(f"  Compliant:  {val_summary['compliant_files']} ({val_summary['compliance_rate']}%)")
    print(f"  Violations: {val_summary['total_errors']}")
    print(f"  Trails:     {val_summary['total_trails_deposited']}")

    print(f"\n{'='*60}")
    print("Phase 2: Context Analysis (Dependencies)")
    print(f"{'='*60}")

    # Run context analysis
    ctx_results = await ctx_agent.analyze_directory(src_path, recursive=True)

    for ctx in ctx_results:
        stats["context_trails"] += ctx.trails_deposited
        stats["total_classes"] += len(ctx.classes)
        stats["total_functions"] += len(ctx.functions)
        stats["total_imports"] += len(ctx.imports)

        if verbose:
            rel_path = Path(ctx.path).relative_to(base_path) if base_path in Path(ctx.path).parents else ctx.path
            print(f"  {rel_path}")
            print(f"      Classes: {len(ctx.classes)}, Functions: {len(ctx.functions)}, Imports: {len(ctx.imports)}")

            if ctx.classes:
                print(f"      Defines: {', '.join(ctx.classes[:5])}{'...' if len(ctx.classes) > 5 else ''}")

    # Print context summary
    ctx_summary = ctx_agent.get_summary(ctx_results)
    print(f"\nContext Summary:")
    print(f"  Files:     {ctx_summary['total_files']}")
    print(f"  Classes:   {ctx_summary['total_classes']}")
    print(f"  Functions: {ctx_summary['total_functions']}")
    print(f"  Imports:   {ctx_summary['total_imports']}")
    print(f"  Trails:    {ctx_summary['total_trails_deposited']}")

    print(f"\n{'='*60}")
    print("Phase 3: Dependency Graph")
    print(f"{'='*60}")

    # Build and display dependency graph
    graph = await ctx_agent.build_dependency_graph(src_path, recursive=True)
    print(ctx_agent.format_graph(graph))

    return stats


def main():
    parser = argparse.ArgumentParser(description="Seed trails using OTTO OS agents")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without depositing trails")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    base_path = Path(__file__).parent.parent

    if args.dry_run:
        print("=== DRY RUN MODE (no trails will be deposited) ===")
        store = None
    else:
        store = get_store()
        # Decay old trails first
        pruned = store.decay_all()
        print(f"Decayed trails: {pruned} pruned, {store.count_trails()} remaining")

    print(f"\nSeeding trails for: {base_path}")

    # Run async seeding
    stats = asyncio.run(seed_with_agents(
        base_path,
        store,
        dry_run=args.dry_run,
        verbose=args.verbose,
    ))

    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"Files analyzed:     {stats['files_analyzed']}")
    print(f"Validation trails:  {stats['validation_trails']}")
    print(f"Context trails:     {stats['context_trails']}")
    print(f"Total trails:       {stats['validation_trails'] + stats['context_trails']}")
    print(f"Compliant files:    {stats['compliant_files']}")
    print(f"Non-compliant:      {stats['non_compliant_files']}")

    if not args.dry_run and store:
        total = store.count_trails()
        print(f"\nTotal trails in database: {total}")


if __name__ == "__main__":
    main()
