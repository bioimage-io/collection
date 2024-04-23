import json
from pathlib import Path
from typing import Any, Dict, List, Union

from bioimageio.spec import ValidationContext, build_description
from bioimageio.spec.collection import CollectionDescr
from bioimageio.spec.common import HttpUrl
from bioimageio.spec.utils import download
from loguru import logger
from ruyaml import YAML

from .remote_collection import RemoteCollection
from .remote_resource import PublishedVersion
from .s3_client import Client

yaml = YAML(typ="safe")

COLLECTION_JSON_S3_PATH = "collection.json"


def generate_collection_json(
    client: Client,
    collection_template: Path = Path("collection_template.json"),
) -> None:
    """generate a json file with an overview of all published resources"""
    logger.info("generating {}", COLLECTION_JSON_S3_PATH)

    remote_collection = RemoteCollection(client=client)
    with collection_template.open() as f:
        collection = json.load(f)

    collection["config"]["url_root"] = client.get_file_url("").strip("/")
    for p in remote_collection.get_all_published_versions():
        collection["collection"].append(create_entry(p))

    coll_descr = build_description(
        collection, context=ValidationContext(perform_io_checks=False)
    )
    if not isinstance(coll_descr, CollectionDescr):
        logger.error(coll_descr.validation_summary.format())

    client.put_json(COLLECTION_JSON_S3_PATH, collection)


def create_entry(
    p: PublishedVersion,
) -> Dict[str, Any]:
    with ValidationContext(perform_io_checks=False):
        rdf_url = HttpUrl(p.rdf_url)

    rdf = yaml.load(download(rdf_url).path)
    entry = {
        k: rdf[k]
        for k in (
            "authors",
            "description",
            "id_emoji",
            "id",
            "license",
            "name",
            "type",
        )
    }
    try:
        thumbnails = rdf["config"]["bioimageio"]["thumbnails"]
    except KeyError:
        thumbnails: Dict[Any, Any] = {}
    else:
        if not isinstance(thumbnails, dict):
            thumbnails = {}

    def maybe_swap_with_thumbnail(
        src: Union[Any, Dict[Any, Any], List[Any]],
    ) -> Any:
        if isinstance(src, dict):
            return {k: maybe_swap_with_thumbnail(v) for k, v in src.items()}

        if isinstance(src, list):
            return [maybe_swap_with_thumbnail(s) for s in src]

        if isinstance(src, str):
            clean_name = Path(src).name  # remove any leading './'
            return thumbnails.get(clean_name, src)

        return src

    entry["covers"] = maybe_swap_with_thumbnail(rdf["covers"])
    entry["badges"] = maybe_swap_with_thumbnail(rdf.get("badges", []))
    entry["tags"] = rdf.get("tags", [])
    entry["links"] = rdf.get("links", [])
    if "training_data" in rdf:
        entry["training_data"] = rdf["training_data"]

    if "icon" in rdf:
        entry["icon"] = maybe_swap_with_thumbnail(rdf["icon"])

    entry["created"] = p.info.timestamp.isoformat()
    entry["download_count"] = "?"
    entry["nickname"] = entry["id"]
    entry["nickname_icon"] = entry["id_emoji"]
    entry["entry_source"] = p.rdf_url
    entry["rdf_source"] = entry["entry_source"]
    entry["version_number"] = p.number
    entry["versions"] = list(p.concept.versions.published)
    return entry
