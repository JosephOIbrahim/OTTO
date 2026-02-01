"""
Otto Trails MCP - Pheromone Trail System via Model Context Protocol.

Enables trail operations from any MCP-compatible client:
- Read trails for files
- Deposit new trails
- Query trail patterns
- Follow context relationships
"""

from .server import create_server, main

__version__ = "0.1.0"

__all__ = ["create_server", "main"]
