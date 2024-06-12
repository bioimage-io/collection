from typing import Mapping

from .common import Node


class IdInfo(Node, frozen=True):
    source: str
    sha256: str


IdMap = Mapping[str, IdInfo]
