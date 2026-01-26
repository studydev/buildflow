"""Storage Service for Azure Blob Storage operations.

Per tasks.md T600: Implements upload/download/delete for generated assets.
"""

import logging
from datetime import datetime, timedelta
from typing import BinaryIO, Optional, Union
from uuid import UUID

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    ContainerClient,
    ContentSettings,
    generate_blob_sas,
)

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class BlobNotFoundError(StorageError):
    """Blob not found in storage."""
    pass


class StorageUploadError(StorageError):
    """Failed to upload blob."""
    pass


# Container names
REPO_IMAGES_CONTAINER = "repo-images"  # AI-generated thumbnail images

# Content type mappings
CONTENT_TYPE_MAP = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "svg": "image/svg+xml",
    "json": "application/json",
    "txt": "text/plain",
}


class StorageService:
    """
    Service for Azure Blob Storage operations.

    Provides:
    - upload_blob(): Upload file to blob storage
    - download_blob(): Download blob content
    - get_blob_url(): Get direct blob URL
    - get_sas_url(): Generate SAS URL with time-limited access
    - delete_blob(): Remove blob from storage
    - list_blobs(): List blobs in a container/prefix
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        account_name: Optional[str] = None,
        account_key: Optional[str] = None,
    ):
        """
        Initialize storage service.

        Can be initialized with connection string or account name/key.
        Falls back to settings if not provided.
        """
        self.connection_string = connection_string or getattr(
            settings, 'azure_storage_connection_string', None
        )
        self.account_name = account_name or getattr(
            settings, 'azure_storage_account_name', None
        )
        self.account_key = account_key or getattr(
            settings, 'azure_storage_account_key', None
        )

        self._client: Optional[BlobServiceClient] = None
        self._containers: dict[str, ContainerClient] = {}

    @property
    def client(self) -> BlobServiceClient:
        """Get or create blob service client."""
        if self._client is None:
            if self.connection_string:
                self._client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
            elif self.account_name and self.account_key:
                account_url = f"https://{self.account_name}.blob.core.windows.net"
                self._client = BlobServiceClient(
                    account_url=account_url,
                    credential=self.account_key,
                )
            else:
                raise StorageError(
                    "Storage not configured. Provide connection_string or account_name/key."
                )
        return self._client

    def get_container_client(self, container_name: str) -> ContainerClient:
        """Get container client, creating container if needed."""
        if container_name not in self._containers:
            container_client = self.client.get_container_client(container_name)

            # Ensure container exists
            try:
                container_client.create_container()
                logger.info(f"Created container: {container_name}")
            except ResourceExistsError:
                pass  # Container already exists

            self._containers[container_name] = container_client

        return self._containers[container_name]

    async def upload_blob(
        self,
        container_name: str,
        blob_path: str,
        data: Union[bytes, BinaryIO],
        content_type: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
        overwrite: bool = True,
    ) -> str:
        """
        Upload data to blob storage.

        Args:
            container_name: Target container name
            blob_path: Path within container (e.g., "{content_id}/thumbnail.png")
            data: File content as bytes or file-like object
            content_type: MIME type (auto-detected from extension if not provided)
            metadata: Optional metadata dict
            overwrite: Whether to overwrite existing blob

        Returns:
            Full blob URL
        """
        try:
            container_client = self.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_path)

            # Auto-detect content type from extension
            if content_type is None:
                ext = blob_path.split('.')[-1].lower() if '.' in blob_path else None
                content_type = CONTENT_TYPE_MAP.get(ext, "application/octet-stream")

            content_settings = ContentSettings(content_type=content_type)

            blob_client.upload_blob(
                data,
                overwrite=overwrite,
                content_settings=content_settings,
                metadata=metadata,
            )

            logger.info(f"Uploaded blob: {container_name}/{blob_path}")

            return blob_client.url

        except Exception as e:
            logger.error(f"Failed to upload blob {blob_path}: {e}")
            raise StorageUploadError(f"Upload failed: {e}")

    async def download_blob(
        self,
        container_name: str,
        blob_path: str,
    ) -> bytes:
        """
        Download blob content.

        Args:
            container_name: Container name
            blob_path: Path within container

        Returns:
            Blob content as bytes
        """
        try:
            container_client = self.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_path)

            download_stream = blob_client.download_blob()
            return download_stream.readall()

        except ResourceNotFoundError:
            raise BlobNotFoundError(f"Blob not found: {container_name}/{blob_path}")
        except Exception as e:
            logger.error(f"Failed to download blob {blob_path}: {e}")
            raise StorageError(f"Download failed: {e}")

    def get_blob_url(
        self,
        container_name: str,
        blob_path: str,
    ) -> str:
        """
        Get the direct URL of a blob.

        Note: This URL requires authentication unless the container is public.

        Args:
            container_name: Container name
            blob_path: Path within container

        Returns:
            Blob URL
        """
        container_client = self.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_path)
        return blob_client.url

    def get_sas_url(
        self,
        container_name: str,
        blob_path: str,
        expiry_hours: int = 24,
        permissions: str = "r",
    ) -> str:
        """
        Generate a SAS URL with time-limited access.

        Args:
            container_name: Container name
            blob_path: Path within container
            expiry_hours: Hours until SAS expires (default: 24)
            permissions: SAS permissions (r=read, w=write, d=delete)

        Returns:
            SAS URL
        """
        if not self.account_name or not self.account_key:
            raise StorageError("Account name and key required for SAS generation")

        # Build permissions
        sas_permissions = BlobSasPermissions(
            read='r' in permissions,
            write='w' in permissions,
            delete='d' in permissions,
        )

        # Generate SAS token
        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=container_name,
            blob_name=blob_path,
            account_key=self.account_key,
            permission=sas_permissions,
            expiry=datetime.utcnow() + timedelta(hours=expiry_hours),
        )

        blob_url = f"https://{self.account_name}.blob.core.windows.net/{container_name}/{blob_path}"
        return f"{blob_url}?{sas_token}"

    async def delete_blob(
        self,
        container_name: str,
        blob_path: str,
    ) -> bool:
        """
        Delete a blob from storage.

        Args:
            container_name: Container name
            blob_path: Path within container

        Returns:
            True if deleted, False if not found
        """
        try:
            container_client = self.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_path)

            blob_client.delete_blob()
            logger.info(f"Deleted blob: {container_name}/{blob_path}")
            return True

        except ResourceNotFoundError:
            logger.warning(f"Blob not found for deletion: {container_name}/{blob_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete blob {blob_path}: {e}")
            raise StorageError(f"Delete failed: {e}")

    async def list_blobs(
        self,
        container_name: str,
        prefix: Optional[str] = None,
        max_results: int = 100,
    ) -> list[dict[str, str]]:
        """
        List blobs in a container.

        Args:
            container_name: Container name
            prefix: Optional path prefix to filter by
            max_results: Maximum number of results

        Returns:
            List of blob info dicts with 'name', 'url', 'size', 'last_modified'
        """
        try:
            container_client = self.get_container_client(container_name)

            blobs = []
            for blob in container_client.list_blobs(name_starts_with=prefix):
                if len(blobs) >= max_results:
                    break
                blobs.append({
                    "name": blob.name,
                    "url": f"{container_client.url}/{blob.name}",
                    "size": blob.size,
                    "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                    "content_type": blob.content_settings.content_type if blob.content_settings else None,
                })

            return blobs

        except Exception as e:
            logger.error(f"Failed to list blobs: {e}")
            raise StorageError(f"List failed: {e}")

    async def blob_exists(
        self,
        container_name: str,
        blob_path: str,
    ) -> bool:
        """Check if a blob exists."""
        try:
            container_client = self.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_path)
            return blob_client.exists()
        except Exception:
            return False

    def build_asset_path(
        self,
        content_id: Union[str, UUID],
        asset_type: str,
        format: str = "png",
    ) -> str:
        """
        Build standard asset path per design.md §3.4.

        Path format: /{content_id}/{asset_type}.{format}

        Args:
            content_id: Content UUID
            asset_type: Asset type (thumbnail, preview, og_image)
            format: File format (png, jpg, webp)

        Returns:
            Blob path string
        """
        return f"{str(content_id)}/{asset_type}.{format}"


# Singleton instance
_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get the storage service singleton."""
    global _service
    if _service is None:
        _service = StorageService()
    return _service
