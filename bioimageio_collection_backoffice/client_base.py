from __future__ import annotations

import io
import json
from abc import ABC
from dataclasses import dataclass
from typing import (
    Any,
    BinaryIO,
    Iterator,
    List,
    Optional,
    Union,
)

from pydantic import BaseModel

from .common import yaml


@dataclass
class ClientBase(ABC):
    """Convenience wrapper around a `Minio` S3 client"""

    def put_and_cache(self, path: str, file: bytes) -> None:
        raise NotImplementedError

    def put(
        self, path: str, file_object: Union[io.BytesIO, BinaryIO], length: Optional[int]
    ) -> None:
        raise NotImplementedError

    def _put_impl(
        self, path: str, file_object: Union[io.BytesIO, BinaryIO], length: Optional[int]
    ) -> None:
        """upload a file(like object)"""
        raise NotImplementedError

    def get_file_urls(
        self,
        path: str = "",
    ) -> List[str]:
        raise NotImplementedError

    def put_pydantic(self, path: str, obj: BaseModel):
        """upload a json file from a pydantic model"""
        self.put_json_string(path, obj.model_dump_json(exclude_defaults=False))

    def put_json(
        self, path: str, json_value: Any  # TODO: type json_value as JsonValue
    ):
        """upload a json file from a json serializable value"""
        json_str = json.dumps(json_value)
        self.put_json_string(path, json_str)

    def put_yaml(self, yaml_value: Any, path: str):
        """upload a yaml file from a yaml serializable value"""
        stream = io.StringIO()
        yaml.dump(yaml_value, stream)
        data = stream.getvalue().encode()
        self.put(
            path,
            io.BytesIO(data),
            length=len(data),
        )

    def put_json_string(self, path: str, json_str: str):
        data = json_str.encode()
        self.put_and_cache(path, data)

    def ls(
        self, path: str, only_folders: bool = False, only_files: bool = False
    ) -> Iterator[str]:
        """
        List folder contents, non-recursive, ala `ls` but no "." or ".."
        """
        raise NotImplementedError

    def cp_dir(self, src: str, tgt: str) -> None:
        raise NotImplementedError

    def mv_dir(
        self, src: str, tgt: str, *, bypass_governance_mode: bool = False
    ) -> None:
        """move all objects under `src` to `tgt`"""
        raise NotImplementedError

    def rm_dir(self, path: str, *, bypass_governance_mode: bool = False) -> None:
        """remove all objects under `path`"""
        raise NotImplementedError

    def rm(self, path: str) -> None:
        raise NotImplementedError

    def load_file(self, path: str, /) -> Optional[bytes]:
        """Load file

        Returns:
            file content or `None` if no object at `path` was found.
        """
        raise NotImplementedError

    def get_file_url(self, path: str) -> str:
        """Get the full URL to `path`"""
        raise NotImplementedError
