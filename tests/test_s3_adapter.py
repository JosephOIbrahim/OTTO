"""
Tests for S3 Storage Adapter.

Tests the S3 adapter for AWS S3 / MinIO sync.
"""

import asyncio
import hashlib
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from otto.sync.adapters.s3 import S3Adapter, S3Config
from otto.sync.storage_adapter import (
    StorageType,
    RemoteFile,
    StorageError,
    AuthenticationError,
    FileNotFoundError,
    ConnectionError,
    OTTO_FOLDER,
    create_storage_adapter,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def s3_config():
    """Create S3 config."""
    return {
        "bucket": "test-bucket",
        "access_key": "AKIAIOSFODNN7EXAMPLE",
        "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "region": "us-east-1",
    }


@pytest.fixture
def adapter(s3_config):
    """Create S3 adapter."""
    return S3Adapter(**s3_config)


@pytest.fixture
def list_response_single():
    """Sample ListObjectsV2 response with single object."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
        <Name>test-bucket</Name>
        <Prefix>.otto-sync/</Prefix>
        <Contents>
            <Key>.otto-sync/test.enc</Key>
            <LastModified>2025-01-01T12:00:00.000Z</LastModified>
            <ETag>"abc123"</ETag>
            <Size>1024</Size>
        </Contents>
    </ListBucketResult>
    """


@pytest.fixture
def list_response_multiple():
    """Sample ListObjectsV2 response with multiple objects."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
        <Name>test-bucket</Name>
        <Prefix>.otto-sync/</Prefix>
        <Contents>
            <Key>.otto-sync/file1.enc</Key>
            <LastModified>2025-01-01T12:00:00.000Z</LastModified>
            <ETag>"etag1"</ETag>
            <Size>1024</Size>
        </Contents>
        <Contents>
            <Key>.otto-sync/file2.enc</Key>
            <LastModified>2025-01-02T12:00:00.000Z</LastModified>
            <ETag>"etag2"</ETag>
            <Size>2048</Size>
        </Contents>
        <Contents>
            <Key>.otto-sync/subdir/file3.enc</Key>
            <LastModified>2025-01-03T12:00:00.000Z</LastModified>
            <ETag>"etag3"</ETag>
            <Size>4096</Size>
        </Contents>
    </ListBucketResult>
    """


@pytest.fixture
def list_response_paginated():
    """Sample paginated ListObjectsV2 response."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
        <Name>test-bucket</Name>
        <Prefix>.otto-sync/</Prefix>
        <IsTruncated>true</IsTruncated>
        <NextContinuationToken>token123</NextContinuationToken>
        <Contents>
            <Key>.otto-sync/file1.enc</Key>
            <LastModified>2025-01-01T12:00:00.000Z</LastModified>
            <ETag>"etag1"</ETag>
            <Size>1024</Size>
        </Contents>
    </ListBucketResult>
    """


# =============================================================================
# Test: Configuration
# =============================================================================

class TestS3Config:
    """Tests for S3 configuration."""

    def test_config_defaults(self):
        """Config has correct defaults."""
        config = S3Config(
            bucket="bucket",
            access_key="key",
            secret_key="secret",
        )
        assert config.region == "us-east-1"
        assert config.endpoint is None
        assert config.use_ssl is True
        assert config.timeout == 30

    def test_config_custom_values(self):
        """Config accepts custom values."""
        config = S3Config(
            bucket="bucket",
            access_key="key",
            secret_key="secret",
            region="eu-west-1",
            endpoint="minio.example.com:9000",
            use_ssl=False,
            timeout=60,
        )
        assert config.region == "eu-west-1"
        assert config.endpoint == "minio.example.com:9000"
        assert config.use_ssl is False
        assert config.timeout == 60


# =============================================================================
# Test: Initialization
# =============================================================================

class TestS3AdapterInit:
    """Tests for adapter initialization."""

    def test_init_stores_config(self, s3_config):
        """Init stores configuration."""
        adapter = S3Adapter(**s3_config)
        assert adapter.config.bucket == "test-bucket"
        assert adapter.config.access_key == "AKIAIOSFODNN7EXAMPLE"
        assert adapter.config.region == "us-east-1"

    def test_init_not_connected(self, adapter):
        """Init starts disconnected."""
        assert adapter.connected is False
        assert adapter.info.connected is False

    def test_init_custom_endpoint(self, s3_config):
        """Init with custom endpoint (MinIO)."""
        config = s3_config.copy()
        config["endpoint"] = "minio.local:9000"
        adapter = S3Adapter(**config)
        assert adapter.config.endpoint == "minio.local:9000"

    def test_base_url_aws(self, s3_config):
        """Base URL for AWS S3."""
        adapter = S3Adapter(**s3_config)
        assert "s3.us-east-1.amazonaws.com" in adapter._base_url
        assert "test-bucket" in adapter._base_url

    def test_base_url_minio(self, s3_config):
        """Base URL for MinIO."""
        config = s3_config.copy()
        config["endpoint"] = "minio.local:9000"
        adapter = S3Adapter(**config)
        assert "minio.local:9000" in adapter._base_url


# =============================================================================
# Test: URL Construction
# =============================================================================

class TestURLConstruction:
    """Tests for URL construction."""

    def test_make_url_simple(self, adapter):
        """Make URL for simple key."""
        url = adapter._make_url("test.enc")
        assert "test.enc" in url

    def test_make_url_empty(self, adapter):
        """Make URL for bucket root."""
        url = adapter._make_url("")
        assert adapter._base_url in url

    def test_make_url_with_params(self, adapter):
        """Make URL with query parameters."""
        url = adapter._make_url("", query_params={"list-type": "2", "prefix": "test/"})
        assert "list-type=2" in url
        assert "prefix=test" in url

    def test_make_url_encodes_special_chars(self, adapter):
        """Make URL encodes special characters."""
        url = adapter._make_url("path with spaces/file.enc")
        assert "path%20with%20spaces" in url


# =============================================================================
# Test: AWS Signature V4
# =============================================================================

class TestSignature:
    """Tests for AWS Signature V4."""

    def test_sign_request_has_authorization(self, adapter):
        """Signed request has Authorization header."""
        headers = adapter._sign_request("GET", "test.enc", {})
        assert "Authorization" in headers
        assert "AWS4-HMAC-SHA256" in headers["Authorization"]

    def test_sign_request_has_date(self, adapter):
        """Signed request has x-amz-date header."""
        headers = adapter._sign_request("GET", "test.enc", {})
        assert "x-amz-date" in headers

    def test_sign_request_has_content_sha256(self, adapter):
        """Signed request has x-amz-content-sha256 header."""
        headers = adapter._sign_request("GET", "test.enc", {})
        assert "x-amz-content-sha256" in headers

    def test_sign_request_includes_credential(self, adapter):
        """Authorization includes Credential."""
        headers = adapter._sign_request("GET", "test.enc", {})
        assert "Credential=AKIAIOSFODNN7EXAMPLE" in headers["Authorization"]

    def test_sign_request_includes_region(self, adapter):
        """Authorization includes region."""
        headers = adapter._sign_request("GET", "test.enc", {})
        assert "us-east-1" in headers["Authorization"]


# =============================================================================
# Test: List Response Parsing
# =============================================================================

class TestListParsing:
    """Tests for ListObjectsV2 response parsing."""

    def test_parse_single_object(self, adapter, list_response_single):
        """Parse response with single object."""
        files, token = adapter._parse_list_response(list_response_single, f"{OTTO_FOLDER}/")
        assert len(files) == 1
        assert files[0].path == "test.enc"
        assert files[0].size == 1024
        assert files[0].etag == "abc123"
        assert token is None

    def test_parse_multiple_objects(self, adapter, list_response_multiple):
        """Parse response with multiple objects."""
        files, token = adapter._parse_list_response(list_response_multiple, f"{OTTO_FOLDER}/")
        assert len(files) == 3
        paths = {f.path for f in files}
        assert "file1.enc" in paths
        assert "file2.enc" in paths
        assert "subdir/file3.enc" in paths

    def test_parse_extracts_sizes(self, adapter, list_response_multiple):
        """Parse extracts file sizes."""
        files, _ = adapter._parse_list_response(list_response_multiple, f"{OTTO_FOLDER}/")
        sizes = {f.size for f in files}
        assert 1024 in sizes
        assert 2048 in sizes
        assert 4096 in sizes

    def test_parse_continuation_token(self, adapter, list_response_paginated):
        """Parse extracts continuation token."""
        files, token = adapter._parse_list_response(list_response_paginated, f"{OTTO_FOLDER}/")
        assert token == "token123"

    def test_parse_invalid_xml_returns_empty(self, adapter):
        """Parse returns empty list for invalid XML."""
        files, token = adapter._parse_list_response("not xml", f"{OTTO_FOLDER}/")
        assert files == []
        assert token is None

    def test_parse_strips_otto_prefix(self, adapter, list_response_single):
        """Parse strips OTTO_FOLDER prefix from paths."""
        files, _ = adapter._parse_list_response(list_response_single, f"{OTTO_FOLDER}/")
        # Path should be "test.enc" not ".otto-sync/test.enc"
        assert files[0].path == "test.enc"


# =============================================================================
# Test: Connection
# =============================================================================

class TestConnection:
    """Tests for connection handling."""

    @pytest.mark.asyncio
    async def test_connect_success(self, adapter):
        """Connect succeeds with valid credentials."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.head = MagicMock(return_value=mock_response)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            await adapter.connect()

            assert adapter.connected is True

    @pytest.mark.asyncio
    async def test_connect_auth_failure(self, adapter):
        """Connect raises AuthenticationError on 403."""
        mock_response = AsyncMock()
        mock_response.status = 403
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.head = MagicMock(return_value=mock_response)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            with pytest.raises(AuthenticationError):
                await adapter.connect()

    @pytest.mark.asyncio
    async def test_connect_bucket_not_found(self, adapter):
        """Connect raises ConnectionError on 404."""
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.head = MagicMock(return_value=mock_response)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            with pytest.raises(ConnectionError, match="Bucket not found"):
                await adapter.connect()

    @pytest.mark.asyncio
    async def test_disconnect_closes_session(self, adapter):
        """Disconnect closes session."""
        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        adapter._session = mock_session
        adapter._connected = True

        await adapter.disconnect()

        mock_session.close.assert_called_once()
        assert adapter.connected is False

    @pytest.mark.asyncio
    async def test_connect_already_connected(self, adapter):
        """Connect is no-op when already connected."""
        adapter._connected = True

        await adapter.connect()

        assert adapter.connected is True


# =============================================================================
# Test: Upload
# =============================================================================

class TestUpload:
    """Tests for upload operations."""

    @pytest.mark.asyncio
    async def test_upload_not_connected_raises(self, adapter):
        """Upload raises when not connected."""
        with pytest.raises(ConnectionError, match="Not connected"):
            await adapter.upload("test.enc", b"data")

    @pytest.mark.asyncio
    async def test_upload_success(self, adapter):
        """Upload succeeds and returns RemoteFile."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"ETag": '"abc123"'}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.put = MagicMock(return_value=mock_response)

        result = await adapter.upload("test.enc", b"test data")

        assert isinstance(result, RemoteFile)
        assert result.path == "test.enc"
        assert result.etag == "abc123"
        assert result.content_hash == hashlib.sha256(b"test data").hexdigest()

    @pytest.mark.asyncio
    async def test_upload_auth_error(self, adapter):
        """Upload raises AuthenticationError on 403."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 403
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.put = MagicMock(return_value=mock_response)

        with pytest.raises(AuthenticationError):
            await adapter.upload("test.enc", b"data")


# =============================================================================
# Test: Download
# =============================================================================

class TestDownload:
    """Tests for download operations."""

    @pytest.mark.asyncio
    async def test_download_not_connected_raises(self, adapter):
        """Download raises when not connected."""
        with pytest.raises(ConnectionError, match="Not connected"):
            await adapter.download("test.enc")

    @pytest.mark.asyncio
    async def test_download_success(self, adapter):
        """Download returns file data."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"file content")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.get = MagicMock(return_value=mock_response)

        data = await adapter.download("test.enc")
        assert data == b"file content"

    @pytest.mark.asyncio
    async def test_download_file_not_found(self, adapter):
        """Download raises FileNotFoundError on 404."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.get = MagicMock(return_value=mock_response)

        with pytest.raises(FileNotFoundError):
            await adapter.download("nonexistent.enc")


# =============================================================================
# Test: Delete
# =============================================================================

class TestDelete:
    """Tests for delete operations."""

    @pytest.mark.asyncio
    async def test_delete_not_connected_raises(self, adapter):
        """Delete raises when not connected."""
        with pytest.raises(ConnectionError, match="Not connected"):
            await adapter.delete("test.enc")

    @pytest.mark.asyncio
    async def test_delete_success(self, adapter):
        """Delete succeeds on 204."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.delete = MagicMock(return_value=mock_response)

        await adapter.delete("test.enc")  # Should not raise


# =============================================================================
# Test: List Files
# =============================================================================

class TestListFiles:
    """Tests for list files operations."""

    @pytest.mark.asyncio
    async def test_list_files_not_connected_raises(self, adapter):
        """List files raises when not connected."""
        with pytest.raises(ConnectionError, match="Not connected"):
            await adapter.list_files()

    @pytest.mark.asyncio
    async def test_list_files_success(self, adapter, list_response_multiple):
        """List files returns RemoteFile objects."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=list_response_multiple)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.get = MagicMock(return_value=mock_response)

        files = await adapter.list_files()
        assert len(files) == 3


# =============================================================================
# Test: Exists
# =============================================================================

class TestExists:
    """Tests for exists operations."""

    @pytest.mark.asyncio
    async def test_exists_not_connected_raises(self, adapter):
        """Exists raises when not connected."""
        with pytest.raises(ConnectionError, match="Not connected"):
            await adapter.exists("test.enc")

    @pytest.mark.asyncio
    async def test_exists_returns_true(self, adapter):
        """Exists returns True when file exists."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.head = MagicMock(return_value=mock_response)

        result = await adapter.exists("test.enc")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false(self, adapter):
        """Exists returns False when file doesn't exist."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.head = MagicMock(return_value=mock_response)

        result = await adapter.exists("nonexistent.enc")
        assert result is False


# =============================================================================
# Test: Get File Info
# =============================================================================

class TestGetFileInfo:
    """Tests for get file info operations."""

    @pytest.mark.asyncio
    async def test_get_file_info_not_connected_raises(self, adapter):
        """Get file info raises when not connected."""
        with pytest.raises(ConnectionError, match="Not connected"):
            await adapter.get_file_info("test.enc")

    @pytest.mark.asyncio
    async def test_get_file_info_success(self, adapter):
        """Get file info returns RemoteFile."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {
            "Content-Length": "1024",
            "ETag": '"abc123"',
            "Last-Modified": "Thu, 01 Jan 2025 12:00:00 GMT",
        }
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.head = MagicMock(return_value=mock_response)

        info = await adapter.get_file_info("test.enc")
        assert isinstance(info, RemoteFile)
        assert info.path == "test.enc"
        assert info.size == 1024
        assert info.etag == "abc123"

    @pytest.mark.asyncio
    async def test_get_file_info_not_found(self, adapter):
        """Get file info raises FileNotFoundError on 404."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.head = MagicMock(return_value=mock_response)

        with pytest.raises(FileNotFoundError):
            await adapter.get_file_info("nonexistent.enc")


# =============================================================================
# Test: Factory Function
# =============================================================================

class TestFactory:
    """Tests for storage adapter factory."""

    def test_create_s3_adapter(self, s3_config):
        """Factory creates S3 adapter."""
        adapter = create_storage_adapter("s3", **s3_config)
        assert isinstance(adapter, S3Adapter)

    def test_create_s3_missing_bucket(self):
        """Factory raises on missing bucket."""
        with pytest.raises(ValueError, match="bucket"):
            create_storage_adapter(
                "s3",
                access_key="key",
                secret_key="secret",
            )

    def test_create_s3_missing_access_key(self):
        """Factory raises on missing access_key."""
        with pytest.raises(ValueError, match="access_key"):
            create_storage_adapter(
                "s3",
                bucket="bucket",
                secret_key="secret",
            )

    def test_create_s3_missing_secret_key(self):
        """Factory raises on missing secret_key."""
        with pytest.raises(ValueError, match="secret_key"):
            create_storage_adapter(
                "s3",
                bucket="bucket",
                access_key="key",
            )

    def test_create_s3_with_minio_endpoint(self, s3_config):
        """Factory passes custom endpoint for MinIO."""
        config = s3_config.copy()
        config["endpoint"] = "minio.local:9000"
        config["use_ssl"] = False

        adapter = create_storage_adapter("s3", **config)
        assert adapter.config.endpoint == "minio.local:9000"
        assert adapter.config.use_ssl is False

    def test_create_s3_optional_params(self, s3_config):
        """Factory passes optional params."""
        config = s3_config.copy()
        config["region"] = "eu-west-1"
        config["timeout"] = 60

        adapter = create_storage_adapter("s3", **config)
        assert adapter.config.region == "eu-west-1"
        assert adapter.config.timeout == 60
