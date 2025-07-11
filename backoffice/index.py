import hashlib
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

import httpx
from loguru import logger
from pydantic import BaseModel

from backoffice._settings import settings
from backoffice.utils import get_local_rdf_path, get_report_path


class Node(BaseModel, frozen=True, extra="ignore"):
    pass


class ItemVersion(Node, frozen=True):
    version: str
    comment: Optional[str]
    created_at: datetime


class IndexItemVersion(ItemVersion, frozen=True):
    source: str
    sha256: str


class Item(Node, frozen=True):
    id: str
    versions: Sequence[ItemVersion]
    type: str


class IndexItem(Item, frozen=True):
    versions: Sequence[IndexItemVersion]


class Response(Node, frozen=True):
    """Response from Hypha list endpoint"""

    items: list[Item]
    total: int
    offset: int
    limit: int


class Index(Node, frozen=True):
    items: list[IndexItem]
    total: int
    count_per_type: dict[str, int]


def create_index() -> Index:
    """Index the bioimage.io collection"""

    index_path = Path("index.json")
    if index_path.exists():
        logger.info("loading index from {}", index_path)
        index = Index.model_validate_json(index_path.read_text(encoding="utf-8"))
    else:
        url = f"{settings.hypha_base_url}/public/services/artifact-manager/list"

        def request(offset: int) -> Response:
            r = httpx.get(
                url,
                params=dict(
                    parent_id="bioimage-io/bioimage.io",
                    offset=offset,
                    pagination=True,
                    limit=10000,
                ),
                headers=settings.get_hypha_headers(),
            )
            try:
                _ = r.raise_for_status()
            except Exception as e:
                logger.error(r.json())
                raise e
            else:
                return Response.model_validate_json(r.content)

        items: list[Item] = []
        for page in range(100):
            response = request(len(items))
            logger.info("Page {}: {} entries", page, len(response.items))
            items.extend(response.items)
            if response.total <= len(items):
                if response.total != len(items):
                    logger.error(
                        "response.total {} != len(items) {}", response.total, len(items)
                    )
                break

        index_items: list[IndexItem] = []
        for item in items:
            domain, item_id_wo_domain = item.id.split("/", 1)
            versions: list[IndexItemVersion] = []
            for v in item.versions:
                url = f"{settings.hypha_base_url}/{domain}/artifacts/{item_id_wo_domain}/files/rdf.yaml?version={v.version}"
                sha256 = _initialize_report_directory(item, v, url)
                versions.append(
                    IndexItemVersion(
                        version=v.version,
                        comment=v.comment,
                        created_at=v.created_at,
                        source=url,
                        sha256=sha256,
                    )
                )
            index_items.append(IndexItem(id=item.id, versions=versions, type=item.type))

        count_per_type = defaultdict[str, int](int)
        for item in index_items:
            count_per_type[item.type] += 1

        index = Index(
            items=index_items,
            total=len(index_items),
            count_per_type=dict(count_per_type),
        )

        _ = index_path.write_text(index.model_dump_json(indent=4), encoding="utf-8")
        logger.info("saved index to {}", index_path)

    logger.info(
        "loaded index with {} ids and {} versions",
        len(index.items),
        sum(len(item.versions) for item in index.items),
    )
    return index


def _initialize_report_directory(item: Item, v: ItemVersion, url: str) -> str:
    """Initialize the report directory for an item version.

    Returns sha256 of the rdf.yaml file."""
    report_path = get_report_path(item.id, v.version)
    r = httpx.get(url, follow_redirects=True)
    _ = r.raise_for_status()
    data = r.content
    sha256 = hashlib.sha256(data).hexdigest()
    rdf_path = get_local_rdf_path(item.id, v.version)
    assert report_path in rdf_path.parents
    if rdf_path.exists():
        existing_sha256 = hashlib.sha256(rdf_path.read_bytes()).hexdigest()
        if existing_sha256 != sha256:
            logger.warning(
                "RDF file at {} already exists with different SHA-256: {} != {}. deleting and replacing...",
                rdf_path,
                existing_sha256,
                sha256,
            )
            shutil.rmtree(report_path)

    report_path.mkdir(parents=True, exist_ok=True)
    _ = rdf_path.write_bytes(data)
    logger.info("Initialized report directory {}", report_path)
    return sha256


if __name__ == "__main__":
    _ = create_index()
