import json
from pathlib import Path
from typing import Any, List

from bioimageio.spec import ValidationContext, build_description
from bioimageio.spec.collection import CollectionDescr
from bioimageio.spec.common import HttpUrl
from bioimageio.spec.utils import download
from dotenv import load_dotenv
from loguru import logger
from ruyaml import YAML

from backoffice.s3_client import Client
from backoffice.s3_structure.versions import (
    PublishedVersionInfo,
    PublishNumber,
    Versions,
)

yaml = YAML(typ="safe")
_ = load_dotenv()

COLLECTION_JSON_S3_PATH = "collection.json"


def generate_collection_json(
    client: Client,
    collection_template: Path = Path("collection_template.json"),
) -> None:
    """generate a json file with an overview of all published resources"""
    logger.info("generating {}", COLLECTION_JSON_S3_PATH)

    with collection_template.open() as f:
        collection = json.load(f)

    resource_dirs = [p for p in client.ls("", only_folders=True)]
    versions_data = {
        rid: client.load_file(f"{rid}/versions.json") for rid in resource_dirs
    }
    missing = {rid for rid, vdata in versions_data.items() if vdata is None}
    if missing:
        logger.warning("{} missing versions.json files for {}", len(missing), missing)

    all_versions = {
        rid: Versions.model_validate_json(vd)
        for rid, vd in versions_data.items()
        if vd is not None
    }

    def create_entry(
        rid: str,
        v: PublishNumber,
        v_info: PublishedVersionInfo,
        versions: List[PublishNumber],
    ) -> dict[str, Any]:
        rdf_s3_path = f"{rid}/{v}/files/rdf.yaml"
        with ValidationContext(perform_io_checks=False):
            rdf_url = HttpUrl(client.get_file_url(rdf_s3_path))

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
            thumbnails: dict[Any, Any] = {}
        else:
            if not isinstance(thumbnails, dict):
                thumbnails = {}

        def maybe_swap_with_thumbnail(src: Any | dict[Any, Any] | list[Any]) -> Any:
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

        entry["created"] = v_info.timestamp.isoformat()
        entry["download_count"] = "?"
        entry["nickname"] = entry["id"]
        entry["nickname_icon"] = entry["id_emoji"]
        entry["entry_source"] = client.get_file_url(rdf_s3_path)
        entry["rdf_source"] = entry["entry_source"]
        entry["versions"] = versions
        return entry

    collection["collection"] = [
        create_entry(rid, v, v_info, list(vs.published))
        for rid, vs in all_versions.items()
        for v, v_info in vs.published.items()
    ]
    coll_descr = build_description(
        collection, context=ValidationContext(perform_io_checks=False)
    )
    if not isinstance(coll_descr, CollectionDescr):
        logger.error(coll_descr.validation_summary.format())

    client.put_json(COLLECTION_JSON_S3_PATH, collection)
