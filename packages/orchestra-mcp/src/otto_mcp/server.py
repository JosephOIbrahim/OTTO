"""
Orchestra MCP Server - Cognitive Safety Layer via Model Context Protocol.

This server exposes Orchestra's cognitive state management to any MCP-compatible
client, enabling cross-tool safety gating and cognitive state awareness.

Usage:
    # Run directly
    python -m orchestra_mcp.server

    # Or via entry point
    orchestra-mcp

    # Configure in Claude Desktop
    {
        "mcpServers": {
            "orchestra": {
                "command": "orchestra-mcp"
            }
        }
    }

Tools Provided:
    orchestra_status     - Get current cognitive state
    orchestra_check      - Check if operation is safe given current state
    orchestra_calibrate  - Set focus/urgency calibration
    orchestra_expert     - Get recommended expert for a message

References:
    MCP Specification: https://modelcontextprotocol.io/
    Orchestra: https://github.com/JosephOIbrahim/Orchestra
"""

import asyncio
import json
import logging
from typing import Any

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    Server = None

from otto.cognitive_state import (
    CognitiveStateManager,
    BurnoutLevel,
    EnergyLevel,
)
from otto.expert_router import create_router
from otto.prism_detector import create_detector

logger = logging.getLogger(__name__)


def create_server() -> "Server":
    """Create and configure the MCP server."""
    if not MCP_AVAILABLE:
        raise ImportError(
            "MCP package not installed. Install with: pip install mcp"
        )

    server = Server("orchestra-mcp")
    state_manager = CognitiveStateManager()
    router = create_router()
    detector = create_detector()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available Orchestra tools."""
        return [
            Tool(
                name="orchestra_status",
                description=(
                    "Get current cognitive state including burnout level, "
                    "energy, momentum, and recommended thinking depth. "
                    "Use this to understand the user's current capacity."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            Tool(
                name="orchestra_check",
                description=(
                    "Check if an operation is safe given current cognitive state. "
                    "Returns whether to proceed and recommended adjustments. "
                    "Use before starting complex operations."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "description": "Description of the operation to check"
                        },
                        "thinking_depth": {
                            "type": "string",
                            "enum": ["minimal", "standard", "deep", "ultradeep"],
                            "description": "Requested thinking depth"
                        }
                    },
                    "required": ["operation"]
                }
            ),
            Tool(
                name="orchestra_calibrate",
                description=(
                    "Set focus and urgency calibration for the session. "
                    "This adjusts how Orchestra gates operations."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "focus_level": {
                            "type": "string",
                            "enum": ["scattered", "moderate", "locked_in"],
                            "description": "Current focus level"
                        },
                        "urgency": {
                            "type": "string",
                            "enum": ["relaxed", "moderate", "deadline"],
                            "description": "Current urgency level"
                        }
                    },
                    "required": []
                }
            ),
            Tool(
                name="orchestra_expert",
                description=(
                    "Get the recommended intervention expert for a message. "
                    "Returns the expert type and reasoning based on PRISM signal detection."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "The message to analyze for expert routing"
                        }
                    },
                    "required": ["message"]
                }
            ),
            Tool(
                name="orchestra_set_burnout",
                description=(
                    "Manually set burnout level. Use when user explicitly indicates their state."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "level": {
                            "type": "string",
                            "enum": ["green", "yellow", "orange", "red"],
                            "description": "Burnout level to set"
                        }
                    },
                    "required": ["level"]
                }
            ),
            Tool(
                name="orchestra_set_energy",
                description=(
                    "Manually set energy level. Use when user explicitly indicates their state."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "level": {
                            "type": "string",
                            "enum": ["high", "medium", "low", "depleted"],
                            "description": "Energy level to set"
                        }
                    },
                    "required": ["level"]
                }
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""
        try:
            if name == "orchestra_status":
                return await handle_status(state_manager)
            elif name == "orchestra_check":
                return await handle_check(state_manager, arguments)
            elif name == "orchestra_calibrate":
                return await handle_calibrate(state_manager, arguments)
            elif name == "orchestra_expert":
                return await handle_expert(state_manager, router, detector, arguments)
            elif name == "orchestra_set_burnout":
                return await handle_set_burnout(state_manager, arguments)
            elif name == "orchestra_set_energy":
                return await handle_set_energy(state_manager, arguments)
            else:
                return [TextContent(
                    type="text",
                    text=f"Unknown tool: {name}"
                )]
        except Exception as e:
            logger.exception(f"Error in tool {name}")
            return [TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )]

    return server


async def handle_status(state_manager: CognitiveStateManager) -> list[TextContent]:
    """Handle orchestra_status tool."""
    state = state_manager.get_state()
    max_depth = state.get_max_thinking_depth()
    should_intervene = state.should_intervene()

    status = {
        "burnout_level": state.burnout_level.value,
        "energy_level": state.energy_level.value,
        "momentum_phase": state.momentum_phase.value,
        "mode": state.mode.value,
        "altitude": state.altitude.value,
        "focus_level": state.focus_level,
        "urgency": state.urgency,
        "max_thinking_depth": max_depth,
        "should_intervene": should_intervene,
        "exchange_count": state.exchange_count,
        "tasks_completed": state.tasks_completed,
        "tangent_budget": state.tangent_budget,
        "epistemic_tension": round(state.epistemic_tension, 3),
        "convergence_attractor": state.convergence_attractor,
    }

    # Human-readable summary
    summary_parts = [
        f"Burnout: {state.burnout_level.value.upper()}",
        f"Energy: {state.energy_level.value}",
        f"Max Depth: {max_depth}",
    ]
    if should_intervene:
        summary_parts.append("INTERVENTION RECOMMENDED")

    summary = " | ".join(summary_parts)

    return [TextContent(
        type="text",
        text=f"{summary}\n\n```json\n{json.dumps(status, indent=2)}\n```"
    )]


async def handle_check(
    state_manager: CognitiveStateManager,
    arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle orchestra_check tool."""
    state = state_manager.get_state()
    operation = arguments.get("operation", "unknown")
    requested_depth = arguments.get("thinking_depth", "standard")

    max_depth = state.get_max_thinking_depth()
    depth_order = ["minimal", "standard", "deep", "ultradeep"]

    max_idx = depth_order.index(max_depth) if max_depth in depth_order else 1
    req_idx = depth_order.index(requested_depth) if requested_depth in depth_order else 1

    allowed = req_idx <= max_idx
    recommended_depth = requested_depth if allowed else max_depth

    result = {
        "operation": operation,
        "requested_depth": requested_depth,
        "allowed": allowed,
        "recommended_depth": recommended_depth,
        "reason": None,
    }

    if not allowed:
        if state.energy_level.value == "depleted":
            result["reason"] = "Energy depleted - only minimal depth allowed"
        elif state.burnout_level.value in ["orange", "red"]:
            result["reason"] = f"Burnout at {state.burnout_level.value.upper()} - depth capped at {max_depth}"
        else:
            result["reason"] = f"Current state limits depth to {max_depth}"

    status = "SAFE" if allowed else "ADJUST DEPTH"

    return [TextContent(
        type="text",
        text=f"{status}: {result['reason'] or 'Operation safe to proceed'}\n\n```json\n{json.dumps(result, indent=2)}\n```"
    )]


