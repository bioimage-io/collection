from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Sequence

from pydantic import Field

from .common import Node


class Message(Node, frozen=True):
    author: str
    text: str
    timestamp: datetime


class MessageWithDefaults(Message, frozen=True):
    timestamp: datetime = datetime.now()


class Chat(Node, frozen=True):
    """`<id>/<version>/chat.json` keeps a record of version specific comments"""

    file_name: ClassVar[str] = "chat.json"

    messages: Sequence[Message]
    """messages"""

    def get_updated(self, update: Chat) -> Chat:
        assert set(self.model_fields) == {"messages"}, set(self.model_fields)
        return Chat(messages=list(self.messages) + list(update.messages))

    @staticmethod
    def get_class_with_defaults():
        return ChatWithDefaults


class ChatWithDefaults(Chat, frozen=True):
    messages: Sequence[Message] = Field(default_factory=list)
