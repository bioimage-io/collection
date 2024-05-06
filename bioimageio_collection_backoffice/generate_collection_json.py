import json
from pathlib import Path
from typing import Any, Dict, List, Union

from bioimageio.spec import ValidationContext, build_description
from bioimageio.spec._internal.io import (
    get_sha256,  # TODO: use bioimageio.spec.utils.get_sha256
)
from bioimageio.spec.collection import CollectionDescr
from bioimageio.spec.common import HttpUrl
from bioimageio.spec.utils import download
from loguru import logger
from ruyaml import YAML
from typing_extensions import Literal, assert_never

from .remote_collection import RemoteCollection
from .remote_resource import PublishedVersion, StagedVersion
from .s3_client import Client

yaml = YAML(typ="safe")


def generate_collection_json(
    client: Client,
    collection_template: Path = Path("collection_template.json"),
    mode: Literal["published", "staged"] = "published",
) -> None:
    """generate a json file with an overview of all published resources"""
    output_file_name: str = (
        "collection.json" if mode == "published" else f"collection_{mode}.json"
    )
    logger.info("generating {}", output_file_name)

    remote_collection = RemoteCollection(client=client)
    with collection_template.open() as f:
        collection = json.load(f)

    error_in_published_entry = None
    if mode == "published":
        for rv in remote_collection.get_all_published_versions():
            try:
                entry = create_entry(client, rv)
            except Exception as e:
                error_in_published_entry = (
                    f"failed to create {rv.id} {rv.version} entry: {e}"
                )
                logger.error(error_in_published_entry)
            else:
                collection["collection"].append(entry)
    elif mode == "staged":
        for rv in remote_collection.get_all_staged_versions():
            try:
                entry = create_entry(client, rv)
            except Exception as e:
                logger.info("failed to create {} {} entry: {}", rv.id, rv.version, e)
            else:
                collection["collection"].append(entry)
    else:
        assert_never(mode)
    coll_descr = build_description(
        collection, context=ValidationContext(perform_io_checks=False)
    )
    if not isinstance(coll_descr, CollectionDescr):
        logger.error(coll_descr.validation_summary.format())

    client.put_json(output_file_name, collection)
    if error_in_published_entry is not None:
        raise ValueError(error_in_published_entry)


def create_entry(
    client: Client,
    rv: Union[PublishedVersion, StagedVersion],
) -> Dict[str, Any]:
    with ValidationContext(perform_io_checks=False):
        rdf_url = HttpUrl(rv.rdf_url)

    rdf_path = download(rdf_url).path
    rdf = yaml.load(rdf_path)

    entry = {
        k: rdf[k]
        for k in (
            "description",
            "id_emoji",
            "id",
            "license",
            "name",
            "type",
        )
    }

    entry["authors"] = rdf.get("authors", [])

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
            if clean_name in thumbnails:
                return rv.get_file_url(thumbnails[clean_name])
            else:
                return src

        return src

    entry["covers"] = maybe_swap_with_thumbnail(rdf.get("covers", []))
    entry["badges"] = maybe_swap_with_thumbnail(rdf.get("badges", []))
    entry["tags"] = rdf.get("tags", [])
    entry["links"] = rdf.get("links", [])
    if "training_data" in rdf:
        entry["training_data"] = rdf["training_data"]

    if "icon" in rdf:
        entry["icon"] = maybe_swap_with_thumbnail(rdf["icon"])

    entry["created"] = rv.info.timestamp.isoformat()
    entry["download_count"] = "?"
    entry["nickname"] = entry["id"]
    entry["nickname_icon"] = entry["id_emoji"]
    entry["entry_source"] = rv.rdf_url
    entry["entry_sha256"] = get_sha256(rdf_path)
    entry["rdf_source"] = entry["entry_source"]
    entry["version_number"] = rv.version
    entry["versions"] = list(rv.concept.versions.published)
    entry["staged_versions"] = [f"staged/{s}" for s in rv.concept.versions.staged]
    entry["doi"] = rv.doi if isinstance(rv, PublishedVersion) else None
    entry["concept_doi"] = rv.concept.doi
    entry["root_url"] = (
        client.get_file_url("").strip("/") + "/" + rv.folder.strip("/") + "/files"
    )
    return entry
