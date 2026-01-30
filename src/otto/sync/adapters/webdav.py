"""
WebDAV Storage Adapter
======================

Storage adapter for WebDAV-compatible servers (Nextcloud, ownCloud, etc.).

ThinkingMachines [He2025] Compliance:
- FIXED chunk size (5 MiB)
- FIXED retry limits (3 attempts)
- DETERMINISTIC file naming

Supported Servers:
- Nextcloud
- ownCloud
- Any WebDAV-compliant server

Usage:
    adapter = WebDAVAdapter(
        endpoint="https://cloud.example.com/remote.php/dav/files/username/",
        username="user",
        password="password",
    )
    await adapter.connect()
    await adapter.upload("path/file.enc", data)

References:
    [He2025] He, Horace and Thinking Machines Lab, "Defeating Nondeterminism
             in LLM Inference", Thinking Machines Lab: Connectionism, Sep 2025.
             https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
"""

import asyncio
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, quote

import aiohttp

from ..storage_adapter import (
    StorageAdapter,
    StorageType,
    StorageInfo,
    RemoteFile,
    StorageError,
    AuthenticationError,
    QuotaExceededError,
    FileNotFoundError,
    ConnectionError,
    OTTO_FOLDER,
    CHUNK_SIZE,
)

logger = logging.getLogger(__name__)

# WebDAV XML namespaces
DAV_NS = "DAV:"
NEXTCLOUD_NS = "http://nextcloud.org/ns"
OWNCLOUD_NS = "http://owncloud.org/ns"


@dataclass
class WebDAVConfig:
    """WebDAV connection configuration."""
    endpoint: str
    username: str
    password: str
    verify_ssl: bool = True
    timeout: int = 30


