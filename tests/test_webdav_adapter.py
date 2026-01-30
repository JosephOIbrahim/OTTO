"""
Tests for WebDAV Storage Adapter.

Tests the WebDAV adapter for Nextcloud/ownCloud sync.
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from otto.sync.adapters.webdav import WebDAVAdapter, WebDAVConfig
from otto.sync.storage_adapter import (
    StorageType,
    RemoteFile,
    StorageError,
    AuthenticationError,
    QuotaExceededError,
    FileNotFoundError,
    ConnectionError,
    OTTO_FOLDER,
    create_storage_adapter,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def webdav_config():
    """Create WebDAV config."""
    return {
        "endpoint": "https://cloud.example.com/remote.php/dav/files/user/",
        "username": "testuser",
        "password": "testpass",
        "verify_ssl": True,
        "timeout": 30,
    }


@pytest.fixture
def adapter(webdav_config):
    """Create WebDAV adapter."""
    return WebDAVAdapter(**webdav_config)


@pytest.fixture
def propfind_response_single():
    """Sample PROPFIND response for single file."""
    return """<?xml version="1.0" encoding="utf-8"?>
    <d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
        <d:response>
            <d:href>/remote.php/dav/files/user/test.enc</d:href>
            <d:propstat>
                <d:prop>
                    <d:getlastmodified>Thu, 01 Jan 2025 12:00:00 GMT</d:getlastmodified>
                    <d:getcontentlength>1024</d:getcontentlength>
                    <d:getetag>"abc123"</d:getetag>
                </d:prop>
            </d:propstat>
        </d:response>
    </d:multistatus>
    """


@pytest.fixture
def propfind_response_dir():
    """Sample PROPFIND response for directory listing."""
    return """<?xml version="1.0" encoding="utf-8"?>
    <d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
        <d:response>
            <d:href>/remote.php/dav/files/user/.otto-sync/</d:href>
            <d:propstat>
                <d:prop>
                    <d:resourcetype><d:collection/></d:resourcetype>
                </d:prop>
            </d:propstat>
        </d:response>
        <d:response>
            <d:href>/remote.php/dav/files/user/.otto-sync/file1.enc</d:href>
            <d:propstat>
                <d:prop>
                    <d:getlastmodified>Thu, 01 Jan 2025 12:00:00 GMT</d:getlastmodified>
                    <d:getcontentlength>1024</d:getcontentlength>
                    <d:getetag>"file1etag"</d:getetag>
                </d:prop>
            </d:propstat>
        </d:response>
        <d:response>
            <d:href>/remote.php/dav/files/user/.otto-sync/file2.enc</d:href>
            <d:propstat>
                <d:prop>
                    <d:getlastmodified>Fri, 02 Jan 2025 12:00:00 GMT</d:getlastmodified>
                    <d:getcontentlength>2048</d:getcontentlength>
                    <d:getetag>"file2etag"</d:getetag>
                </d:prop>
            </d:propstat>
        </d:response>
    </d:multistatus>
    """


@pytest.fixture
def quota_response():
    """Sample quota PROPFIND response."""
    return """<?xml version="1.0" encoding="utf-8"?>
    <d:multistatus xmlns:d="DAV:">
        <d:response>
            <d:href>/remote.php/dav/files/user/</d:href>
            <d:propstat>
                <d:prop>
                    <d:quota-available-bytes>10737418240</d:quota-available-bytes>
                    <d:quota-used-bytes>1073741824</d:quota-used-bytes>
                </d:prop>
            </d:propstat>
        </d:response>
    </d:multistatus>
    """


# =============================================================================
# Test: Configuration
# =============================================================================

class TestWebDAVConfig:
    """Tests for WebDAV configuration."""

    def test_config_defaults(self):
        """Config has correct defaults."""
        config = WebDAVConfig(
            endpoint="https://example.com/dav/",
            username="user",
            password="pass",
        )
        assert config.verify_ssl is True
        assert config.timeout == 30

    def test_config_custom_values(self):
        """Config accepts custom values."""
        config = WebDAVConfig(
            endpoint="https://example.com/dav/",
            username="user",
            password="pass",
            verify_ssl=False,
            timeout=60,
        )
        assert config.verify_ssl is False
        assert config.timeout == 60


# =============================================================================
# Test: Initialization
# =============================================================================

class TestWebDAVAdapterInit:
    """Tests for adapter initialization."""

    def test_init_normalizes_endpoint(self, webdav_config):
        """Init normalizes endpoint URL."""
        # Without trailing slash
        config = webdav_config.copy()
        config["endpoint"] = "https://cloud.example.com/dav"
        adapter = WebDAVAdapter(**config)
        assert adapter.config.endpoint.endswith("/")

    def test_init_preserves_trailing_slash(self, webdav_config):
        """Init preserves existing trailing slash."""
        adapter = WebDAVAdapter(**webdav_config)
        assert adapter.config.endpoint.endswith("/")

    def test_init_sets_storage_type(self, adapter):
        """Init sets correct storage type."""
        assert adapter.storage_type == StorageType.WEBDAV

    def test_init_not_connected(self, adapter):
        """Init starts disconnected."""
        assert adapter.connected is False
        assert adapter.info.connected is False

    def test_init_stores_credentials(self, adapter):
        """Init stores credentials in config."""
        assert adapter.config.username == "testuser"
        assert adapter.config.password == "testpass"


# =============================================================================
# Test: URL Construction
# =============================================================================

class TestURLConstruction:
    """Tests for URL path construction."""

    def test_make_url_simple_path(self, adapter):
        """Make URL for simple path."""
        url = adapter._make_url("test.enc")
        assert url == "https://cloud.example.com/remote.php/dav/files/user/test.enc"

    def test_make_url_nested_path(self, adapter):
        """Make URL for nested path."""
        url = adapter._make_url("folder/subfolder/test.enc")
        assert "folder/subfolder/test.enc" in url

    def test_make_url_encodes_spaces(self, adapter):
        """Make URL encodes spaces."""
        url = adapter._make_url("my file.enc")
        assert "my%20file.enc" in url

    def test_make_url_encodes_special_chars(self, adapter):
        """Make URL encodes special characters."""
        url = adapter._make_url("test#file.enc")
        assert "test%23file.enc" in url


# =============================================================================
# Test: PROPFIND Parsing
# =============================================================================

class TestPropfindParsing:
    """Tests for PROPFIND XML response parsing."""

    def test_parse_single_file(self, adapter, propfind_response_single):
        """Parse single file response."""
        files = adapter._parse_propfind_response(propfind_response_single, "")
        assert len(files) == 1
        assert files[0].size == 1024
        assert files[0].etag == "abc123"

    def test_parse_directory_skips_collections(self, adapter, propfind_response_dir):
        """Parse directory response skips collections."""
        files = adapter._parse_propfind_response(propfind_response_dir, OTTO_FOLDER)
        # Should have 2 files, not the collection
        assert len(files) == 2

    def test_parse_extracts_etags(self, adapter, propfind_response_dir):
        """Parse extracts etag values."""
        files = adapter._parse_propfind_response(propfind_response_dir, OTTO_FOLDER)
        etags = {f.etag for f in files}
        assert "file1etag" in etags
        assert "file2etag" in etags

    def test_parse_extracts_sizes(self, adapter, propfind_response_dir):
        """Parse extracts file sizes."""
        files = adapter._parse_propfind_response(propfind_response_dir, OTTO_FOLDER)
        sizes = {f.size for f in files}
        assert 1024 in sizes
        assert 2048 in sizes

    def test_parse_invalid_xml_returns_empty(self, adapter):
        """Parse returns empty list for invalid XML."""
        files = adapter._parse_propfind_response("not xml", "")
        assert files == []

    def test_parse_quota_response(self, adapter, quota_response):
        """Parse quota information."""
        adapter._parse_quota_response(quota_response)
        # 10GB available + 1GB used = 11GB total
        assert adapter._info.quota_total == 10737418240 + 1073741824
        assert adapter._info.quota_used == 1073741824


# =============================================================================
# Test: Connection
# =============================================================================

class TestConnection:
    """Tests for connection handling."""

    @pytest.mark.asyncio
    async def test_connect_success(self, adapter):
        """Connect succeeds with valid credentials."""
        mock_response = AsyncMock()
        mock_response.status = 207
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_response.text = AsyncMock(return_value="<multistatus/>")

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=mock_response)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            await adapter.connect()

            assert adapter.connected is True
            assert adapter.info.connected is True

    @pytest.mark.asyncio
    async def test_connect_auth_failure(self, adapter):
        """Connect raises AuthenticationError on 401."""
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=mock_response)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            with pytest.raises(AuthenticationError):
                await adapter.connect()

    @pytest.mark.asyncio
    async def test_connect_not_found(self, adapter):
        """Connect raises ConnectionError on 404."""
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=mock_response)
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session

            with pytest.raises(ConnectionError):
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
    async def test_connect_when_already_connected(self, adapter):
        """Connect is no-op when already connected."""
        adapter._connected = True

        await adapter.connect()  # Should not raise

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
    async def test_upload_quota_exceeded(self, adapter):
        """Upload raises QuotaExceededError on 507."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 507
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.put = MagicMock(return_value=mock_response)
        adapter._session.request = MagicMock(return_value=mock_response)

        with pytest.raises(QuotaExceededError):
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
    async def test_delete_file_not_found(self, adapter):
        """Delete raises FileNotFoundError on 404."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.delete = MagicMock(return_value=mock_response)

        with pytest.raises(FileNotFoundError):
            await adapter.delete("nonexistent.enc")

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
    async def test_list_files_defaults_to_otto_folder(self, adapter, propfind_response_dir):
        """List files defaults to OTTO folder."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 207
        mock_response.text = AsyncMock(return_value=propfind_response_dir)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.request = MagicMock(return_value=mock_response)

        files = await adapter.list_files()
        assert len(files) == 2


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
    async def test_exists_returns_true_on_207(self, adapter):
        """Exists returns True on 207 response."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 207
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.request = MagicMock(return_value=mock_response)

        result = await adapter.exists("test.enc")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_on_404(self, adapter):
        """Exists returns False on 404 response."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.request = MagicMock(return_value=mock_response)

        result = await adapter.exists("nonexistent.enc")
        assert result is False


