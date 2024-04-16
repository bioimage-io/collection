"""describes a file holding all parts to create resource ids"""

import requests

from .._settings import settings
from ..requests_utils import raise_for_status_discretely
from .common import Node


class IdPartsEntry(Node, frozen=True):
    """parts to create resource ids for a specific resource type"""
    nouns: Mapping[str, str]
    adjectives: Sequence[str]


class IdParts(Node, frozen=True):
    model: IdPartsEntry
    dataset: IdPartsEntry
    notebook: IdPartsEntry

    @classmethod
    def load(cls):
        r = requests.get(settings.id_parts)
        raise_for_status_discretely(r)
        return cls.model_validate(r.json())
