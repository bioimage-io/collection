from __future__ import annotations

import collections.abc
from datetime import datetime
from typing import Any, ClassVar, Dict, Optional, Sequence, Union

from bioimageio.spec import ValidationSummary
from pydantic import Field

from .common import Node


class _LogEntryBase(Node, frozen=True, extra="ignore"):
    timestamp: datetime = datetime.now()
    """creation of log entry"""
    log: Any
    """log content"""


class CollectionLogEntry(Node, frozen=True, extra="ignore"):
    message: str = ""
    details: Any = None


class CollectionLog(_LogEntryBase, frozen=True):
    log: Union[str, CollectionLogEntry]


class CollectionCiLogEntry(Node, frozen=True, extra="ignore"):
    message: str = ""
    run_url: str


class CollectionCiLog(_LogEntryBase, frozen=True):
    log: CollectionCiLogEntry


class BioimageioLogEntry(Node, frozen=True, extra="ignore"):
    message: str = ""
    details: Optional[ValidationSummary] = None


class BioimageioLog(_LogEntryBase, frozen=True, extra="ignore"):
    log: BioimageioLogEntry


class Log(Node, frozen=True, extra="allow"):
    """`<id>/<version>/log.json` contains a version specific log"""

    file_name: ClassVar[str] = "log.json"

    bioimageio_spec: Sequence[BioimageioLog] = Field(default_factory=list)
    bioimageio_core: Sequence[BioimageioLog] = Field(default_factory=list)
    collection: Sequence[CollectionLog] = Field(default_factory=list)
    collection_ci: Sequence[CollectionCiLog] = Field(default_factory=list)

    def get_updated(self, update: Log):
        v: Union[Any, Sequence[Any]]
        data: Dict[str, Sequence[Any]] = {}
        for k, v in update:
            assert isinstance(v, collections.abc.Sequence)
            old = getattr(self, k, ())
            assert isinstance(old, collections.abc.Sequence)
            data[k] = list(old) + list(v)

        return Log.model_validate(data)
