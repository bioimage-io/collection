import json
from functools import lru_cache
from pathlib import Path

import httpx
from pydantic import HttpUrl

from .._settings import settings
from ..utils_plain import raise_for_status_discretely
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
            r = httpx.get(
                str(settings.collection_config), timeout=settings.http_timeout
            )
            raise_for_status_discretely(r)
            data = r.json()
        else:
            with Path(settings.collection_config).open(encoding="utf-8") as f:
                data = json.load(f)

        return cls.model_validate(data)
