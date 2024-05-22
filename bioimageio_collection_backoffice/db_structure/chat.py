"""`<concept_id>/<version>/chat.json` keeps a record of version specific comments"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Sequence

from pydantic import Field

from ..common import Node


class Message(Node, frozen=True):
    author: str
    text: str
    timestamp: datetime = datetime.now()


class Chat(Node, frozen=True):
    """`<concept_id>/<version>/chat.json` keeps a record of version specific comments"""

    file_name: ClassVar[str] = "chat.json"

    messages: Sequence[Message] = Field(default_factory=list)
    """messages"""

    def get_updated(self, update: Chat) -> Chat:
        assert set(self.model_fields) == {"messages"}, set(self.model_fields)
        return Chat(messages=list(self.messages) + list(update.messages))
