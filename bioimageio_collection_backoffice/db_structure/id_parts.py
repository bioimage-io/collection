"""describes a file holding all parts to create resource ids"""

from functools import lru_cache
from typing import Mapping, Sequence

import requests
from pydantic import field_validator

from .._settings import settings
from ..requests_utils import raise_for_status_discretely
from .common import Node


class IdPartsEntry(Node, frozen=True):
    """parts to create resource ids for a specific resource type"""

    nouns: Mapping[str, str]
    adjectives: Sequence[str]

    @field_validator("adjectives", mode="after")
    def _sort_adjectives(cls, value: Sequence[str]):
        value = list(value)
        value.sort(
            key=len, reverse=True
        )  # such that longest adjective matches first during validation, e.g. 'easy-' vs 'easy-going-'
        return value

    def get_noun(self, resource_id: str):
        if not isinstance(resource_id, str):
            raise TypeError(f"invalid resource_id type: {type(resource_id)}")
        if not resource_id:
            raise ValueError("empty resource_id")

        for adj in self.adjectives:
            if resource_id.startswith(adj + "-"):
                break
        else:
            return None

        return resource_id[len(adj) + 1 :]

    def validate_resource_id(self, resource_id: str):
        noun = self.get_noun(resource_id)
        if noun is None:
            raise ValueError(
                f"{resource_id} does not start with a listed adjective"
                + " (or does not follow the pattern 'adjective-noun')"
            )

        if noun not in self.nouns:
            raise ValueError(
                f"{resource_id} does not end with a listed noun"
                + " (or does not follow the pattern 'adjective-noun')"
            )


class IdParts(Node, frozen=True):
    """parts to create resource ids"""

    model: IdPartsEntry
    dataset: IdPartsEntry
    notebook: IdPartsEntry

    @classmethod
    @lru_cache
    def load(cls):
        r = requests.get(settings.id_parts)
        raise_for_status_discretely(r)
        return cls.model_validate(r.json())

    def get_icon(self, resource_id: str):
        for parts in (self.model, self.dataset, self.notebook):
            noun = parts.get_noun(resource_id)
            if noun is not None and noun in parts.nouns:
                return parts.nouns[noun]

        return None
