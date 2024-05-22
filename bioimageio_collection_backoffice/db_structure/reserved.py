"""`<concept_id>/<version>/reserved.json` allows to reserve a concept id"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from pydantic import Field

from ..common import Node


class Reserved(Node, frozen=True):
    """`<concept_id>/<version>/reserved.json` allows to reserve a concept id"""

    file_name: ClassVar[str] = "reserved.json"

    timestamp: datetime = Field(default_factory=datetime.now)

    def get_updated(self, update: Reserved) -> Reserved:
        return update
