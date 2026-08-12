from functools import lru_cache

from app.core.config import get_settings
from app.storage.base import MediaStorage
from app.storage.local_storage import LocalDiskStorage


@lru_cache
def get_storage() -> MediaStorage:
    settings = get_settings()
    if settings.media_storage_backend == "s3":
        from app.storage.s3_storage import S3Storage

        return S3Storage(
            bucket=settings.media_s3_bucket,
            region=settings.media_s3_region,
            access_key_id=settings.media_s3_access_key_id,
            secret_access_key=settings.media_s3_secret_access_key,
            endpoint_url=settings.media_s3_endpoint_url,
        )
    return LocalDiskStorage(settings.media_local_path)
