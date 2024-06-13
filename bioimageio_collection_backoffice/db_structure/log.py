from __future__ import annotations

import collections.abc
from datetime import datetime
from typing import Any, ClassVar, Dict, Optional, Sequence, Union

from pydantic import Field

from .._settings import settings
from ..common import Node


class LogContent(Node, frozen=True, extra="ignore"):
    message: str = ""
    details: Any = None
    run_url: Optional[str] = settings.run_url


class LogEntry(Node, frozen=True, extra="ignore"):
    timestamp: datetime = Field(default_factory=datetime.now)
    """creation of log entry"""

    log: LogContent
    """log content"""


class Log(Node, frozen=True, extra="allow"):
    """`<concept_id>/<version>/log.json` contains a version specific log"""

    file_name: ClassVar[str] = "log.json"

    bioimageio_spec: Sequence[LogEntry] = Field(default_factory=list)
    bioimageio_core: Sequence[LogEntry] = Field(default_factory=list)
    collection: Sequence[LogEntry] = Field(default_factory=list)

    def get_updated(self, update: Log) -> Log:
        v: Union[Any, Sequence[Any]]
        data: Dict[str, Sequence[Any]] = {}
        for k, v in update:
            assert isinstance(v, collections.abc.Sequence)
            old = getattr(self, k, ())
            assert isinstance(old, collections.abc.Sequence)
            data[k] = list(old) + list(v)

        return Log.model_validate(data)
