from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Optional, Sequence

from pydantic import Field

from .._settings import settings
from ..common import Node


class LogEntry(Node, frozen=True, extra="ignore"):
    message: str = ""
    """log message"""

    details: Any = None
    """log details"""

    timestamp: datetime = Field(default_factory=datetime.now)
    """creation of log entry"""

    run_url: Optional[str] = settings.run_url
    """gh action run url"""


class Log(Node, frozen=True, extra="ignore"):
    """`<concept_id>/<version>/log.json` contains a version specific log"""

    file_name: ClassVar[str] = "log.json"

    log_version: str = "0.1.0"
    entries: Sequence[LogEntry] = Field(default_factory=list)

    def get_updated(self, update: Log) -> Log:
        if update.log_version != self.log_version:
            return update

        return Log(
            log_version=update.log_version,
            entries=list(self.entries) + list(update.entries),
        )
