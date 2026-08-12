import asyncio
from pathlib import Path

from app.storage.base import MediaStorage, MediaStorageError


class LocalDiskStorage(MediaStorage):
    """Dev/local backend: writes under a single root directory (mounted as a
    volume in docker-compose so uploads survive container restarts). Not
    exposed via a static-files mount -- always read back through
    media_asset_service so access control applies uniformly with the S3
    backend, which never allows anonymous reads either."""

    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents and path != self.root.resolve():
            raise MediaStorageError(f"Refusing to access path outside storage root: {key}")
        return path

    async def save(self, *, key: str, content: bytes, content_type: str) -> None:
        path = self._resolve(key)
        await asyncio.to_thread(self._write, path, content)

    def _write(self, path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    async def read(self, *, key: str) -> bytes:
        path = self._resolve(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as exc:
            raise MediaStorageError(f"No such media object: {key}") from exc

    async def delete(self, *, key: str) -> None:
        path = self._resolve(key)
        await asyncio.to_thread(path.unlink, True)