async def handle_calibrate(
    state_manager: CognitiveStateManager,
    arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle orchestra_calibrate tool."""
    focus = arguments.get("focus_level")
    urgency = arguments.get("urgency")

    state_manager.calibrate(focus_level=focus, urgency=urgency)
    state = state_manager.get_state()

    return [TextContent(
        type="text",
        text=f"Calibrated: focus={state.focus_level}, urgency={state.urgency}"
    )]


async def handle_expert(
    state_manager: CognitiveStateManager,
    router,
    detector,
    arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle orchestra_expert tool."""
    message = arguments.get("message", "")
    state = state_manager.get_state()

    # Detect signals
    signals = detector.detect(message)

    # Check for caps
    caps_detected = message.isupper() and len(message) > 3

    # Route to expert
    result = router.route(
        signals=signals,
        burnout=state.burnout_level,
        energy=state.energy_level,
        momentum=state.momentum_phase,
        mode=state.mode.value,
        tangent_budget=state.tangent_budget,
        caps_detected=caps_detected
    )

    expert_info = {
        "expert": result.expert.value,
        "trigger": result.trigger,
        "priority": result.priority_index,
        "safety_gate_pass": result.safety_gate_pass,
        "constitutional_pass": result.constitutional_pass,
    }

    if result.safety_redirect:
        expert_info["safety_redirect"] = result.safety_redirect

    return [TextContent(
        type="text",
        text=f"Expert: {result.expert.value.upper()} (priority {result.priority_index})\nTrigger: {result.trigger}\n\n```json\n{json.dumps(expert_info, indent=2)}\n```"
    )]


async def handle_set_burnout(
    state_manager: CognitiveStateManager,
    arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle orchestra_set_burnout tool."""
    level = arguments.get("level", "green")
    burnout = BurnoutLevel(level)

    state_manager.batch_update({"burnout_level": burnout})
    state = state_manager.get_state()

    return [TextContent(
        type="text",
        text=f"Burnout set to {state.burnout_level.value.upper()}"
    )]


async def handle_set_energy(
    state_manager: CognitiveStateManager,
    arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle orchestra_set_energy tool."""
    level = arguments.get("level", "medium")
    energy = EnergyLevel(level)

    state_manager.batch_update({"energy_level": energy})
    state = state_manager.get_state()

    return [TextContent(
        type="text",
        text=f"Energy set to {state.energy_level.value}"
    )]


async def run_server():
    """Run the MCP server."""
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Entry point for orchestra-mcp command."""
    if not MCP_AVAILABLE:
        print("Error: MCP package not installed. Install with: pip install mcp")
        return 1

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server())
    return 0


if __name__ == "__main__":
    exit(main())
