"""Build Agent — Phase completion assistant for OTTO.

This agent helps finish OTTO's remaining build phases (2-9) as defined
in the CLAUDE.md spec. It can:

- Read the spec to understand what's needed for each phase
- Read existing code to understand current state
- Write new files and edit existing ones
- Run tests to verify changes
- Track progress against the phase roadmap

The agent works incrementally: one phase at a time, one file at a time,
running tests after each change. It respects the "wrap, don't rewrite"
principle -- existing v4.0 files stay, new code extends.

Uses ClaudeSDKClient with full file access (Read/Write/Edit/Bash/Glob/Grep).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)


BUILDER_SYSTEM_PROMPT = """\
You are OTTO's Build Agent. Your job is to implement OTTO's remaining
build phases incrementally, following the spec in CLAUDE.md.

## Context

OTTO v4.0 is a working commitment tracker with 238 tests.
Phases 0.1 through 1.3 are complete:
- Structured logging (Phase 0.1)
- Cognitive state tracking (Phase 0.2)
- Constitutional layer (Phase 0.3)
- Constitutional wired to nudge (Phase 1.1)
- Snooze and WIP commands (Phase 1.2)
- Scheduler (Phase 1.3)
- Agent SDK integration (done)

Remaining phases:
- Phase 2: PRISM Signal Detection (signals.py, HistoryAnalyzer)
- Phase 3: Mode Architecture (modes/base.py, executor.py, protector.py, restorer.py)
- Phase 4: NEXUS Routing (router.py, end-to-end wiring)
- Phase 5: Pheromone Trails (trails.py, Kahan summation)
- Phase 6: Transport Abstraction (transport/base.py, whatsapp.py, cli_transport.py)
- Phase 7: Agent SDK Integration v2 (modes as MCP tools, constitutional hooks)
- Phase 8: Remaining Modes (decomposer, redirector, acknowledger, guide)
- Phase 9: Hardening (dedup, indices, stable IDs)

## How to Work

1. START by reading CLAUDE.md to understand the current phase requirements
2. READ existing code to understand what's there
3. PLAN the changes needed (tell the user what you intend to do)
4. IMPLEMENT one file at a time
5. RUN TESTS after each file: `python -m pytest tests/ -v -m "not integration"`
6. If tests fail, fix before moving on
7. When a phase is complete, summarize what was done

## Principles

- **Wrap, don't rewrite**: existing v4.0 files stay. New code wraps and extends.
- **He2025 determinism**: sort_keys=True, sorted() on dicts, hashlib not hash().
- **Constitutional language**: never "just" or "simply". Use "achievable" or "small".
- **Tests first**: write test file before implementation when possible.
- **Incremental**: don't try to implement an entire phase at once.
  Break it into sub-tasks and verify each one.

## Test Command

```bash
python -m pytest tests/ -v -m "not integration"
```

Run this after EVERY change to verify nothing breaks. All 178+ non-integration
tests must continue to pass.

## File Locations

- Spec: CLAUDE.md (in project root, one level up from otto_v4/)
- Source: otto_v4/src/otto/
- Tests: otto_v4/tests/
- Agent: otto_v4/otto_agent/

## Important

- Ask the user which phase to work on if not specified
- Show your plan before writing code
- Keep changes small and testable
- If you're unsure about a design decision, ask the user
- Never delete or significantly modify existing v4.0 files
"""


# Subagents for specific build tasks
BUILD_SUBAGENTS: dict[str, AgentDefinition] = {
    "test-runner": AgentDefinition(
        description=(
            "Runs OTTO's test suite and reports results. Use after making "
            "code changes to verify nothing is broken."
        ),
        prompt="""\
Run the OTTO test suite and report results.

Command: python -m pytest tests/ -v -m "not integration"

Report:
1. Total tests passed/failed/skipped
2. Any failures with file and test name
3. Whether the change is safe to proceed with
""",
        tools=["Bash"],
        model="haiku",
    ),
    "spec-reader": AgentDefinition(
        description=(
            "Reads the OTTO CLAUDE.md spec and extracts requirements for "
            "a specific phase. Use to understand what needs to be built."
        ),
        prompt="""\
Read the OTTO CLAUDE.md spec file and extract the detailed requirements
for the requested phase. Report:
1. Files to create/modify
2. Tests to write
3. Quality gate criteria
4. Dependencies on previous phases
""",
        tools=["Read", "Glob"],
        model="haiku",
    ),
}


async def run_builder(
    prompt: str | None = None,
    *,
    phase: str | None = None,
    interactive: bool = False,
    max_turns: int | None = None,
) -> None:
    """Run the Build Agent.

    Parameters
    ----------
    prompt:
        Specific instruction. Overrides phase if provided.
    phase:
        Phase to work on (e.g. "2.1", "3", "5.1").
    interactive:
        If True, runs a conversation loop.
    max_turns:
        Maximum turns per query.
    """
    cwd = str(Path(__file__).resolve().parent.parent.parent / "otto_v4")

    options = ClaudeAgentOptions(
        system_prompt=BUILDER_SYSTEM_PROMPT,
        allowed_tools=[
            "Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task",
        ],
        agents=BUILD_SUBAGENTS,
        permission_mode="acceptEdits",
        max_turns=max_turns or 50,
        cwd=cwd,
        setting_sources=["project"],
    )

    if prompt is None:
        if phase:
            prompt = (
                f"Work on Phase {phase} of OTTO's build roadmap. "
                f"Start by reading CLAUDE.md to understand the requirements, "
                f"then read the existing code, plan your changes, and implement "
                f"incrementally with tests after each change."
            )
        else:
            prompt = (
                "Read CLAUDE.md and the current codebase to determine which "
                "phase to work on next. Show me the current state and what "
                "needs to be built."
            )

    if not interactive:
        print(f"OTTO Build Agent")
        print(f"Working directory: {cwd}")
        if phase:
            print(f"Target phase: {phase}")
        print("-" * 60)

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(block.text, end="")
                elif isinstance(message, ResultMessage):
                    if message.is_error:
                        print(f"\n[Error: {message.result}]")
                    else:
                        cost = message.total_cost_usd
                        if cost is not None:
                            print(f"\n\n[Build cost: ${cost:.4f}]")
            print()
        return

    # Interactive mode
    print("OTTO Build Agent -- Phase Completion Assistant")
    print(f"Working directory: {cwd}")
    print("Type 'exit' to quit, 'test' to run tests, 'status' for phase status.\n")

    async with ClaudeSDKClient(options=options) as client:
        # Initial prompt
        await client.query(prompt)
        print("Builder: ", end="")
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text, end="")
        print("\n")

        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBuild session ended.")
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("Build session ended.")
                break
            if user_input.lower() == "test":
                user_input = "Run the test suite and report results."
            if user_input.lower() == "status":
                user_input = (
                    "Read CLAUDE.md and check which phases are complete vs "
                    "remaining. Show a summary."
                )

            await client.query(user_input)
            print("Builder: ", end="")
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(block.text, end="")
                elif isinstance(message, ResultMessage):
                    if message.is_error:
                        print(f"\n[Error: {message.result}]")
            print("\n")
