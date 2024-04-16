from typing import Mapping, Sequence

import requests

from bioimageio_collection_backoffice._settings import settings
from bioimageio_collection_backoffice.db_structure.common import Node
from bioimageio_collection_backoffice.requests_utils import raise_for_status_discretely


class IdPartsEntry(Node, frozen=True):
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
