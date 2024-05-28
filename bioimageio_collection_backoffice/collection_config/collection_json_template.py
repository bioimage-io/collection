"""a summary of all collection records"""

from __future__ import annotations

from typing import Any, Literal, Optional, Sequence

from bioimageio.spec.generic.v0_3 import Author, CiteEntry, LicenseId, Version
from pydantic import HttpUrl

from ..common import Node


class Partner(Node, frozen=True):
    background_image: str
    default_type: str
    explore_button_text: str
    id: str
    logo: str
    resource_types: Sequence[str]
    splash_feature_list: Sequence[str]
    splash_subtitle: Optional[str]
    splash_title: str


class CollectionWebsiteConfigTemplate(Node, frozen=True):
    background_image: str
    default_type: str
    explore_button_text: str
    partners: Sequence[Partner]
    splash_feature_list: Sequence[str]
    splash_subtitle: str
    splash_title: str


class CollectionJsonTemplate(Node, frozen=True):
    """a summary of all collection records"""

    authors: Sequence[Author]
    cite: Sequence[CiteEntry]
    config: CollectionWebsiteConfigTemplate
    description: str
    documentation: HttpUrl
    format_version: Version
    git_repo: HttpUrl
    icon: HttpUrl
    license: LicenseId
    name: str
    tags: Sequence[str]
    type: Literal["collection"]
    version: Version

    collection: Sequence[Any]
