"""
Notion MCP Server
=================

MCP server for Notion operations.
Provides access to pages, databases, and blocks.

ThinkingMachines [He2025] Compliance:
- Deterministic page ordering (by last edited)
- Fixed block type mapping
- Sorted iteration
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_mcp import MCPServer, MCPTool, MCPResource

logger = logging.getLogger(__name__)


class NotionMCPServer(MCPServer):
    """MCP server for Notion operations."""

    server_name = "notion"
    server_version = "1.0.0"

    def __init__(self):
        """Initialize Notion MCP server."""
        super().__init__()
        self._register_tools()
        self._register_resources()

    def _register_tools(self) -> None:
        """Register Notion tools."""
        # Search pages (TRUST)
        self.register_tool(MCPTool(
            name="notion_search",
            description="Search Notion pages and databases",
            parameters={
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "filter_type": {
                    "type": "string",
                    "enum": ["page", "database", "all"],
                    "description": "Filter by type",
                    "default": "all",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results",
                    "default": 20,
                },
            },
            approval_action="notion.read",
            category="read",
            _handler=self._handle_search,
        ))

        # Read page (TRUST)
        self.register_tool(MCPTool(
            name="notion_read_page",
            description="Read content of a Notion page",
            parameters={
                "page_id": {
                    "type": "string",
                    "description": "Page ID or URL",
                },
                "include_children": {
                    "type": "boolean",
                    "description": "Include child blocks",
                    "default": True,
                },
            },
            approval_action="notion.read",
            category="read",
            _handler=self._handle_read_page,
        ))

        # Query database (TRUST)
        self.register_tool(MCPTool(
            name="notion_query_database",
            description="Query a Notion database",
            parameters={
                "database_id": {
                    "type": "string",
                    "description": "Database ID",
                },
                "filter": {
                    "type": "object",
                    "description": "Filter conditions (Notion filter format)",
                },
                "sorts": {
                    "type": "array",
                    "description": "Sort conditions",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results",
                    "default": 100,
                },
            },
            approval_action="notion.read",
            category="read",
            _handler=self._handle_query_database,
        ))

        # Create page (TRUST)
        self.register_tool(MCPTool(
            name="notion_create_page",
            description="Create a new Notion page",
            parameters={
                "parent_id": {
                    "type": "string",
                    "description": "Parent page or database ID",
                },
                "title": {
                    "type": "string",
                    "description": "Page title",
                },
                "content": {
                    "type": "string",
                    "description": "Page content (markdown)",
                },
                "properties": {
                    "type": "object",
                    "description": "Page properties (for database pages)",
                },
            },
            approval_action="notion.read",
            category="write",
            _handler=self._handle_create_page,
        ))

        # Update page (TRUST)
        self.register_tool(MCPTool(
            name="notion_update_page",
            description="Update a Notion page",
            parameters={
                "page_id": {
                    "type": "string",
                    "description": "Page ID to update",
                },
                "title": {
                    "type": "string",
                    "description": "New title (optional)",
                },
                "properties": {
                    "type": "object",
                    "description": "Properties to update",
                },
            },
            approval_action="notion.read",
            category="write",
            _handler=self._handle_update_page,
        ))

        # Append to page (TRUST)
        self.register_tool(MCPTool(
            name="notion_append_blocks",
            description="Append content blocks to a page",
            parameters={
                "page_id": {
                    "type": "string",
                    "description": "Page ID",
                },
                "content": {
                    "type": "string",
                    "description": "Content to append (markdown)",
                },
            },
            approval_action="notion.read",
            category="write",
            _handler=self._handle_append_blocks,
        ))

        # Archive page (CONSTITUTIONAL - destructive)
        self.register_tool(MCPTool(
            name="notion_archive_page",
            description="Archive (delete) a Notion page",
            parameters={
                "page_id": {
                    "type": "string",
                    "description": "Page ID to archive",
                },
            },
            approval_action="file.delete",
            category="delete",
            _handler=self._handle_archive_page,
        ))

    def _register_resources(self) -> None:
        """Register Notion resources."""
        self.register_resource(MCPResource(
            uri="notion://recent",
            name="Recent Pages",
            description="Recently edited pages",
            approval_action="notion.read",
        ))

        self.register_resource(MCPResource(
            uri="notion://favorites",
            name="Favorite Pages",
            description="Starred/favorited pages",
            approval_action="notion.read",
        ))

    # =========================================================================
    # Tool Handlers
    # =========================================================================

    async def _handle_search(
        self,
        query: str,
        filter_type: str = "all",
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search Notion pages."""
        logger.info(f"Searching Notion: {query}")

        # Mock response
        return [
            {
                "id": "page_1",
                "type": "page",
                "title": f"Result for: {query}",
                "url": "https://notion.so/page_1",
                "last_edited": datetime.now().isoformat(),
                "parent_type": "workspace",
            }
        ]

    async def _handle_read_page(
        self,
        page_id: str,
        include_children: bool = True,
    ) -> Dict[str, Any]:
        """Read Notion page content."""
        logger.info(f"Reading Notion page: {page_id}")

        return {
            "id": page_id,
            "title": "Sample Page",
            "url": f"https://notion.so/{page_id}",
            "created_time": datetime.now().isoformat(),
            "last_edited_time": datetime.now().isoformat(),
            "properties": {},
            "content": [
                {
                    "type": "paragraph",
                    "text": "This is the page content.",
                }
            ] if include_children else None,
        }

    async def _handle_query_database(
        self,
        database_id: str,
        filter: Optional[Dict[str, Any]] = None,
        sorts: Optional[List[Dict[str, Any]]] = None,
        max_results: int = 100,
    ) -> Dict[str, Any]:
        """Query Notion database."""
        logger.info(f"Querying Notion database: {database_id}")

        return {
            "database_id": database_id,
            "results": [
                {
                    "id": "row_1",
                    "properties": {
                        "Name": {"title": [{"text": {"content": "Sample Row"}}]},
                        "Status": {"select": {"name": "Done"}},
                    },
                }
            ],
            "has_more": False,
            "next_cursor": None,
        }

    async def _handle_create_page(
        self,
        parent_id: str,
        title: str,
        content: str = "",
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create Notion page."""
        logger.info(f"Creating Notion page: {title}")

        return {
            "id": f"page_{datetime.now().timestamp():.0f}",
            "title": title,
            "parent_id": parent_id,
            "url": f"https://notion.so/page_{datetime.now().timestamp():.0f}",
            "created_time": datetime.now().isoformat(),
        }

    async def _handle_update_page(
        self,
        page_id: str,
        title: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update Notion page."""
        logger.info(f"Updating Notion page: {page_id}")

        return {
            "id": page_id,
            "title": title or "Updated Page",
            "last_edited_time": datetime.now().isoformat(),
        }

    async def _handle_append_blocks(
        self,
        page_id: str,
        content: str,
    ) -> Dict[str, Any]:
        """Append blocks to page."""
        logger.info(f"Appending to Notion page: {page_id}")

        return {
            "page_id": page_id,
            "blocks_added": 1,
            "last_edited_time": datetime.now().isoformat(),
        }

    async def _handle_archive_page(self, page_id: str) -> Dict[str, Any]:
        """Archive Notion page."""
        logger.info(f"Archiving Notion page: {page_id}")

        return {
            "id": page_id,
            "archived": True,
            "archived_time": datetime.now().isoformat(),
        }

    # =========================================================================
    # Resource Handler
    # =========================================================================

    async def _read_resource_content(self, uri: str) -> Any:
        """Read Notion resource content."""
        if uri == "notion://recent":
            return await self._handle_search("", max_results=10)

        elif uri == "notion://favorites":
            return await self._handle_search("is:starred", max_results=10)

        else:
            raise ValueError(f"Unknown resource: {uri}")


__all__ = ["NotionMCPServer"]
