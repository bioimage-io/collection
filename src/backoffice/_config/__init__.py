import json
from functools import lru_cache
from pathlib import Path

import requests
from pydantic import HttpUrl

from .._requests_utils import raise_for_status_discretely
from .._settings import settings
from .common import ConfigNode
from .id_parts import IdParts
from .reviewers import Reviewers


class CollectionConfig(ConfigNode, frozen=True):
    id_parts: IdParts
    reviewers: Reviewers

    @classmethod
    @lru_cache
    def load(cls):
        if isinstance(settings.collection_config, HttpUrl):
            r = requests.get(str(settings.collection_config))
            raise_for_status_discretely(r)
            data = r.json()
        else:
            with Path(settings.collection_config).open(encoding="utf-8") as f:
                data = json.load(f)

        return cls.model_validate(data)
