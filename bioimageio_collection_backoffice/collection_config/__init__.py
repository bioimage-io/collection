import json
from functools import lru_cache
from pathlib import Path

import requests

from ..common import Node
from ..requests_utils import raise_for_status_discretely
from ..settings import settings
from .collection_json_template import CollectionJsonTemplate
from .id_parts import IdParts
from .reviewers import Reviewers


class CollectionConfig(Node, frozen=True):
    collection_template: CollectionJsonTemplate
    id_parts: IdParts
    reviewers: Reviewers

    @property
    def partners(self):
        return self.collection_template.config.partners

    @classmethod
    @lru_cache
    def load(cls):
        if settings.collection_config.startswith("http"):
            r = requests.get(settings.collection_config)
            raise_for_status_discretely(r)
            data = r.json()
        else:
            with Path(settings.collection_config).open(encoding="utf-8") as f:
                data = json.load(f)

        return cls.model_validate(data)
