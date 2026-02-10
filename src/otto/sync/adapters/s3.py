"""
S3 Storage Adapter
==================

Storage adapter for AWS S3 and S3-compatible services (MinIO, etc.).

Determinism:
- FIXED chunk size (5 MiB)
- FIXED retry limits (3 attempts)
- DETERMINISTIC file naming

Supported Services:
- AWS S3
- MinIO
- Any S3-compatible API

Usage:
    adapter = S3Adapter(
        bucket="my-bucket",
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        endpoint="https://s3.amazonaws.com",  # Optional for AWS
    )
    await adapter.connect()
    await adapter.upload("path/file.enc", data)

References:
    He, Horace and Thinking Machines Lab, "Defeating Nondeterminism
             in LLM Inference", Thinking Machines Lab: Connectionism, Sep 2025.
             https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
"""

import asyncio
import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote, urlencode
import xml.etree.ElementTree as ET

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

# S3 XML namespace
S3_NS = "http://s3.amazonaws.com/doc/2006-03-01/"


@dataclass
class S3Config:
    """S3 connection configuration."""
    bucket: str
    access_key: str
    secret_key: str
    region: str = "us-east-1"
    endpoint: Optional[str] = None  # None = use AWS default
    use_ssl: bool = True
    timeout: int = 30


