import asyncio

from app.storage.base import MediaStorage, MediaStorageError


class S3Storage(MediaStorage):
    """Production backend: S3 / S3-compatible object storage (works against
    real AWS S3 or an S3-compatible endpoint like MinIO/DigitalOcean Spaces via
    media_s3_endpoint_url). boto3 is sync, so calls run in a thread pool to fit
    the async MediaStorage interface -- same adapter pattern used for Celery
    tasks calling the async gateway (see app/workers/tasks.py).

    Unverified against real S3 in this environment (no AWS credentials
    available to test with); implemented directly against boto3's documented
    API. Bucket should be private with no public-read policy -- all access
    goes through media_asset_service's visibility checks, never a raw S3 URL."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str | None = None,
    ):
        import boto3

        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
            endpoint_url=endpoint_url or None,
        )

    async def save(self, *, key: str, content: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )

    async def read(self, *, key: str) -> bytes:
        from botocore.exceptions import ClientError

        try:
            response = await asyncio.to_thread(self._client.get_object, Bucket=self.bucket, Key=key)
        except ClientError as exc:
            raise MediaStorageError(f"No such media object: {key}") from exc
        return await asyncio.to_thread(response["Body"].read)

    async def delete(self, *, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self.bucket, Key=key)
