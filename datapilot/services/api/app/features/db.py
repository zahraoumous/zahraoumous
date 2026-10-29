from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url.get_secret_value(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=15000"},
    )


def get_s3():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        region_name=settings.s3_region,
        config=Config(
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 2},
            s3={"addressing_style": "path"},
        ),
    )


def ensure_bucket(client) -> None:
    settings = get_settings()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        args: dict[str, Any] = {"Bucket": settings.s3_bucket}
        if settings.s3_region != "us-east-1":
            args["CreateBucketConfiguration"] = {"LocationConstraint": settings.s3_region}
        try:
            client.create_bucket(**args)
        except ClientError as create_error:
            if create_error.response.get("Error", {}).get("Code") != "BucketAlreadyOwnedByYou":
                raise
