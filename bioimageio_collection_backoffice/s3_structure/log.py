from __future__ import annotations

from datetime import datetime
from typing import Any, List

from bioimageio.spec import ValidationSummary
from pydantic import Field

from .common import Node


class _LogEntryBase(Node):
    timestamp: datetime = datetime.now()
    """creation of log entry"""
    log: Any
    """log content"""


class BioimageioLog(_LogEntryBase):
    log: ValidationSummary


<<<<<<< ours
=======
class Logs(Node):
>>>>>>> theirs
class Log(Node, extra="allow"):
    """`<id>/<version>/log.json` contains a version specific log"""

    bioimageio_spec: List[BioimageioLog] = Field(default_factory=list)
    bioimageio_core: List[BioimageioLog] = Field(default_factory=list)

    def extend(self, other: Log):
        v: List[Any]
        for k, v in other:
            assert isinstance(v, list)
            logs = getattr(self, k, [])
            assert isinstance(logs, list)
            logs.extend(v)
