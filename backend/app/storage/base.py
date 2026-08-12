from abc import ABC, abstractmethod


class MediaStorageError(Exception):
    pass


class MediaStorage(ABC):
    """Provider-agnostic object storage for uploaded photos, mirroring the
    NotificationGateway pattern (app/gateways/base.py): swappable per
    environment via MEDIA_STORAGE_BACKEND, one adapter per backend, no calling
    code touches the backend directly.

    Callers only ever get bytes back through media_asset_service, which
    re-checks visibility before returning anything -- storage_key is an opaque,
    unguessable identifier, never a resolvable public URL on its own."""

    @abstractmethod
    async def save(self, *, key: str, content: bytes, content_type: str) -> None: ...

    @abstractmethod
    async def read(self, *, key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, *, key: str) -> None: ...
