from __future__ import annotations

import collections.abc
from datetime import datetime
from typing import Any, ClassVar, Dict, Sequence, Union

from bioimageio.spec import ValidationSummary
from pydantic import Field

from .common import Node


class _LogEntryBase(Node, frozen=True):
    timestamp: datetime
    """creation of log entry"""
    log: Any
    """log content"""


class _LogEntryBaseWithDefaults(_LogEntryBase, frozen=True):
    timestamp: datetime = datetime.now()
    """creation of log entry"""


class CollectionLog(_LogEntryBase, frozen=True):
    log: str


class CollectionLogWithDefaults(_LogEntryBaseWithDefaults, CollectionLog, frozen=True):
    pass


class BioimageioLog(_LogEntryBase, frozen=True):
    log: ValidationSummary


class BioimageioLogWithDefaults(_LogEntryBaseWithDefaults, BioimageioLog, frozen=True):
    pass


class Log(Node, frozen=True, extra="allow"):
    """`<id>/<version>/log.json` contains a version specific log"""

    file_name: ClassVar[str] = "log.json"

    bioimageio_spec: Sequence[BioimageioLog]
    bioimageio_core: Sequence[BioimageioLog]
    collection: Sequence[CollectionLog]

    def get_updated(self, update: Log):
        v: Union[Any, Sequence[Any]]
        data: Dict[str, Sequence[Any]] = {}
        for k, v in update:
            assert isinstance(v, collections.abc.Sequence)
            old = getattr(self, k, ())
            assert isinstance(old, collections.abc.Sequence)
            data[k] = list(old) + list(v)

        return Log.model_validate(data)

    @staticmethod
    def get_class_with_defaults():
        return LogWithDefaults


class LogWithDefaults(Log, frozen=True, extra="allow"):
    """`<id>/<version>/log.json` contains a version specific log"""

    bioimageio_spec: Sequence[BioimageioLogWithDefaults] = Field(default_factory=list)
    bioimageio_core: Sequence[BioimageioLogWithDefaults] = Field(default_factory=list)
    collection: Sequence[CollectionLogWithDefaults] = Field(default_factory=list)