class S3Adapter(StorageAdapter):
    """
    S3 storage adapter for AWS S3 / MinIO.

    ThinkingMachines Compliance:
    - FIXED chunk size for uploads
    - FIXED retry policy
    - DETERMINISTIC operations
    """

    def __init__(
        self,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        endpoint: Optional[str] = None,
        use_ssl: bool = True,
        timeout: int = 30,
    ):
        """
        Initialize S3 adapter.

        Args:
            bucket: S3 bucket name
            access_key: AWS access key ID
            secret_key: AWS secret access key
            region: AWS region (default: us-east-1)
            endpoint: Custom endpoint for S3-compatible services (e.g., MinIO)
            use_ssl: Whether to use HTTPS (default: True)
            timeout: Request timeout in seconds
        """
        super().__init__(StorageType.WEBDAV)  # Reusing WEBDAV type for now

        self.config = S3Config(
            bucket=bucket,
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            endpoint=endpoint,
            use_ssl=use_ssl,
            timeout=timeout,
        )

        self._session: Optional[aiohttp.ClientSession] = None
        self._info.endpoint = endpoint or f"s3.{region}.amazonaws.com"
        self._info.username = access_key[:8] + "..."  # Partial key for display

    @property
    def _base_url(self) -> str:
        """Get base URL for S3 requests."""
        protocol = "https" if self.config.use_ssl else "http"
        if self.config.endpoint:
            # Custom endpoint (MinIO, etc.)
            return f"{protocol}://{self.config.endpoint}"
        else:
            # AWS S3 - use virtual-hosted style
            return f"{protocol}://{self.config.bucket}.s3.{self.config.region}.amazonaws.com"

    def _get_host(self) -> str:
        """Get host for signature."""
        if self.config.endpoint:
            return self.config.endpoint
        return f"{self.config.bucket}.s3.{self.config.region}.amazonaws.com"

    async def connect(self) -> None:
        """
        Connect to S3.

        Verifies credentials and creates OTTO prefix.

        Raises:
            AuthenticationError: If authentication fails
            ConnectionError: If connection fails
        """
        if self._connected:
            return

        try:
            connector = aiohttp.TCPConnector(ssl=self.config.use_ssl)
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)

            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
            )

            # Test connection with HEAD request on bucket
            url = self._make_url("")
            headers = self._sign_request("HEAD", "", {})

            async with self._session.head(url, headers=headers) as response:
                if response.status == 403:
                    raise AuthenticationError("Invalid credentials")
                if response.status == 404:
                    raise ConnectionError(f"Bucket not found: {self.config.bucket}")
                if response.status not in (200, 301, 307):
                    raise ConnectionError(f"Connection failed: HTTP {response.status}")

            self._connected = True
            self._info.connected = True

            logger.info(f"Connected to S3: {self._base_url}")

        except aiohttp.ClientError as e:
            await self.disconnect()
            raise ConnectionError(f"Connection failed: {e}")

    async def disconnect(self) -> None:
        """Disconnect from S3."""
        if self._session:
            await self._session.close()
            self._session = None

        self._connected = False
        self._info.connected = False

    async def upload(self, remote_path: str, data: bytes) -> RemoteFile:
        """
        Upload data to S3.

        Args:
            remote_path: Path on S3 (key)
            data: Data to upload

        Returns:
            RemoteFile with upload metadata

        Raises:
            StorageError: If upload fails
        """
        if not self._connected or not self._session:
            raise ConnectionError("Not connected")

        # Prepend OTTO folder
        key = f"{OTTO_FOLDER}/{remote_path}"
        url = self._make_url(key)

        # Calculate content hash
        content_hash = hashlib.sha256(data).hexdigest()

        headers = self._sign_request(
            "PUT",
            key,
            {
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(data)),
                "x-amz-content-sha256": content_hash,
            },
            payload_hash=content_hash,
        )

        try:
            async with self._session.put(url, data=data, headers=headers) as response:
                if response.status == 403:
                    raise AuthenticationError("Access denied")
                if response.status not in (200, 204):
                    text = await response.text()
                    raise StorageError(f"Upload failed: HTTP {response.status} - {text}")

                # Get ETag from response
                etag = response.headers.get("ETag", "").strip('"')

                return RemoteFile(
                    path=remote_path,
                    size=len(data),
                    modified=datetime.now(timezone.utc),
                    etag=etag,
                    content_hash=content_hash,
                )

        except aiohttp.ClientError as e:
            raise StorageError(f"Upload failed: {e}")

    async def download(self, remote_path: str) -> bytes:
        """
        Download data from S3.

        Args:
            remote_path: Path on S3 (key)

        Returns:
            Downloaded data

        Raises:
            FileNotFoundError: If file not found
            StorageError: If download fails
        """
        if not self._connected or not self._session:
            raise ConnectionError("Not connected")

        key = f"{OTTO_FOLDER}/{remote_path}"
        url = self._make_url(key)
        headers = self._sign_request("GET", key, {})

        try:
            async with self._session.get(url, headers=headers) as response:
                if response.status == 404:
                    raise FileNotFoundError(f"File not found: {remote_path}")
                if response.status == 403:
                    raise AuthenticationError("Access denied")
                if response.status != 200:
                    raise StorageError(f"Download failed: HTTP {response.status}")

                return await response.read()

        except aiohttp.ClientError as e:
            raise StorageError(f"Download failed: {e}")

    async def delete(self, remote_path: str) -> None:
        """
        Delete file from S3.

        Args:
            remote_path: Path on S3 (key)

        Raises:
            FileNotFoundError: If file not found
            StorageError: If delete fails
        """
        if not self._connected or not self._session:
            raise ConnectionError("Not connected")

        key = f"{OTTO_FOLDER}/{remote_path}"
        url = self._make_url(key)
        headers = self._sign_request("DELETE", key, {})

        try:
            async with self._session.delete(url, headers=headers) as response:
                # S3 returns 204 even if file doesn't exist
                if response.status == 403:
                    raise AuthenticationError("Access denied")
                if response.status not in (200, 204):
                    raise StorageError(f"Delete failed: HTTP {response.status}")

        except aiohttp.ClientError as e:
            raise StorageError(f"Delete failed: {e}")

    async def list_files(self, remote_path: str = "") -> list[RemoteFile]:
        """
        List files with prefix.

        Args:
            remote_path: Prefix to list (empty for OTTO root)

        Returns:
            List of RemoteFile objects

        Raises:
            StorageError: If list fails
        """
        if not self._connected or not self._session:
            raise ConnectionError("Not connected")

        # Default to OTTO folder
        prefix = f"{OTTO_FOLDER}/{remote_path}" if remote_path else f"{OTTO_FOLDER}/"

        files = []
        continuation_token = None

        while True:
            # Build query params
            params = {
                "list-type": "2",
                "prefix": prefix,
            }
            if continuation_token:
                params["continuation-token"] = continuation_token

            url = self._make_url("", query_params=params)
            headers = self._sign_request("GET", "", {}, query_params=params)

            try:
                async with self._session.get(url, headers=headers) as response:
                    if response.status != 200:
                        raise StorageError(f"List failed: HTTP {response.status}")

                    text = await response.text()
                    batch, continuation_token = self._parse_list_response(text, prefix)
                    files.extend(batch)

                    if not continuation_token:
                        break

            except aiohttp.ClientError as e:
                raise StorageError(f"List failed: {e}")

        return files

    async def exists(self, remote_path: str) -> bool:
        """
        Check if file exists.

        Args:
            remote_path: Path on S3 (key)

        Returns:
            True if file exists
        """
        if not self._connected or not self._session:
            raise ConnectionError("Not connected")

        key = f"{OTTO_FOLDER}/{remote_path}"
        url = self._make_url(key)
        headers = self._sign_request("HEAD", key, {})

        try:
            async with self._session.head(url, headers=headers) as response:
                return response.status == 200

        except aiohttp.ClientError:
            return False

    async def get_file_info(self, remote_path: str) -> RemoteFile:
        """
        Get file metadata.

        Args:
            remote_path: Path on S3 (key)

        Returns:
            RemoteFile with metadata

        Raises:
            FileNotFoundError: If file not found
        """
        if not self._connected or not self._session:
            raise ConnectionError("Not connected")

        key = f"{OTTO_FOLDER}/{remote_path}"
        url = self._make_url(key)
        headers = self._sign_request("HEAD", key, {})

        try:
            async with self._session.head(url, headers=headers) as response:
                if response.status == 404:
                    raise FileNotFoundError(f"File not found: {remote_path}")
                if response.status != 200:
                    raise StorageError(f"Get info failed: HTTP {response.status}")

                size = int(response.headers.get("Content-Length", 0))
                etag = response.headers.get("ETag", "").strip('"')
                last_modified = response.headers.get("Last-Modified", "")

                # Parse Last-Modified header
                try:
                    from email.utils import parsedate_to_datetime
                    modified = parsedate_to_datetime(last_modified)
                except Exception:
                    modified = datetime.now(timezone.utc)

                return RemoteFile(
                    path=remote_path,
                    size=size,
                    modified=modified,
                    etag=etag,
                )

        except aiohttp.ClientError as e:
            raise StorageError(f"Get info failed: {e}")

    # =========================================================================
    # AWS Signature V4 Implementation
    # =========================================================================

    def _sign_request(
        self,
        method: str,
        key: str,
        headers: dict,
        query_params: Optional[dict] = None,
        payload_hash: Optional[str] = None,
    ) -> dict:
        """
        Sign request with AWS Signature V4.

        Args:
            method: HTTP method
            key: S3 object key
            headers: Request headers
            query_params: Query parameters
            payload_hash: SHA256 hash of payload (UNSIGNED-PAYLOAD for streaming)

        Returns:
            Headers with Authorization
        """
        now = datetime.now(timezone.utc)
        date_stamp = now.strftime("%Y%m%d")
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")

        # Default payload hash
        if payload_hash is None:
            payload_hash = "UNSIGNED-PAYLOAD"

        # Build headers
        host = self._get_host()
        signed_headers = {
            "host": host,
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
        }
        signed_headers.update({k.lower(): v for k, v in headers.items()})

        # Canonical request
        canonical_uri = "/" + quote(key, safe="/")
        canonical_querystring = ""
        if query_params:
            canonical_querystring = "&".join(
                f"{quote(k, safe='')}={quote(str(v), safe='')}"
                for k, v in sorted(query_params.items())
            )

        canonical_headers = "".join(
            f"{k}:{v}\n" for k, v in sorted(signed_headers.items())
        )
        signed_headers_str = ";".join(sorted(signed_headers.keys()))

        canonical_request = "\n".join([
            method,
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers_str,
            payload_hash,
        ])

        # String to sign
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.config.region}/s3/aws4_request"
        string_to_sign = "\n".join([
            algorithm,
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ])

        # Signing key
        def sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        k_date = sign(f"AWS4{self.config.secret_key}".encode(), date_stamp)
        k_region = sign(k_date, self.config.region)
        k_service = sign(k_region, "s3")
        k_signing = sign(k_service, "aws4_request")

        # Signature
        signature = hmac.new(
            k_signing,
            string_to_sign.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Authorization header
        authorization = (
            f"{algorithm} "
            f"Credential={self.config.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers_str}, "
            f"Signature={signature}"
        )

        # Return all headers
        result = dict(signed_headers)
        result["Authorization"] = authorization
        return result

    def _make_url(self, key: str, query_params: Optional[dict] = None) -> str:
        """Create full URL for S3 request."""
        url = self._base_url
        if key:
            url = f"{url}/{quote(key, safe='/')}"

        if query_params:
            query_string = "&".join(
                f"{quote(k, safe='')}={quote(str(v), safe='')}"
                for k, v in sorted(query_params.items())
            )
            url = f"{url}?{query_string}"

        return url

    def _parse_list_response(
        self,
        xml_text: str,
        prefix: str,
    ) -> tuple[list[RemoteFile], Optional[str]]:
        """
        Parse ListObjectsV2 XML response.

        Returns:
            Tuple of (files, continuation_token)
        """
        files = []
        continuation_token = None

        try:
            root = ET.fromstring(xml_text)

            # Handle namespace
            ns = {"s3": S3_NS}

            # Check for continuation
            cont_elem = root.find("s3:NextContinuationToken", ns)
            if cont_elem is not None and cont_elem.text:
                continuation_token = cont_elem.text

            # Parse contents
            for content in root.findall("s3:Contents", ns):
                key_elem = content.find("s3:Key", ns)
                if key_elem is None or not key_elem.text:
                    continue

                key = key_elem.text

                # Skip the prefix itself
                if key == prefix or key.endswith("/"):
                    continue

                # Get size
                size_elem = content.find("s3:Size", ns)
                size = int(size_elem.text) if size_elem is not None and size_elem.text else 0

                # Get last modified
                modified_elem = content.find("s3:LastModified", ns)
                if modified_elem is not None and modified_elem.text:
                    try:
                        modified = datetime.fromisoformat(
                            modified_elem.text.replace("Z", "+00:00")
                        )
                    except Exception:
                        modified = datetime.now(timezone.utc)
                else:
                    modified = datetime.now(timezone.utc)

                # Get ETag
                etag_elem = content.find("s3:ETag", ns)
                etag = etag_elem.text.strip('"') if etag_elem is not None and etag_elem.text else None

                # Remove OTTO_FOLDER prefix from path
                path = key
                if path.startswith(f"{OTTO_FOLDER}/"):
                    path = path[len(f"{OTTO_FOLDER}/"):]

                files.append(RemoteFile(
                    path=path,
                    size=size,
                    modified=modified,
                    etag=etag,
                ))

        except ET.ParseError as e:
            logger.error(f"Failed to parse S3 list response: {e}")

        return files, continuation_token


__all__ = [
    "S3Adapter",
    "S3Config",
]
