from __future__ import annotations

from datetime import datetime
from typing import Any

from bioimageio.spec import ValidationSummary
from pydantic import Field

from backoffice.s3_structure.common import Node


class _LogEntryBase(Node):
    timestamp: datetime = datetime.now()
    """creation of log entry"""
    log: Any
    """log content"""


class BioimageioLog(_LogEntryBase):
    log: ValidationSummary


class Logs(Node):
    """`<id>/<version>/log.json` contains a version specific log"""

    bioimageio_spec: list[BioimageioLog] = Field(default_factory=list)
    bioimageio_core: list[BioimageioLog] = Field(default_factory=list)

    def extend(self, other: Logs):
        for k, v in other:
            assert isinstance(v, list)
            logs = getattr(self, k)
            assert isinstance(logs, list)
            logs.extend(v)
