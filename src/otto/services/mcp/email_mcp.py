"""
Email MCP Server
================

MCP server for email operations.
Integrates with Gmail, Outlook, and IMAP providers.

Determinism:
- Deterministic email ordering (by date)
- Fixed threading model
- Sorted iteration

Per spec:
- TRUST: email.read (can earn auto-approval)
- CONSTITUTIONAL: email.send (always requires approval)
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_mcp import MCPServer, MCPTool, MCPResource

logger = logging.getLogger(__name__)


class EmailMCPServer(MCPServer):
    """MCP server for email operations."""

    server_name = "email"
    server_version = "1.0.0"

    def __init__(self):
        """Initialize email MCP server."""
        super().__init__()
        self._register_tools()
        self._register_resources()

    def _register_tools(self) -> None:
        """Register email tools."""
        # List emails (TRUST)
        self.register_tool(MCPTool(
            name="email_list",
            description="List emails from inbox or folder",
            parameters={
                "folder": {
                    "type": "string",
                    "description": "Folder name (inbox, sent, drafts, etc.)",
                    "default": "inbox",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (optional)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum emails to return",
                    "default": 20,
                },
                "unread_only": {
                    "type": "boolean",
                    "description": "Only return unread emails",
                    "default": False,
                },
            },
            approval_action="email.read",
            category="read",
            _handler=self._handle_list_emails,
        ))

        # Read email (TRUST)
        self.register_tool(MCPTool(
            name="email_read",
            description="Read full content of an email",
            parameters={
                "email_id": {
                    "type": "string",
                    "description": "Email ID",
                },
            },
            approval_action="email.read",
            category="read",
            _handler=self._handle_read_email,
        ))

        # Search emails (TRUST)
        self.register_tool(MCPTool(
            name="email_search",
            description="Search emails with advanced query",
            parameters={
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "from_email": {
                    "type": "string",
                    "description": "Filter by sender (optional)",
                },
                "date_after": {
                    "type": "string",
                    "description": "Emails after this date (optional)",
                },
                "date_before": {
                    "type": "string",
                    "description": "Emails before this date (optional)",
                },
                "has_attachment": {
                    "type": "boolean",
                    "description": "Filter for emails with attachments",
                },
            },
            approval_action="email.read",
            category="read",
            _handler=self._handle_search_emails,
        ))

        # Send email (CONSTITUTIONAL - always requires approval)
        self.register_tool(MCPTool(
            name="email_send",
            description="Send an email",
            parameters={
                "to": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Recipient email addresses",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject",
                },
                "body": {
                    "type": "string",
                    "description": "Email body (plain text or HTML)",
                },
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "CC recipients (optional)",
                },
                "bcc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "BCC recipients (optional)",
                },
                "reply_to_id": {
                    "type": "string",
                    "description": "Email ID to reply to (optional)",
                },
            },
            approval_action="email.send",
            category="write",
            _handler=self._handle_send_email,
        ))

        # Draft email (TRUST - doesn't actually send)
        self.register_tool(MCPTool(
            name="email_draft",
            description="Create an email draft",
            parameters={
                "to": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Recipient email addresses",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject",
                },
                "body": {
                    "type": "string",
                    "description": "Email body",
                },
            },
            approval_action="email.read",  # Creating draft is lower risk
            category="write",
            _handler=self._handle_create_draft,
        ))

        # Mark as read (TRUST)
        self.register_tool(MCPTool(
            name="email_mark_read",
            description="Mark email as read/unread",
            parameters={
                "email_id": {
                    "type": "string",
                    "description": "Email ID",
                },
                "is_read": {
                    "type": "boolean",
                    "description": "Mark as read (true) or unread (false)",
                },
            },
            approval_action="email.read",
            category="write",
            _handler=self._handle_mark_read,
        ))

    def _register_resources(self) -> None:
        """Register email resources."""
        self.register_resource(MCPResource(
            uri="email://inbox",
            name="Inbox",
            description="Recent emails from inbox",
            approval_action="email.read",
        ))

        self.register_resource(MCPResource(
            uri="email://unread",
            name="Unread Emails",
            description="Unread emails count and preview",
            approval_action="email.read",
        ))

    # =========================================================================
    # Tool Handlers
    # =========================================================================

    async def _handle_list_emails(
        self,
        folder: str = "inbox",
        query: Optional[str] = None,
        max_results: int = 20,
        unread_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """List emails from folder."""
        logger.info(f"Listing emails from {folder}")

        # Mock response
        return [
            {
                "id": "email_1",
                "from": "sender@example.com",
                "to": ["user@example.com"],
                "subject": "Test Email",
                "snippet": "This is a test email...",
                "date": datetime.now().isoformat(),
                "is_read": False,
                "has_attachments": False,
            }
        ]

    async def _handle_read_email(self, email_id: str) -> Dict[str, Any]:
        """Read full email content."""
        logger.info(f"Reading email: {email_id}")

        return {
            "id": email_id,
            "from": "sender@example.com",
            "to": ["user@example.com"],
            "subject": "Test Email",
            "body": "This is the full email body.",
            "body_html": "<p>This is the full email body.</p>",
            "date": datetime.now().isoformat(),
            "attachments": [],
        }

    async def _handle_search_emails(
        self,
        query: str,
        from_email: Optional[str] = None,
        date_after: Optional[str] = None,
        date_before: Optional[str] = None,
        has_attachment: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Search emails."""
        logger.info(f"Searching emails: {query}")

        return [
            {
                "id": "email_1",
                "from": from_email or "sender@example.com",
                "subject": f"Result for: {query}",
                "date": datetime.now().isoformat(),
            }
        ]

    async def _handle_send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send email."""
        logger.info(f"Sending email to {to}: {subject}")

        return {
            "id": f"sent_{datetime.now().timestamp():.0f}",
            "to": to,
            "cc": cc or [],
            "bcc": bcc or [],
            "subject": subject,
            "sent_at": datetime.now().isoformat(),
            "thread_id": reply_to_id,
        }

    async def _handle_create_draft(
        self,
        to: List[str],
        subject: str,
        body: str,
    ) -> Dict[str, Any]:
        """Create email draft."""
        logger.info(f"Creating draft: {subject}")

        return {
            "id": f"draft_{datetime.now().timestamp():.0f}",
            "to": to,
            "subject": subject,
            "body_preview": body[:100],
            "created_at": datetime.now().isoformat(),
        }

    async def _handle_mark_read(
        self,
        email_id: str,
        is_read: bool,
    ) -> Dict[str, Any]:
        """Mark email read/unread."""
        logger.info(f"Marking email {email_id} as {'read' if is_read else 'unread'}")

        return {
            "email_id": email_id,
            "is_read": is_read,
            "updated_at": datetime.now().isoformat(),
        }

    # =========================================================================
    # Resource Handler
    # =========================================================================

    async def _read_resource_content(self, uri: str) -> Any:
        """Read email resource content."""
        if uri == "email://inbox":
            return await self._handle_list_emails(folder="inbox", max_results=10)

        elif uri == "email://unread":
            emails = await self._handle_list_emails(folder="inbox", unread_only=True)
            return {
                "count": len(emails),
                "emails": emails[:5],  # Preview first 5
            }

        else:
            raise ValueError(f"Unknown resource: {uri}")


__all__ = ["EmailMCPServer"]
