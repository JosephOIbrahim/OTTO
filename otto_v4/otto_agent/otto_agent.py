"""otto_agent.py -- OTTO Cognitive Commitment Agent

Entry point for the autonomous agent. Wraps OTTO's commitment loop
(detect -> store -> nudge) with Claude as orchestrator, gated by
the constitutional layer via pre-tool-use hooks.

Uses the anthropic SDK with standard tool-use message loop.

USAGE:
    cd C:/Users/User/OTTO_OS/otto_v4
    python -m otto_agent.otto_agent "What commitments do I have?"
    python -m otto_agent.otto_agent "Add a commitment to send the report to Sarah by Friday"
"""

import json
import logging
import os
import sys
from pathlib import Path

from anthropic import Anthropic

# Ensure otto source is importable at module load (for model_config import below).
_otto_src = str(Path(__file__).resolve().parent.parent / "src")
if _otto_src not in sys.path:
    sys.path.insert(0, _otto_src)

from otto.model_config import AGENT_MODEL, TEMPERATURE

# Setup logging
_log_dir = Path(__file__).parent / "logs"
_log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            _log_dir / "agent.log", mode="a", encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger("otto.agent")

# Model configuration (model + temperature imported from otto.model_config)
MAX_TOKENS = 4096
MAX_AGENT_TURNS = 15


def _load_system_prompt() -> str:
    """Build the system prompt from CLAUDE.md."""
    agent_dir = Path(__file__).parent
    claude_md = agent_dir / "CLAUDE.md"

    personality = ""
    if claude_md.exists():
        personality = claude_md.read_text(encoding="utf-8")

    return personality


def _init_default_stores():
    """Create default store instances pointing at ~/.otto/commitments.db."""
    from otto.state import StateStore
    from otto.store import CommitmentStore
    from otto_agent.otto_tools import init_stores

    db_path = str(Path(os.path.expanduser("~/.otto/commitments.db")))
    store = CommitmentStore(db_path=db_path)
    state_store = StateStore(db_path=db_path)
    init_stores(store=store, state_store=state_store)

    return store, state_store


def run_agent(goal: str) -> list[dict]:
    """
    Run the agentic tool-use loop with constitutional gating.

    Returns the full message history for testing/inspection.
    """
    from otto_agent.otto_hooks import constitutional_gate, format_suppression_result
    from otto_agent.otto_tools import (
        TOOL_DEFINITIONS,
        execute_tool,
        get_state_store,
    )

    # Initialize stores
    _init_default_stores()

    # Create Anthropic client
    client = Anthropic()
    system_prompt = _load_system_prompt()

    messages = [{"role": "user", "content": goal}]

    logger.info("Starting agent with goal: %s", goal)
    print(f"\n{'='*60}")
    print(f"  OTTO AGENT")
    print(f"{'='*60}\n")

    # Agentic loop
    for turn in range(MAX_AGENT_TURNS):
        logger.info("Agent turn %d/%d", turn + 1, MAX_AGENT_TURNS)

        response = client.messages.create(
            model=AGENT_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Process response content blocks
        assistant_content = []
        tool_uses = []

        for block in response.content:
            if block.type == "text":
                print(block.text)
                assistant_content.append(
                    {"type": "text", "text": block.text}
                )
            elif block.type == "tool_use":
                tool_uses.append(block)
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        messages.append({"role": "assistant", "content": assistant_content})

        # No tool calls = agent is done
        if not tool_uses:
            logger.info("Agent completed (no more tool calls)")
            break

        # Execute tool calls with constitutional gating
        tool_results = []
        for tool_use in tool_uses:
            tool_name = tool_use.name
            tool_input = tool_use.input

            logger.info(
                "Tool call: %s(%s)",
                tool_name,
                json.dumps(tool_input)[:200],
            )

            # Constitutional gate: check before executing
            state = get_state_store().load()
            suppression = constitutional_gate(tool_name, tool_input, state)

            if suppression is not None:
                result_str = format_suppression_result(suppression)
                logger.info("Tool suppressed by constitutional layer")
            else:
                result_str = execute_tool(tool_name, tool_input)

            logger.info("Tool result: %s", result_str[:300])

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result_str,
            })

        messages.append({"role": "user", "content": tool_results})

    else:
        logger.warning("Agent hit max turns (%d)", MAX_AGENT_TURNS)
        print(
            f"\n[Agent reached {MAX_AGENT_TURNS} turns -- stopping]"
        )

    print(f"\n{'='*60}")
    print("  OTTO AGENT -- Complete")
    print(f"{'='*60}\n")

    return messages


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print('Usage: python -m otto_agent.otto_agent "<goal>"')
        print(
            'Example: python -m otto_agent.otto_agent '
            '"What commitments do I have?"'
        )
        sys.exit(1)

    goal = " ".join(sys.argv[1:])
    run_agent(goal)


if __name__ == "__main__":
    main()
