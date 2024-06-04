from __future__ import annotations

from datetime import datetime
from typing import Literal, Mapping, Optional, Sequence, Union

from loguru import logger
from pydantic import HttpUrl, model_validator

from .collection_config.collection_json_template import (
    CollectionJsonTemplate,
    CollectionWebsiteConfigTemplate,
)
from .common import Node


class Author(Node, frozen=True):
    name: str
    affiliation: Optional[str] = None
    email: Optional[str] = None
    orcid: Optional[str] = None


class Badge(Node, frozen=True):
    icon: HttpUrl
    label: str
    url: HttpUrl


class TrainingData(Node, frozen=True):
    id: str


class CollectionEntry(Node, frozen=True):
    authors: Sequence[Author]
    badges: Sequence[Badge]
    concept_doi: Optional[str]
    covers: Sequence[HttpUrl]
    created: datetime
    description: str
    download_count: Union[Literal["?"], int]
    download_url: Optional[HttpUrl] = None
    icon: Union[HttpUrl, str, None] = None
    id: str
    license: Optional[str]
    links: Sequence[str]
    name: str
    nickname_icon: Optional[str]
    nickname: str
    rdf_sha256: str
    rdf_source: HttpUrl
    root_url: str
    tags: Sequence[str]
    training_data: Optional[TrainingData] = None
    type: Literal["application", "model", "notebook", "dataset"]
    versions: Sequence[str]
    """available versions of this resource. newest first"""
    dois: Sequence[Optional[str]]
    """version specific dois of the available versions. newest first"""


class CollectionWebsiteConfig(CollectionWebsiteConfigTemplate, frozen=True):
    n_resource_versions: Mapping[str, int]
    resource_types: Sequence[str]
    n_resources: Mapping[str, int]
    url_root: HttpUrl

    @model_validator(mode="after")
    def _validate_default_type(self):
        if self.default_type not in self.resource_types:
            logger.warning(
                "Missing `default_type={self.default_type}` in `resource_types={self.resource_types}`"
            )
        return self


class CollectionJson(CollectionJsonTemplate, frozen=True):
    collection: Sequence[CollectionEntry]
    config: CollectionWebsiteConfig
