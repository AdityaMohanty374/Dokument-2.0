import boto3
from botocore.client import Config as BotoConfig

from config import settings

_s3 = boto3.client(
    "s3",
    endpoint_url=settings.R2_ENDPOINT_URL,
    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    config=BotoConfig(signature_version="s3v4"),
    region_name="auto",
)


def upload_pdf(local_path: str, storage_key: str):
    _s3.upload_file(local_path, settings.R2_BUCKET_NAME, storage_key)


def download_pdf(storage_key: str, local_path: str):
    _s3.download_file(settings.R2_BUCKET_NAME, storage_key, local_path)


def delete_pdf(storage_key: str):
    _s3.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=storage_key)


def presigned_url(storage_key: str, expires_in: int = 3600) -> str:
    return _s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.R2_BUCKET_NAME, "Key": storage_key},
        ExpiresIn=expires_in,
    )
