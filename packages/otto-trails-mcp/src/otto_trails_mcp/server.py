"""
Otto Trails MCP Server - Pheromone Trail System via Model Context Protocol.

This server exposes the Pheromone Trail system to any MCP-compatible client,
enabling distributed learning through trail deposits and queries.

Usage:
    # Run directly
    python -m otto_trails_mcp.server

    # Or via entry point
    otto-trails-mcp

    # Configure in Claude Desktop
    {
        "mcpServers": {
            "otto-trails": {
                "command": "otto-trails-mcp"
            }
        }
    }

Tools Provided:
    otto_read_trails      - Read all trails for a file path
    otto_deposit_trail    - Create or reinforce a trail
    otto_reinforce_trail  - Strengthen an existing trail
    otto_query_trails     - Flexible trail search
    otto_get_related      - Follow CONTEXT trails to find related files
    otto_decay_trails     - Run decay and prune dead trails

Determinism:
- All queries return results in deterministic order
- Trail operations are atomic via SQLite transactions
- Same inputs -> same outputs

References:
    MCP Specification: https://modelcontextprotocol.io/
    OTTO OS: https://github.com/JosephOIbrahim/otto-os
"""

import asyncio
import json
import logging
from typing import Any, Optional

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    Server = None

from otto.trails import (
    Trail,
    TrailType,
    TrailQuery,
    TrailStore,
    get_store,
)

logger = logging.getLogger(__name__)


def create_server() -> "Server":
    """Create and configure the MCP server."""
    if not MCP_AVAILABLE:
        raise ImportError(
            "MCP package not installed. Install with: pip install mcp"
        )

    server = Server("otto-trails-mcp")
    store = get_store()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available Trail tools."""
        return [
            Tool(
                name="otto_read_trails",
                description=(
                    "Read all living trails for a file path. "
                    "Returns trails sorted by (trail_type, signal) for determinism."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path to read trails for"
                        }
                    },
                    "required": ["path"]
                }
            ),
            Tool(
                name="otto_deposit_trail",
                description=(
                    "Create or reinforce a trail. If a matching trail exists "
                    "(same type, path, signal), it is reinforced instead of duplicated."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path to attach trail to"
                        },
                        "signal": {
                            "type": "string",
                            "description": "Trail signal (e.g., 'he2025_compliant', 'depends_on:utils.py')"
                        },
                        "trail_type": {
                            "type": "string",
                            "enum": ["quality", "context", "decision", "pattern", "work"],
                            "description": "Type of trail"
                        },
                        "strength": {
                            "type": "number",
                            "description": "Initial strength 0.0-1.0 (default 1.0)",
                            "default": 1.0
                        },
                        "deposited_by": {
                            "type": "string",
                            "description": "Agent/session ID depositing the trail",
                            "default": "mcp_client"
                        }
                    },
                    "required": ["path", "signal", "trail_type"]
                }
            ),
            Tool(
                name="otto_reinforce_trail",
                description=(
                    "Strengthen an existing trail by a boost amount. "
                    "Use for positive reinforcement of good patterns."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path of the trail"
                        },
                        "signal": {
                            "type": "string",
                            "description": "Trail signal to reinforce"
                        },
                        "trail_type": {
                            "type": "string",
                            "enum": ["quality", "context", "decision", "pattern", "work"],
                            "description": "Type of trail"
                        },
                        "boost": {
                            "type": "number",
                            "description": "Amount to add to strength (default 0.2)",
                            "default": 0.2
                        }
                    },
                    "required": ["path", "signal", "trail_type"]
                }
            ),
            Tool(
                name="otto_query_trails",
                description=(
                    "Flexible search for trails matching criteria. "
                    "All parameters are optional filters."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trail_type": {
                            "type": "string",
                            "enum": ["quality", "context", "decision", "pattern", "work"],
                            "description": "Filter by trail type"
                        },
                        "path": {
                            "type": "string",
                            "description": "Exact path match"
                        },
                        "path_prefix": {
                            "type": "string",
                            "description": "Path starts with this prefix"
                        },
                        "signal_contains": {
                            "type": "string",
                            "description": "Signal contains this substring"
                        },
                        "min_strength": {
                            "type": "number",
                            "description": "Minimum current strength after decay"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results to return (default 100)",
                            "default": 100
                        }
                    },
                    "required": []
                }
            ),
            Tool(
                name="otto_get_related",
                description=(
                    "Follow CONTEXT trails to find related files. "
                    "Returns files connected via depends_on, used_by, or related_to trails."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Starting file path"
                        }
                    },
                    "required": ["path"]
                }
            ),
            Tool(
                name="otto_decay_trails",
                description=(
                    "Apply decay to all trails and prune dead ones. "
                    "Should be run periodically (e.g., on session start)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""
        try:
            if name == "otto_read_trails":
                return await handle_read_trails(store, arguments)
            elif name == "otto_deposit_trail":
                return await handle_deposit_trail(store, arguments)
            elif name == "otto_reinforce_trail":
                return await handle_reinforce_trail(store, arguments)
            elif name == "otto_query_trails":
                return await handle_query_trails(store, arguments)
            elif name == "otto_get_related":
                return await handle_get_related(store, arguments)
            elif name == "otto_decay_trails":
                return await handle_decay_trails(store, arguments)
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


async def handle_read_trails(
    store: TrailStore,
    arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle otto_read_trails tool."""
    path = arguments.get("path", "")

    if not path:
        return [TextContent(
            type="text",
            text="Error: path is required"
        )]

    trails = store.read_trails(path)

    if not trails:
        return [TextContent(
            type="text",
            text=f"No trails found for: {path}"
        )]

    result = {
        "path": path,
        "count": len(trails),
        "trails": [t.to_dict() for t in trails],
    }

    summary_lines = [f"Found {len(trails)} trails for {path}:"]
    for trail in trails:
        summary_lines.append(
            f"  [{trail.trail_type.value}] {trail.signal} "
            f"(strength: {trail.current_strength():.2f})"
        )

    return [TextContent(
        type="text",
        text="\n".join(summary_lines) + f"\n\n```json\n{json.dumps(result, indent=2, default=str)}\n```"
    )]


