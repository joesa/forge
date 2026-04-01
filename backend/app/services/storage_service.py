"""
Cloudflare R2 storage service — S3-compatible via boto3.

R2 is Cloudflare's object storage with an S3-compatible API.
We use boto3 with a custom endpoint URL pointed at the R2 account.

All public functions are async (wrapping synchronous boto3 calls via
asyncio.to_thread) so they integrate cleanly with FastAPI's async stack.
"""

import asyncio
from typing import Any

import boto3
import structlog
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import settings

logger = structlog.get_logger(__name__)


def _build_client() -> Any:
    """Create a boto3 S3 client configured for Cloudflare R2."""
    endpoint_url = (
        f"https://{settings.CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com"
    )
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=BotoConfig(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
        region_name="auto",
    )


# Module-level lazy singleton
_client: Any = None


def _get_client() -> Any:
    global _client
    if _client is None:
        _client = _build_client()
    return _client


# ── Public API ───────────────────────────────────────────────────────


async def upload_file(key: str, content: bytes, content_type: str) -> str:
    """
    Upload a file to R2.

    Parameters
    ----------
    key : str
        Object key (e.g. ``projects/{project_id}/src/index.tsx``).
    content : bytes
        Raw file content.
    content_type : str
        MIME type (e.g. ``text/plain``, ``application/json``).

    Returns
    -------
    str
        The object key (can be used to build URLs or fetch later).
    """
    client = _get_client()
    try:
        await asyncio.to_thread(
            client.put_object,
            Bucket=settings.R2_BUCKET_NAME,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        logger.info("r2_upload_ok", key=key, size=len(content))
        return key
    except ClientError as exc:
        logger.error("r2_upload_failed", key=key, error=str(exc))
        raise


async def download_file(key: str) -> bytes:
    """
    Download a file from R2.

    Returns
    -------
    bytes
        The raw file content.

    Raises
    ------
    ClientError
        If the key does not exist or R2 is unreachable.
    """
    client = _get_client()
    try:
        response = await asyncio.to_thread(
            client.get_object,
            Bucket=settings.R2_BUCKET_NAME,
            Key=key,
        )
        body = await asyncio.to_thread(response["Body"].read)
        logger.info("r2_download_ok", key=key, size=len(body))
        return body
    except ClientError as exc:
        logger.error("r2_download_failed", key=key, error=str(exc))
        raise


async def delete_file(key: str) -> None:
    """
    Delete a single file from R2.

    Silently succeeds if the key does not exist (S3 semantics).
    """
    client = _get_client()
    try:
        await asyncio.to_thread(
            client.delete_object,
            Bucket=settings.R2_BUCKET_NAME,
            Key=key,
        )
        logger.info("r2_delete_ok", key=key)
    except ClientError as exc:
        logger.error("r2_delete_failed", key=key, error=str(exc))
        raise


async def list_files(prefix: str) -> list[str]:
    """
    List all object keys under *prefix*.

    Parameters
    ----------
    prefix : str
        Key prefix (e.g. ``projects/{project_id}/``).

    Returns
    -------
    list[str]
        Sorted list of matching object keys.
    """
    client = _get_client()
    keys: list[str] = []

    try:
        paginator = client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(
            Bucket=settings.R2_BUCKET_NAME,
            Prefix=prefix,
        )

        # Paginator is synchronous — iterate in thread
        def _collect_keys() -> list[str]:
            result: list[str] = []
            for page in page_iterator:
                for obj in page.get("Contents", []):
                    result.append(obj["Key"])
            return sorted(result)

        keys = await asyncio.to_thread(_collect_keys)
        logger.info("r2_list_ok", prefix=prefix, count=len(keys))
    except ClientError as exc:
        logger.error("r2_list_failed", prefix=prefix, error=str(exc))
        raise

    return keys


async def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    """
    Generate a presigned URL for temporary direct access to a file.

    Parameters
    ----------
    key : str
        Object key.
    expires_in : int
        URL lifetime in seconds (default 1 hour).

    Returns
    -------
    str
        The presigned URL.
    """
    client = _get_client()
    try:
        url: str = await asyncio.to_thread(
            client.generate_presigned_url,
            "get_object",
            Params={
                "Bucket": settings.R2_BUCKET_NAME,
                "Key": key,
            },
            ExpiresIn=expires_in,
        )
        logger.info("r2_presigned_url_ok", key=key, expires_in=expires_in)
        return url
    except ClientError as exc:
        logger.error("r2_presigned_url_failed", key=key, error=str(exc))
        raise


async def delete_prefix(prefix: str) -> int:
    """
    Delete ALL objects under *prefix* (recursive).

    Returns the number of objects deleted.
    """
    keys = await list_files(prefix)
    if not keys:
        return 0

    client = _get_client()
    # S3 delete_objects supports up to 1000 keys per call
    deleted = 0
    for i in range(0, len(keys), 1000):
        batch = keys[i : i + 1000]
        delete_spec = {"Objects": [{"Key": k} for k in batch], "Quiet": True}
        try:
            await asyncio.to_thread(
                client.delete_objects,
                Bucket=settings.R2_BUCKET_NAME,
                Delete=delete_spec,
            )
            deleted += len(batch)
        except ClientError as exc:
            logger.error(
                "r2_delete_prefix_failed", prefix=prefix, error=str(exc)
            )
            raise

    logger.info("r2_delete_prefix_ok", prefix=prefix, deleted=deleted)
    return deleted
