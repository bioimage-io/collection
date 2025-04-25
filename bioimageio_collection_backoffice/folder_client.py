from __future__ import annotations

import io
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    BinaryIO,
    Iterator,
    List,
    Optional,
    Union,
)

from loguru import logger
from pydantic import BaseModel

from .client_base import ClientBase
from .common import yaml


@dataclass
class FolderClient(ClientBase):
    base: Path
    """Path to local collection folder to use instead of S3 client."""

    def __post_init__(self):
        logger.debug("Using local collection folder: {}", self.base)
        if not self.base.exists():
            raise FileNotFoundError(
                f"local collection folder {self.base} does not exist"
            )

    def put_and_cache(self, path: str, file: bytes):
        self.put(path, io.BytesIO(file), length=len(file))

    def put(
        self, path: str, file_object: Union[io.BytesIO, BinaryIO], length: Optional[int]
    ) -> None:
        file_path = self.base / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        _ = file_path.write_bytes(file_object.read())
        logger.info("Updated {}", self.get_file_url(path))

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

    def get_file_urls(
        self,
        path: str = "",
    ) -> List[str]:
        return [
            self.get_file_url(p.as_posix())
            for p in self.base.glob(f"{self.base / path / "**/*"}") if p.is_file()
        ]

    def ls(
        self, path: str, only_folders: bool = False, only_files: bool = False
    ) -> Iterator[str]:
        """
        List folder contents, non-recursive, ala `ls` but no "." or ".."
        """

        if only_folders and only_files:
            raise ValueError("only one of `only_folders` or `only_files` can be True")

        list_all = not (only_folders or only_files)
        logger.debug("Running ls at path: {}", path)
        yield from (
            p.name
            for p in (self.base / path).glob("*")
            if list_all or only_folders and p.is_dir() or only_files and p.is_file()
        )

    def cp_dir(self, src: str, tgt: str):
        _ = shutil.copy(self.base / src, self.base / tgt)

    def mv_dir(self, src: str, tgt: str, *, bypass_governance_mode: bool = False):
        """move all objects under `src` to `tgt`"""
        _ = shutil.move(self.base / src, self.base / tgt)

    def rm_dir(self, path: str, *, bypass_governance_mode: bool = False):
        """remove all objects under `prefix`"""
        assert path == "" or path.endswith("/")
        shutil.rmtree(self.base / path)

    def rm(self, path: str):
        (self.base / path).unlink()

    def load_file(self, path: str, /) -> Optional[bytes]:
        """Load file

        Returns:
            file content or `None` if no object at `path` was found.
        """
        p = self.base / path
        return p.read_bytes() if p.exists() else None

    def get_file_url(self, path: str) -> str:
        """Get the full URL to `path`"""
        return f"file://{(self.base / path).resolve().as_posix()}"
