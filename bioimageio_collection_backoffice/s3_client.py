from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    BinaryIO,
    Iterator,
    List,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

from dotenv import load_dotenv
from loguru import logger
from minio import Minio, S3Error
from minio.commonconfig import CopySource
from minio.datatypes import Object
from minio.deleteobjects import DeleteObject
from pydantic import BaseModel

from .cache import SizedValueLRU

_ = load_dotenv()


M = TypeVar("M", bound=BaseModel)


@dataclass
class Client:
    """Convenience wrapper around a `Minio` S3 client"""

    host: str = os.environ["S3_HOST"]
    """S3 host"""
    bucket: str = os.environ["S3_BUCKET"]
    """S3 bucket"""
    prefix: str = os.environ["S3_FOLDER"]
    """S3 prefix ('root folder')"""
    access_key: str = field(default=os.environ["S3_ACCESS_KEY_ID"], repr=False)
    """S3 access key"""
    secret_key: str = field(default=os.environ["S3_SECRET_ACCESS_KEY"], repr=False)
    """S3 secret key"""
    max_bytes_cached: int = int(1e9)
    _client: Minio = field(init=False, compare=False, repr=False)
    _cache: Optional[SizedValueLRU[str, Optional[bytes]]] = field(
        init=False, compare=False, repr=False
    )

    def __post_init__(self):
        self.prefix = self.prefix.strip("/")
        if not self.prefix:
            raise ValueError("empty prefix not allowed")

        self._client = Minio(
            self.host,
            access_key=self.access_key,
            secret_key=self.secret_key,
        )
        found = self._bucket_exists(self.bucket)
        if not found:
            raise Exception("target bucket does not exist: {self.bucket}")

        self._cache = SizedValueLRU(maxsize=int(5e9))
        self.load_file = self._cache(self.load_file)
        logger.debug("Created S3-Client: {}", self)

    def _bucket_exists(self, bucket: str) -> bool:
        return self._client.bucket_exists(bucket)

    def put_and_cache(self, path: str, file: bytes):
        self.put(path, io.BytesIO(file), length=len(file))
        if self._cache is not None:
            self._cache.update((path,), file, only_if_cached=False)

    def put(
        self, path: str, file_object: Union[io.BytesIO, BinaryIO], length: Optional[int]
    ) -> None:
        """upload a file(like object)"""
        # For unknown length (ie without reading file into mem) give `part_size`
        if self._cache is not None:
            self._cache.pop((path,))

        part_size = 0
        if length is None:
            length = -1

        if length == -1:
            part_size = 10 * 1024 * 1024

        prefixed_path = f"{self.prefix}/{path}"
        _ = self._client.put_object(
            self.bucket,
            prefixed_path,
            file_object,
            length=length,
            part_size=part_size,
        )
        logger.info("Uploaded {}", self.get_file_url(path))

    def put_pydantic(self, path: str, obj: BaseModel):
        """convenience method to upload a json file from a pydantic model"""
        self.put_json_string(path, obj.model_dump_json(exclude_defaults=False))
        logger.debug("Uploaded {} containing {}", self.get_file_url(path), obj)

    def put_json(self, path: str, json_value: Any):
        """convenience method to upload a json file from a json serializable value"""
        json_str = json.dumps(json_value)
        self.put_json_string(path, json_str)
        logger.debug(
            "Uploaded {} containing {}",
            self.get_file_url(path),
            f"{json_str[:100]}{'...' if len(json_str)>100 else ''}",
        )

    def put_json_string(self, path: str, json_str: str):
        data = json_str.encode()
        self.put_and_cache(path, data)

    def get_file_urls(
        self,
        path: str = "",
    ) -> List[str]:
        """Checks an S3 'folder' for its list of files"""
        logger.debug("Getting file list using {}, at {}", self, path)
        prefix_folder = f"{self.prefix}/"
        path = f"{prefix_folder}{path}"
        objects = self._client.list_objects(self.bucket, prefix=path, recursive=True)
        file_urls: List[str] = []
        for obj in objects:
            if obj.is_dir or obj.object_name is None:
                continue
            assert obj.bucket_name == self.bucket
            assert obj.object_name.startswith(prefix_folder), obj.object_name
            url = self.get_file_url(obj.object_name[len(prefix_folder) :])
            file_urls.append(url)

        return file_urls

    # def get_presigned_file_urls(
    #     self,
    #     path: str = "",
    #     exclude_files: Sequence[str] = (),
    #     lifetime: timedelta = timedelta(hours=1),
    # ) -> List[str]:
    #     """Checks an S3 'folder' for its list of files"""
    #     logger.debug("Getting file list using {}, at {}", self, path)
    #     path = f"{self.prefix}/{path}"
    #     objects = self._client.list_objects(self.bucket, prefix=path, recursive=True)
    #     file_urls: List[str] = []
    #     for obj in objects:
    #         if obj.is_dir or obj.object_name is None:
    #             continue
    #         if Path(obj.object_name).name in exclude_files:
    #             continue
    #         # Option 1:
    #         url = self._client.get_presigned_url(
    #             "GET",
    #             obj.bucket_name,
    #             obj.object_name,
    #             expires=lifetime,
    #         )
    #         file_urls.append(url)
    #         # Option 2: Work with minio.datatypes.Object directly
    #     return file_urls

    def ls(
        self, path: str, only_folders: bool = False, only_files: bool = False
    ) -> Iterator[str]:
        """
        List folder contents, non-recursive, ala `ls` but no "." or ".."
        """
        path = f"{self.prefix}/{path}"
        logger.debug("Running ls at path: {}", path)
        objects = self._client.list_objects(self.bucket, prefix=path, recursive=False)
        for obj in objects:
            if (
                (only_files and obj.is_dir)
                or (only_folders and not obj.is_dir)
                or obj.object_name is None
            ):
                continue

            yield Path(obj.object_name).name

    def cp_dir(self, src: str, tgt: str):
        _ = self._cp_dir(src, tgt)

    def mv_dir(self, src: str, tgt: str, *, bypass_governance_mode: bool = False):
        """copy and delete all objects under `src` to `tgt`"""
        objects = self._cp_dir(src, tgt)
        self._rm_objs(objects, bypass_governance_mode=bypass_governance_mode)

    def rm_dir(self, prefix: str, *, bypass_governance_mode: bool = False):
        """remove all objects under `prefix`"""
        assert prefix == "" or prefix.endswith("/")
        objects = list(
            self._client.list_objects(
                self.bucket, f"{self.prefix}/{prefix}", recursive=True
            )
        )
        self._rm_objs(objects, bypass_governance_mode=bypass_governance_mode)

    def _cp_dir(self, src: str, tgt: str):
        assert src.endswith("/")
        assert tgt.endswith("/")
        src = f"{self.prefix}/{src}"
        tgt = f"{self.prefix}/{tgt}"
        objects = list(self._client.list_objects(self.bucket, src, recursive=True))
        # copy
        for obj in objects:
            assert obj.object_name is not None and obj.object_name.startswith(src)
            tgt_obj_name = f"{tgt}{obj.object_name[len(src) :]}"

            _ = self._client.copy_object(
                self.bucket,
                tgt_obj_name,
                CopySource(self.bucket, obj.object_name),
            )

        return objects

    def _rm_objs(
        self, objects: Sequence[Object], *, bypass_governance_mode: bool
    ) -> None:
        _ = list(
            self._client.remove_objects(
                self.bucket,
                (
                    DeleteObject(obj.object_name)
                    for obj in objects
                    if obj.object_name is not None
                ),
                bypass_governance_mode=bypass_governance_mode,
            )
        )

    def load_file(self, path: str, /) -> Optional[bytes]:
        """Load file

        Returns:
            file content or `None` if no object at `path` was found.
        """
        try:
            response = self._client.get_object(self.bucket, f"{self.prefix}/{path}")
            content = response.read()
        except Exception as e:
            if isinstance(e, S3Error) and e.code == "NoSuchKey":
                logger.info("Object {} not found with {}", path, self)
                content = None
            else:
                logger.critical("Failed to get object {} with {}", path, self)
                raise

        else:
            logger.debug("Loaded {}", path)

            try:
                response.close()
                response.release_conn()
            except Exception:
                pass

        return content

    def get_file_url(self, path: str) -> str:
        """Get the full URL to `path`"""
        return f"https://{self.host}/{self.bucket}/{self.prefix}/{path}"
