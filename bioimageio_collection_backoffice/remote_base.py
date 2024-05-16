from abc import abstractmethod
from dataclasses import dataclass
from typing import Type, TypeVar

from loguru import logger

from bioimageio_collection_backoffice.s3_client import Client

from .db_structure.chat import Chat
from .db_structure.log import Log
from .db_structure.partners import Partners
from .db_structure.versions import Versions

JsonFileT = TypeVar("JsonFileT", Versions, Log, Chat, Partners)


@dataclass
class RemoteBase:
    client: Client
    """Client to connect to remote storage"""

    @property
    @abstractmethod
    def folder(self) -> str: ...

    def _get_json(self, typ: Type[JsonFileT]) -> JsonFileT:
        path = self.folder + typ.file_name
        data = self.client.load_file(path)
        if data is None:
            return typ()
        else:
            return typ.model_validate_json(data)

    def _extend_json(self, extension: JsonFileT):
        path = self.folder + extension.file_name
        logger.info("Extending {} with {}", path, extension)
        current = self._get_json(extension.__class__)
        updated = current.get_updated(extension)
        self.client.put_pydantic(path, updated)
