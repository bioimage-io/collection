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


def generate_collection_json(
    client: Client,
    collection_template: Path = Path("collection_template.json"),
    output_path: Path = Path("collection.json"),
) -> None:
    """generate a json file with an overview of all published resources"""
    with collection_template.open() as f:
        collection = json.load(f)

    logger.info("generating {}", output_path)
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

    def get_info(
        rid: str,
        v: PublishNumber,
        v_info: PublishedVersionInfo,
        versions: List[PublishNumber],
    ) -> dict[str, Any]:
        rdf_s3_path = f"{rid}/{v}/files/rdf.yaml"
        with ValidationContext(perform_io_checks=False):
            rdf_url = HttpUrl(client.get_file_url(rdf_s3_path))

        rdf = yaml.load(download(rdf_url).path)
        info = {
            k: rdf[k]
            for k in (
                "authors",
                "covers",
                "description",
                "id",
                "id_emoji",
                "license",
                "links",
                "name",
                "type",
            )
        }

        info["badges"] = rdf.get("badges", [])
        info["tags"] = rdf.get("tags", [])
        if "training_data" in rdf:
            info["training_data"] = rdf["training_data"]

        if "icon" in rdf:
            info["icon"] = rdf["icon"]

        info["created"] = v_info.timestamp.isoformat()
        info["download_count"] = "?"
        info["nickname"] = info["id"]
        info["nickname_icon"] = info["id_emoji"]
        info["rdf_source"] = client.get_file_url(rdf_s3_path)
        info["versions"] = versions
        return info

    collection["collection"] = [
        get_info(rid, v, v_info, list(vs.published))
        for rid, vs in all_versions.items()
        for v, v_info in vs.published.items()
    ]
    coll_descr = build_description(
        collection, context=ValidationContext(perform_io_checks=False)
    )
    assert isinstance(coll_descr, CollectionDescr)
