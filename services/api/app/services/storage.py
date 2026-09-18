from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import quote
import boto3
from botocore.client import Config
from ..config import get_settings


class StorageProvider(ABC):
    @abstractmethod
    def put_bytes(self, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    def get_bytes(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def signed_get_url(self, key: str, expires_seconds: int = 300) -> str: ...

    @abstractmethod
    def healthcheck(self) -> None: ...


class LocalStorage(StorageProvider):
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if self.root not in candidate.parents and candidate != self.root:
            raise ValueError("Invalid storage key")
        return candidate

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            return

    def signed_get_url(self, key: str, expires_seconds: int = 300) -> str:
        return f"/api/v1/files/local/{quote(key)}"

    def healthcheck(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not os.access(self.root, os.R_OK | os.W_OK):
            raise RuntimeError("Local storage is not readable and writable")


class S3Storage(StorageProvider):
    def __init__(self):
        s = get_settings()
        self.bucket = s.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint_url,
            aws_access_key_id=s.s3_access_key,
            aws_secret_access_key=s.s3_secret_key,
            region_name=s.s3_region,
            config=Config(signature_version="s3v4"),
        )

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get_bytes(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def signed_get_url(self, key: str, expires_seconds: int = 300) -> str:
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_seconds
        )

    def healthcheck(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)


def get_storage() -> StorageProvider:
    s = get_settings()
    if s.storage_backend.lower() == "s3":
        return S3Storage()
    return LocalStorage(s.storage_path)
