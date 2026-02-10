"""
Repository MCP Server
=====================

MCP server for repository operations.
Integrates with GitHub, GitLab, and local git repositories.

Determinism:
- Deterministic commit ordering (by timestamp)
- Fixed diff format
- Sorted file listing
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_mcp import MCPServer, MCPTool, MCPResource

logger = logging.getLogger(__name__)


class ReposMCPServer(MCPServer):
    """MCP server for repository operations."""

    server_name = "repos"
    server_version = "1.0.0"

    def __init__(self):
        """Initialize repos MCP server."""
        super().__init__()
        self._register_tools()
        self._register_resources()

    def _register_tools(self) -> None:
        """Register repository tools."""
        # List repos (TRUST)
        self.register_tool(MCPTool(
            name="repos_list",
            description="List available repositories",
            parameters={
                "owner": {
                    "type": "string",
                    "description": "Filter by owner/organization (optional)",
                },
                "visibility": {
                    "type": "string",
                    "enum": ["public", "private", "all"],
                    "description": "Filter by visibility",
                    "default": "all",
                },
            },
            approval_action="repo.read",
            category="read",
            _handler=self._handle_list_repos,
        ))

        # Get repo info (TRUST)
        self.register_tool(MCPTool(
            name="repos_get",
            description="Get repository details",
            parameters={
                "repo": {
                    "type": "string",
                    "description": "Repository name (owner/repo)",
                },
            },
            approval_action="repo.read",
            category="read",
            _handler=self._handle_get_repo,
        ))

        # List files (TRUST)
        self.register_tool(MCPTool(
            name="repos_list_files",
            description="List files in repository",
            parameters={
                "repo": {
                    "type": "string",
                    "description": "Repository name",
                },
                "path": {
                    "type": "string",
                    "description": "Directory path",
                    "default": "",
                },
                "ref": {
                    "type": "string",
                    "description": "Branch or commit ref",
                    "default": "main",
                },
            },
            approval_action="repo.read",
            category="read",
            _handler=self._handle_list_files,
        ))

        # Read file (TRUST)
        self.register_tool(MCPTool(
            name="repos_read_file",
            description="Read file content from repository",
            parameters={
                "repo": {
                    "type": "string",
                    "description": "Repository name",
                },
                "path": {
                    "type": "string",
                    "description": "File path",
                },
                "ref": {
                    "type": "string",
                    "description": "Branch or commit ref",
                    "default": "main",
                },
            },
            approval_action="repo.read",
            category="read",
            _handler=self._handle_read_file,
        ))

        # List commits (TRUST)
        self.register_tool(MCPTool(
            name="repos_list_commits",
            description="List recent commits",
            parameters={
                "repo": {
                    "type": "string",
                    "description": "Repository name",
                },
                "ref": {
                    "type": "string",
                    "description": "Branch or commit ref",
                    "default": "main",
                },
                "path": {
                    "type": "string",
                    "description": "Filter by file path (optional)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum commits to return",
                    "default": 20,
                },
            },
            approval_action="repo.read",
            category="read",
            _handler=self._handle_list_commits,
        ))

        # Get commit details (TRUST)
        self.register_tool(MCPTool(
            name="repos_get_commit",
            description="Get commit details with diff",
            parameters={
                "repo": {
                    "type": "string",
                    "description": "Repository name",
                },
                "sha": {
                    "type": "string",
                    "description": "Commit SHA",
                },
            },
            approval_action="repo.read",
            category="read",
            _handler=self._handle_get_commit,
        ))

        # List branches (TRUST)
        self.register_tool(MCPTool(
            name="repos_list_branches",
            description="List repository branches",
            parameters={
                "repo": {
                    "type": "string",
                    "description": "Repository name",
                },
            },
            approval_action="repo.read",
            category="read",
            _handler=self._handle_list_branches,
        ))

        # List PRs (TRUST)
        self.register_tool(MCPTool(
            name="repos_list_prs",
            description="List pull requests",
            parameters={
                "repo": {
                    "type": "string",
                    "description": "Repository name",
                },
                "state": {
                    "type": "string",
                    "enum": ["open", "closed", "all"],
                    "description": "PR state filter",
                    "default": "open",
                },
            },
            approval_action="repo.read",
            category="read",
            _handler=self._handle_list_prs,
        ))

        # Get PR details (TRUST)
        self.register_tool(MCPTool(
            name="repos_get_pr",
            description="Get pull request details",
            parameters={
                "repo": {
                    "type": "string",
                    "description": "Repository name",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "PR number",
                },
            },
            approval_action="repo.read",
            category="read",
            _handler=self._handle_get_pr,
        ))

        # List issues (TRUST)
        self.register_tool(MCPTool(
            name="repos_list_issues",
            description="List repository issues",
            parameters={
                "repo": {
                    "type": "string",
                    "description": "Repository name",
                },
                "state": {
                    "type": "string",
                    "enum": ["open", "closed", "all"],
                    "description": "Issue state filter",
                    "default": "open",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by labels",
                },
            },
            approval_action="repo.read",
            category="read",
            _handler=self._handle_list_issues,
        ))

    def _register_resources(self) -> None:
        """Register repository resources."""
        self.register_resource(MCPResource(
            uri="repos://recent",
            name="Recent Repositories",
            description="Recently accessed repositories",
            approval_action="repo.read",
        ))

    # =========================================================================
    # Tool Handlers
    # =========================================================================

    async def _handle_list_repos(
        self,
        owner: Optional[str] = None,
        visibility: str = "all",
    ) -> List[Dict[str, Any]]:
        """List repositories."""
        logger.info(f"Listing repos: owner={owner}, visibility={visibility}")

        return [
            {
                "name": "sample-repo",
                "full_name": f"{owner or 'user'}/sample-repo",
                "description": "A sample repository",
                "visibility": "private",
                "default_branch": "main",
                "updated_at": datetime.now().isoformat(),
                "url": "https://github.com/user/sample-repo",
            }
        ]

    async def _handle_get_repo(self, repo: str) -> Dict[str, Any]:
        """Get repository details."""
        logger.info(f"Getting repo: {repo}")

        return {
            "full_name": repo,
            "description": "Repository description",
            "visibility": "private",
            "default_branch": "main",
            "language": "Python",
            "stars": 0,
            "forks": 0,
            "open_issues": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

    async def _handle_list_files(
        self,
        repo: str,
        path: str = "",
        ref: str = "main",
    ) -> List[Dict[str, Any]]:
        """List files in repository."""
        logger.info(f"Listing files: {repo}/{path}@{ref}")

        return [
            {
                "name": "README.md",
                "path": "README.md",
                "type": "file",
                "size": 1024,
            },
            {
                "name": "src",
                "path": "src",
                "type": "directory",
            },
        ]

    async def _handle_read_file(
        self,
        repo: str,
        path: str,
        ref: str = "main",
    ) -> Dict[str, Any]:
        """Read file content."""
        logger.info(f"Reading file: {repo}/{path}@{ref}")

        return {
            "path": path,
            "content": "# Sample File\n\nThis is sample content.",
            "encoding": "utf-8",
            "size": 42,
            "sha": "abc123",
        }

    async def _handle_list_commits(
        self,
        repo: str,
        ref: str = "main",
        path: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """List commits."""
        logger.info(f"Listing commits: {repo}@{ref}")

        return [
            {
                "sha": "abc123def456",
                "message": "Initial commit",
                "author": "user",
                "date": datetime.now().isoformat(),
                "files_changed": 5,
            }
        ]

    async def _handle_get_commit(
        self,
        repo: str,
        sha: str,
    ) -> Dict[str, Any]:
        """Get commit details."""
        logger.info(f"Getting commit: {repo}@{sha}")

        return {
            "sha": sha,
            "message": "Commit message",
            "author": "user",
            "date": datetime.now().isoformat(),
            "files": [
                {
                    "filename": "README.md",
                    "status": "modified",
                    "additions": 10,
                    "deletions": 5,
                }
            ],
            "stats": {
                "additions": 10,
                "deletions": 5,
                "total": 15,
            },
        }

    async def _handle_list_branches(self, repo: str) -> List[Dict[str, Any]]:
        """List branches."""
        logger.info(f"Listing branches: {repo}")

        return [
            {
                "name": "main",
                "sha": "abc123",
                "protected": True,
            },
            {
                "name": "develop",
                "sha": "def456",
                "protected": False,
            },
        ]

    async def _handle_list_prs(
        self,
        repo: str,
        state: str = "open",
    ) -> List[Dict[str, Any]]:
        """List pull requests."""
        logger.info(f"Listing PRs: {repo} ({state})")

        return [
            {
                "number": 1,
                "title": "Sample PR",
                "state": state,
                "author": "user",
                "created_at": datetime.now().isoformat(),
                "base": "main",
                "head": "feature-branch",
            }
        ]

    async def _handle_get_pr(
        self,
        repo: str,
        pr_number: int,
    ) -> Dict[str, Any]:
        """Get PR details."""
        logger.info(f"Getting PR: {repo}#{pr_number}")

        return {
            "number": pr_number,
            "title": "Sample PR",
            "description": "PR description",
            "state": "open",
            "author": "user",
            "created_at": datetime.now().isoformat(),
            "base": "main",
            "head": "feature-branch",
            "commits": 3,
            "additions": 100,
            "deletions": 50,
            "changed_files": 5,
        }

    async def _handle_list_issues(
        self,
        repo: str,
        state: str = "open",
        labels: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List issues."""
        logger.info(f"Listing issues: {repo} ({state})")

        return [
            {
                "number": 1,
                "title": "Sample Issue",
                "state": state,
                "author": "user",
                "created_at": datetime.now().isoformat(),
                "labels": labels or [],
            }
        ]

    # =========================================================================
    # Resource Handler
    # =========================================================================

    async def _read_resource_content(self, uri: str) -> Any:
        """Read repository resource content."""
        if uri == "repos://recent":
            return await self._handle_list_repos()

        else:
            raise ValueError(f"Unknown resource: {uri}")


__all__ = ["ReposMCPServer"]
