"""
Orchestra MCP Server - Model Context Protocol integration for cognitive safety layer.

Exposes Orchestra's cognitive state and safety gating to MCP-compatible clients
(Claude Desktop, Cursor, etc.)

Tools:
    orchestra_status: Get current cognitive state
    orchestra_check_safety: Check if operation is safe
    orchestra_calibrate: Set focus/urgency levels
    orchestra_get_expert: Get recommended expert for signals
"""

__version__ = "1.0.0"