async def handle_deposit_trail(
    store: TrailStore,
    arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle otto_deposit_trail tool."""
    path = arguments.get("path", "")
    signal = arguments.get("signal", "")
    trail_type_str = arguments.get("trail_type", "quality")
    strength = arguments.get("strength", 1.0)
    deposited_by = arguments.get("deposited_by", "mcp_client")

    if not path or not signal:
        return [TextContent(
            type="text",
            text="Error: path and signal are required"
        )]

    trail = Trail(
        path=path,
        signal=signal,
        trail_type=TrailType(trail_type_str),
        strength=strength,
        deposited_by=deposited_by,
    )

    result = store.deposit(trail)

    action = "reinforced" if result.reinforced_count > 0 else "created"

    return [TextContent(
        type="text",
        text=f"Trail {action}: [{trail_type_str}] {signal} on {path}\nStrength: {result.strength:.2f}, Reinforced: {result.reinforced_count} times"
    )]


async def handle_reinforce_trail(
    store: TrailStore,
    arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle otto_reinforce_trail tool."""
    path = arguments.get("path", "")
    signal = arguments.get("signal", "")
    trail_type_str = arguments.get("trail_type", "quality")
    boost = arguments.get("boost", 0.2)

    if not path or not signal:
        return [TextContent(
            type="text",
            text="Error: path and signal are required"
        )]

    result = store.reinforce(
        path=path,
        signal=signal,
        trail_type=TrailType(trail_type_str),
        boost=boost,
        by="mcp_client",
    )

    if result is None:
        return [TextContent(
            type="text",
            text=f"Trail not found: [{trail_type_str}] {signal} on {path}"
        )]

    return [TextContent(
        type="text",
        text=f"Trail reinforced: [{trail_type_str}] {signal}\nNew strength: {result.strength:.2f}"
    )]


async def handle_query_trails(
    store: TrailStore,
    arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle otto_query_trails tool."""
    query = TrailQuery(
        trail_type=TrailType(arguments["trail_type"]) if "trail_type" in arguments else None,
        path=arguments.get("path"),
        path_prefix=arguments.get("path_prefix"),
        signal_contains=arguments.get("signal_contains"),
        min_strength=arguments.get("min_strength"),
        limit=arguments.get("limit", 100),
    )

    trails = store.query(query)

    if not trails:
        return [TextContent(
            type="text",
            text="No trails match the query"
        )]

    result = {
        "count": len(trails),
        "trails": [t.to_dict() for t in trails],
    }

    summary = f"Found {len(trails)} matching trails"

    return [TextContent(
        type="text",
        text=f"{summary}\n\n```json\n{json.dumps(result, indent=2, default=str)}\n```"
    )]


async def handle_get_related(
    store: TrailStore,
    arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle otto_get_related tool."""
    path = arguments.get("path", "")

    if not path:
        return [TextContent(
            type="text",
            text="Error: path is required"
        )]

    related = store.get_related_paths(path)

    if not related:
        return [TextContent(
            type="text",
            text=f"No related files found for: {path}"
        )]

    result = {
        "source": path,
        "related_count": len(related),
        "related_files": related,
    }

    lines = [f"Related files for {path}:"]
    for rel_path in related:
        lines.append(f"  - {rel_path}")

    return [TextContent(
        type="text",
        text="\n".join(lines) + f"\n\n```json\n{json.dumps(result, indent=2)}\n```"
    )]


async def handle_decay_trails(
    store: TrailStore,
    arguments: dict[str, Any]
) -> list[TextContent]:
    """Handle otto_decay_trails tool."""
    pruned = store.decay_all()
    remaining = store.count_trails()

    return [TextContent(
        type="text",
        text=f"Decay complete: {pruned} trails pruned, {remaining} remaining"
    )]


async def run_server():
    """Run the MCP server."""
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Entry point for otto-trails-mcp command."""
    if not MCP_AVAILABLE:
        print("Error: MCP package not installed. Install with: pip install mcp")
        return 1

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server())
    return 0


if __name__ == "__main__":
    exit(main())
