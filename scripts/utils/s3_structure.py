from typing import Any, Literal, TypedDict

LogCategory = Literal[
    "bioimageio.spec", "bioimageio.core", "ilastik", "deepimagej", "icy", "biapy"
]


class LogEntry(TypedDict):
    timestamp: str
    log: Any


Log = dict[LogCategory, list[LogEntry]]


class Message(TypedDict):
    author: str
    text: str
    time: str


StatusName = Literal["unknown", "staging"]


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
