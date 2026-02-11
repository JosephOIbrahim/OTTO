"""OTTO Agents CLI — Entry point for all three agents.

Usage:
    otto-agents nexus [PROMPT]              Run NEXUS orchestrator
    otto-agents nexus --interactive         Interactive NEXUS conversation
    otto-agents consistency [--target DIR]  Run He2025 determinism audit
    otto-agents build [--phase PHASE]       Run Build Agent
    otto-agents build --interactive         Interactive build session
"""

from __future__ import annotations

import argparse
import asyncio
import sys


def cli() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="otto-agents",
        description="OTTO cognitive agents — NEXUS, consistency, builder",
    )
    subparsers = parser.add_subparsers(dest="agent", help="Agent to run")

    # NEXUS subcommand
    nexus_parser = subparsers.add_parser(
        "nexus", help="NEXUS orchestrator — cognitive commitment agent"
    )
    nexus_parser.add_argument(
        "prompt", nargs="?", default=None,
        help="Prompt for the agent (default: check commitments and energy)",
    )
    nexus_parser.add_argument(
        "-i", "--interactive", action="store_true",
        help="Run in interactive conversation mode",
    )
    nexus_parser.add_argument(
        "--max-turns", type=int, default=None,
        help="Maximum turns per query",
    )

    # Consistency subcommand
    consistency_parser = subparsers.add_parser(
        "consistency", help="He2025 determinism audit"
    )
    consistency_parser.add_argument(
        "--target", default=None,
        help="Directory to audit (default: otto_v4/)",
    )
    consistency_parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Show all messages including tool calls",
    )

    # Build subcommand
    build_parser = subparsers.add_parser(
        "build", help="Build Agent — phase completion assistant"
    )
    build_parser.add_argument(
        "prompt", nargs="?", default=None,
        help="Specific instruction for the builder",
    )
    build_parser.add_argument(
        "--phase", default=None,
        help="Phase to work on (e.g. 2.1, 3, 5.1)",
    )
    build_parser.add_argument(
        "-i", "--interactive", action="store_true",
        help="Run in interactive build session",
    )
    build_parser.add_argument(
        "--max-turns", type=int, default=None,
        help="Maximum turns per query",
    )

    args = parser.parse_args()

    if args.agent is None:
        parser.print_help()
        sys.exit(1)

    if args.agent == "nexus":
        from .nexus import run_nexus
        asyncio.run(run_nexus(
            prompt=args.prompt,
            interactive=args.interactive,
            max_turns=args.max_turns,
        ))

    elif args.agent == "consistency":
        from .consistency import run_consistency
        asyncio.run(run_consistency(
            target_dir=args.target,
            verbose=args.verbose,
        ))

    elif args.agent == "build":
        from .builder import run_builder
        asyncio.run(run_builder(
            prompt=args.prompt,
            phase=args.phase,
            interactive=args.interactive,
            max_turns=args.max_turns,
        ))


if __name__ == "__main__":
    cli()
