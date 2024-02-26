"""
Descriptions of
- `<id>/<version>/log.json` → `Log`
- `<id>/<version>/details.json` → `Details`
"""

from typing import Any, Literal, TypedDict

LogCategory = Literal[
    "bioimageio.spec", "bioimageio.core", "ilastik", "deepimagej", "icy", "biapy"
]


class LogEntry(TypedDict):
    timestamp: str
    """creation of log entry"""
    log: Any
    """log content"""


Log = dict[LogCategory, list[LogEntry]]
"""version specific log at `<id>/<version>/log.json`"""


class Message(TypedDict):
    author: str
    text: str
    time: str
    """time in ISO 8601"""


StatusName = Literal["unknown", "staging", "testing", "awaiting review"]


class Status(TypedDict):
    name: StatusName
    description: str
    step: int
    num_steps: int


class Details(TypedDict):
    """version specific details at `<id>/<version>/details.json`"""

    messages: list[Message]
    """messages"""
    status: Status