# =============================================================================
# Test: Factory Function
# =============================================================================

class TestFactory:
    """Tests for storage adapter factory."""

    def test_create_webdav_adapter(self, webdav_config):
        """Factory creates WebDAV adapter."""
        adapter = create_storage_adapter("webdav", **webdav_config)
        assert isinstance(adapter, WebDAVAdapter)
        assert adapter.storage_type == StorageType.WEBDAV

    def test_create_webdav_missing_endpoint(self):
        """Factory raises on missing endpoint."""
        with pytest.raises(ValueError, match="endpoint"):
            create_storage_adapter(
                "webdav",
                username="user",
                password="pass",
            )

    def test_create_webdav_missing_username(self):
        """Factory raises on missing username."""
        with pytest.raises(ValueError, match="username"):
            create_storage_adapter(
                "webdav",
                endpoint="https://example.com/dav/",
                password="pass",
            )

    def test_create_webdav_missing_password(self):
        """Factory raises on missing password."""
        with pytest.raises(ValueError, match="password"):
            create_storage_adapter(
                "webdav",
                endpoint="https://example.com/dav/",
                username="user",
            )

    def test_create_webdav_optional_params(self, webdav_config):
        """Factory passes optional params."""
        config = webdav_config.copy()
        config["verify_ssl"] = False
        config["timeout"] = 60

        adapter = create_storage_adapter("webdav", **config)
        assert adapter.config.verify_ssl is False
        assert adapter.config.timeout == 60


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
    async def test_get_file_info_not_found(self, adapter):
        """Get file info raises FileNotFoundError on 404."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.request = MagicMock(return_value=mock_response)

        with pytest.raises(FileNotFoundError):
            await adapter.get_file_info("nonexistent.enc")

    @pytest.mark.asyncio
    async def test_get_file_info_success(self, adapter, propfind_response_single):
        """Get file info returns RemoteFile."""
        adapter._connected = True
        adapter._session = MagicMock()

        mock_response = AsyncMock()
        mock_response.status = 207
        mock_response.text = AsyncMock(return_value=propfind_response_single)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        adapter._session.request = MagicMock(return_value=mock_response)

        info = await adapter.get_file_info("test.enc")
        assert isinstance(info, RemoteFile)
        assert info.path == "test.enc"
        assert info.size == 1024
