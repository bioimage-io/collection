from __future__ import annotations

from datetime import datetime

from pydantic import Field

from backoffice.s3_structure.common import Node


class Message(Node):
    author: str
    text: str
    timestamp: datetime = datetime.now()


class Chat(Node):
    """`<id>/<version>/chat.json` keeps a record of version specific comments"""

    messages: list[Message] = Field(default_factory=list)
    """messages"""

    def extend(self, other: Chat):
        assert set(self.model_fields) == {"messages"}, set(self.model_fields)
        self.messages.extend(other.messages)