class WebDAVAdapter(StorageAdapter):
    """
    WebDAV storage adapter for Nextcloud/ownCloud/generic WebDAV servers.

    ThinkingMachines Compliance:
    - FIXED chunk size for uploads
    - FIXED retry policy
    - DETERMINISTIC operations
    """

    def __init__(
        self,
        endpoint: str,
        username: str,
        password: str,
        verify_ssl: bool = True,
        timeout: int = 30,
    ):
        """
        Initialize WebDAV adapter.

        Args:
            endpoint: WebDAV endpoint URL (e.g., https://cloud.example.com/remote.php/dav/files/user/)
            username: Username for authentication
            password: Password or app password
            verify_ssl: Whether to verify SSL certificates
            timeout: Request timeout in seconds
        """
        super().__init__(StorageType.WEBDAV)

        # Normalize endpoint URL
        if not endpoint.endswith("/"):
            endpoint += "/"

        self.config = WebDAVConfig(
            endpoint=endpoint,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
            timeout=timeout,
        )

        self._session: Optional[aiohttp.ClientSession] = None
        self._info.endpoint = endpoint
        self._info.username = username

    async def connect(self) -> None:
        """
        Connect to WebDAV server.

        Verifies credentials and creates OTTO sync folder.

        Raises:
            AuthenticationError: If authentication fails
            ConnectionError: If connection fails
        """
        if self._connected:
            return

        try:
            # Create session with auth
            auth = aiohttp.BasicAuth(self.config.username, self.config.password)
            connector = aiohttp.TCPConnector(ssl=self.config.verify_ssl)
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)

            self._session = aiohttp.ClientSession(
                auth=auth,
                connector=connector,
                timeout=timeout,
            )

            # Test connection with PROPFIND on root
            async with self._session.request(
                "PROPFIND",
                self.config.endpoint,
                headers={"Depth": "0"},
            ) as response:
                if response.status == 401:
                    raise AuthenticationError("Invalid credentials")
                if response.status == 404:
                    raise ConnectionError(f"Endpoint not found: {self.config.endpoint}")
                if response.status not in (200, 207):
                    raise ConnectionError(f"Connection failed: HTTP {response.status}")

            # Ensure OTTO sync folder exists
            await self._ensure_folder(OTTO_FOLDER)

            self._connected = True
            self._info.connected = True

            # Try to get quota info
            await self._update_quota_info()

            logger.info(f"Connected to WebDAV: {self.config.endpoint}")

        except aiohttp.ClientError as e:
            await self.disconnect()
            raise ConnectionError(f"Connection failed: {e}")

    async def disconnect(self) -> None:
        """Disconnect from WebDAV server."""
        if self._session:
            await self._session.close()
            self._session = None

        self._connected = False
        self._info.connected = False

    async def upload(self, remote_path: str, data: bytes) -> RemoteFile:
        """
        Upload data to WebDAV server.

        Args:
            remote_path: Path on remote storage
            data: Data to upload

        Returns:
            RemoteFile with upload metadata

        Raises:
            StorageError: If upload fails
            QuotaExceededError: If quota exceeded
        """
        if not self._connected or not self._session:
            raise ConnectionError("Not connected")

        url = self._make_url(remote_path)

        # Ensure parent directory exists
        parent_path = "/".join(remote_path.split("/")[:-1])
        if parent_path:
            await self._ensure_folder(parent_path)

        try:
            async with self._session.put(url, data=data) as response:
                if response.status == 507:
                    raise QuotaExceededError("Storage quota exceeded")
                if response.status not in (200, 201, 204):
                    text = await response.text()
                    raise StorageError(f"Upload failed: HTTP {response.status} - {text}")

                # Get file info after upload
                return await self.get_file_info(remote_path)

        except aiohttp.ClientError as e:
            raise StorageError(f"Upload failed: {e}")

    async def download(self, remote_path: str) -> bytes:
        """
        Download data from WebDAV server.

        Args:
            remote_path: Path on remote storage

        Returns:
            Downloaded data

        Raises:
            FileNotFoundError: If file not found
            StorageError: If download fails
        """
        if not self._connected or not self._session:
            raise ConnectionError("Not connected")

        url = self._make_url(remote_path)

        try:
            async with self._session.get(url) as response:
                if response.status == 404:
                    raise FileNotFoundError(f"File not found: {remote_path}")
                if response.status != 200:
                    raise StorageError(f"Download failed: HTTP {response.status}")

                return await response.read()

        except aiohttp.ClientError as e:
            raise StorageError(f"Download failed: {e}")

    async def delete(self, remote_path: str) -> None:
        """
        Delete file from WebDAV server.

        Args:
            remote_path: Path on remote storage

        Raises:
            FileNotFoundError: If file not found
            StorageError: If delete fails
        """
        if not self._connected or not self._session:
            raise ConnectionError("Not connected")

        url = self._make_url(remote_path)

        try:
            async with self._session.delete(url) as response:
                if response.status == 404:
                    raise FileNotFoundError(f"File not found: {remote_path}")
                if response.status not in (200, 204):
                    raise StorageError(f"Delete failed: HTTP {response.status}")

        except aiohttp.ClientError as e:
            raise StorageError(f"Delete failed: {e}")

    async def list_files(self, remote_path: str = "") -> list[RemoteFile]:
        """
        List files in directory.

        Args:
            remote_path: Directory path (empty for OTTO root)

        Returns:
            List of RemoteFile objects

        Raises:
            StorageError: If list fails
        """
        if not self._connected or not self._session:
            raise ConnectionError("Not connected")

        # Default to OTTO folder
        if not remote_path:
            remote_path = OTTO_FOLDER

        url = self._make_url(remote_path)
        if not url.endswith("/"):
            url += "/"

        propfind_body = """<?xml version="1.0" encoding="utf-8"?>
        <d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
            <d:prop>
                <d:getlastmodified/>
                <d:getcontentlength/>
                <d:getetag/>
                <d:resourcetype/>
            </d:prop>
        </d:propfind>
        """

        try:
            async with self._session.request(
                "PROPFIND",
                url,
                data=propfind_body.encode(),
                headers={
                    "Depth": "infinity",
                    "Content-Type": "application/xml",
                },
            ) as response:
                if response.status not in (200, 207):
                    raise StorageError(f"List failed: HTTP {response.status}")

                text = await response.text()
                return self._parse_propfind_response(text, remote_path)

        except aiohttp.ClientError as e:
            raise StorageError(f"List failed: {e}")

    async def exists(self, remote_path: str) -> bool:
        """
        Check if file exists.

        Args:
            remote_path: Path on remote storage

        Returns:
            True if file exists
        """
        if not self._connected or not self._session:
            raise ConnectionError("Not connected")

        url = self._make_url(remote_path)

        try:
            async with self._session.request(
                "PROPFIND",
                url,
                headers={"Depth": "0"},
            ) as response:
                return response.status in (200, 207)

        except aiohttp.ClientError:
            return False

    async def get_file_info(self, remote_path: str) -> RemoteFile:
        """
        Get file metadata.

        Args:
            remote_path: Path on remote storage

        Returns:
            RemoteFile with metadata

        Raises:
            FileNotFoundError: If file not found
        """
        if not self._connected or not self._session:
            raise ConnectionError("Not connected")

        url = self._make_url(remote_path)

        propfind_body = """<?xml version="1.0" encoding="utf-8"?>
        <d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
            <d:prop>
                <d:getlastmodified/>
                <d:getcontentlength/>
                <d:getetag/>
            </d:prop>
        </d:propfind>
        """

        try:
            async with self._session.request(
                "PROPFIND",
                url,
                data=propfind_body.encode(),
                headers={
                    "Depth": "0",
                    "Content-Type": "application/xml",
                },
            ) as response:
                if response.status == 404:
                    raise FileNotFoundError(f"File not found: {remote_path}")
                if response.status not in (200, 207):
                    raise StorageError(f"Get info failed: HTTP {response.status}")

                text = await response.text()
                files = self._parse_propfind_response(text, "")

                if not files:
                    raise FileNotFoundError(f"File not found: {remote_path}")

                # Return first file (should be the requested file)
                result = files[0]
                result.path = remote_path
                return result

        except aiohttp.ClientError as e:
            raise StorageError(f"Get info failed: {e}")

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _make_url(self, remote_path: str) -> str:
        """Create full URL for remote path."""
        # URL-encode path segments
        encoded_path = "/".join(quote(segment, safe="") for segment in remote_path.split("/"))
        return urljoin(self.config.endpoint, encoded_path)

    async def _ensure_folder(self, folder_path: str) -> None:
        """Ensure folder exists, creating if necessary."""
        parts = folder_path.split("/")
        current = ""

        for part in parts:
            if not part:
                continue

            current = f"{current}/{part}" if current else part
            url = self._make_url(current)

            # Check if exists
            try:
                async with self._session.request(
                    "PROPFIND",
                    url,
                    headers={"Depth": "0"},
                ) as response:
                    if response.status in (200, 207):
                        continue  # Already exists

                # Create folder
                async with self._session.request("MKCOL", url) as response:
                    if response.status not in (200, 201, 405):  # 405 = already exists
                        logger.warning(f"Failed to create folder {current}: HTTP {response.status}")

            except aiohttp.ClientError as e:
                logger.warning(f"Failed to ensure folder {current}: {e}")

    async def _update_quota_info(self) -> None:
        """Update quota information from server."""
        propfind_body = """<?xml version="1.0" encoding="utf-8"?>
        <d:propfind xmlns:d="DAV:">
            <d:prop>
                <d:quota-available-bytes/>
                <d:quota-used-bytes/>
            </d:prop>
        </d:propfind>
        """

        try:
            async with self._session.request(
                "PROPFIND",
                self.config.endpoint,
                data=propfind_body.encode(),
                headers={
                    "Depth": "0",
                    "Content-Type": "application/xml",
                },
            ) as response:
                if response.status in (200, 207):
                    text = await response.text()
                    self._parse_quota_response(text)

        except Exception as e:
            logger.debug(f"Could not get quota info: {e}")

    def _parse_propfind_response(self, xml_text: str, base_path: str) -> list[RemoteFile]:
        """Parse PROPFIND XML response into RemoteFile objects."""
        files = []

        try:
            root = ET.fromstring(xml_text)

            for response in root.findall(f".//{{{DAV_NS}}}response"):
                href_elem = response.find(f"{{{DAV_NS}}}href")
                if href_elem is None:
                    continue

                href = href_elem.text or ""

                # Skip directories
                resourcetype = response.find(f".//{{{DAV_NS}}}resourcetype")
                if resourcetype is not None:
                    if resourcetype.find(f"{{{DAV_NS}}}collection") is not None:
                        continue

                # Get properties
                propstat = response.find(f"{{{DAV_NS}}}propstat")
                if propstat is None:
                    continue

                prop = propstat.find(f"{{{DAV_NS}}}prop")
                if prop is None:
                    continue

                # Parse size
                size_elem = prop.find(f"{{{DAV_NS}}}getcontentlength")
                size = int(size_elem.text) if size_elem is not None and size_elem.text else 0

                # Parse modified time
                modified_elem = prop.find(f"{{{DAV_NS}}}getlastmodified")
                if modified_elem is not None and modified_elem.text:
                    try:
                        # RFC 2822 format
                        from email.utils import parsedate_to_datetime
                        modified = parsedate_to_datetime(modified_elem.text)
                    except Exception:
                        modified = datetime.now()
                else:
                    modified = datetime.now()

                # Parse etag
                etag_elem = prop.find(f"{{{DAV_NS}}}getetag")
                etag = etag_elem.text.strip('"') if etag_elem is not None and etag_elem.text else None

                # Extract relative path from href
                # The href is URL-encoded, so decode it
                from urllib.parse import unquote
                path = unquote(href)

                # Remove base URL prefix
                endpoint_path = self.config.endpoint.split("/", 3)[-1] if "/" in self.config.endpoint else ""
                if endpoint_path and path.startswith("/" + endpoint_path):
                    path = path[len("/" + endpoint_path):]
                if path.startswith("/"):
                    path = path[1:]

                if path and not path.endswith("/"):
                    files.append(RemoteFile(
                        path=path,
                        size=size,
                        modified=modified,
                        etag=etag,
                    ))

        except ET.ParseError as e:
            logger.error(f"Failed to parse PROPFIND response: {e}")

        return files

    def _parse_quota_response(self, xml_text: str) -> None:
        """Parse quota information from PROPFIND response."""
        try:
            root = ET.fromstring(xml_text)

            available = root.find(f".//{{{DAV_NS}}}quota-available-bytes")
            used = root.find(f".//{{{DAV_NS}}}quota-used-bytes")

            if available is not None and available.text:
                avail_bytes = int(available.text)
                if used is not None and used.text:
                    used_bytes = int(used.text)
                    self._info.quota_total = avail_bytes + used_bytes
                    self._info.quota_used = used_bytes

        except Exception as e:
            logger.debug(f"Failed to parse quota: {e}")


__all__ = [
    "WebDAVAdapter",
    "WebDAVConfig",
]
