from __future__ import annotations

import collections.abc
from datetime import datetime
from typing import Any, ClassVar, Dict, Optional, Sequence, Union

from bioimageio.spec import ValidationSummary
from pydantic import Field

from .._settings import settings
from ..common import Node


class _LogEntryBase(Node, frozen=True, extra="ignore"):
    timestamp: datetime = Field(default_factory=datetime.now)
    """creation of log entry"""
    log: Any
    """log content"""


class CollectionLogEntry(Node, frozen=True, extra="ignore"):
    message: str = ""
    details: Any = None
    run_url: Optional[str] = settings.run_url


class CollectionLog(_LogEntryBase, frozen=True):
    log: Union[str, CollectionLogEntry]


class BioimageioLogEntry(Node, frozen=True, extra="ignore"):
    message: str = ""
    details: Optional[ValidationSummary] = None


class BioimageioLog(_LogEntryBase, frozen=True, extra="ignore"):
    log: BioimageioLogEntry


class Log(Node, frozen=True, extra="allow"):
    """`<concept_id>/<version>/log.json` contains a version specific log"""

    file_name: ClassVar[str] = "log.json"

    bioimageio_spec: Sequence[BioimageioLog] = Field(default_factory=list)
    bioimageio_core: Sequence[BioimageioLog] = Field(default_factory=list)
    collection: Sequence[CollectionLog] = Field(default_factory=list)

    def get_updated(self, update: Log) -> Log:
        v: Union[Any, Sequence[Any]]
        data: Dict[str, Sequence[Any]] = {}
        for k, v in update:
            assert isinstance(v, collections.abc.Sequence)
            old = getattr(self, k, ())
            assert isinstance(old, collections.abc.Sequence)
            data[k] = list(old) + list(v)

        return Log.model_validate(data)
