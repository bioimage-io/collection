import traceback
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, Type, TypeVar, Union

from loguru import logger

from .db_structure.chat import Chat
from .db_structure.log import Log, LogEntry
from .db_structure.reserved import Reserved
from .db_structure.version_info import DraftInfo, RecordInfo
from .s3_client import Client

JsonFileT = TypeVar("JsonFileT", DraftInfo, RecordInfo, Log, Chat, Reserved)


@dataclass
class RemoteBase:
    client: Client
    """Client to connect to remote storage"""

    @property
    @abstractmethod
    def id(self) -> str: ...

    @property
    def folder(self) -> str:
        """The S3 (sub)prefix of this resource"""
        return f"{self.id}/"

    def _get_json(self, typ: Type[JsonFileT]) -> JsonFileT:
        path = self.folder + typ.file_name
        data = self.client.load_file(path)
        if data is None:
            return typ()
        else:
            return typ.model_validate_json(data)

    def _update_json(self, update: JsonFileT):
        path = self.folder + update.file_name
        logger.info("Extending {} with {}", path, update)
        current = self._get_json(update.__class__)
        updated = current.get_updated(update)
        self.client.put_pydantic(path, updated)

    @property
    def log(self) -> Log:
        return self._get_json(Log)

    def log_message(self, message: str, details: Optional[Any] = None):
        self._update_json(Log(entries=[LogEntry(message=message, details=details)]))

    def log_error(self, error: Union[Exception, str], details: Optional[Any] = None):
        if isinstance(error, Exception):
            error = str(error)

        if details is None:
            details = {}

        if isinstance(details, dict) and "traceback" not in details:
            details["traceback"] = traceback.format_stack()

        self._update_json(Log(entries=[LogEntry(message=error, details=details)]))
