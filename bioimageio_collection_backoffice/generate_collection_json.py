from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from bioimageio.spec import ValidationContext
from bioimageio.spec._internal.io import (
    get_sha256,  # TODO: use bioimageio.spec.utils.get_sha256
)
from bioimageio.spec.common import HttpUrl
from bioimageio.spec.utils import download
from loguru import logger
from ruyaml import YAML

from .remote_resource import PublishedVersion, StagedVersion
from .s3_client import Client

yaml = YAML(typ="safe")


def create_entry(
    client: Client,
    rv: Union[PublishedVersion, StagedVersion],
) -> Optional[Dict[str, Any]]:
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
    entry["info"] = rv.info.model_dump(mode="json")
    if isinstance(rv, StagedVersion) and (
        status := entry["info"]["status"]["name"]
    ) in (
        "superseded",
        "published",
    ):
        logger.debug("skipping {} staged version {} {}", status, rv.id, rv.version)
        return None
    try:
        old_doi = rdf["config"]["_conceptdoi"]
    except KeyError:
        pass
    else:
        entry["direct_zenodo_upload_doi"] = old_doi

    return entry


def generate_doi_mapping(
    client: Client,
    collection: Dict[
        str, Union[Any, Dict[str, Union[Any, List[Union[Any, Dict[str, Any]]]]]]
    ],
):
    mapping: Dict[str, str] = {}
    for e in collection["collection"]:
        assert isinstance(e, dict)
        doi: Any = e.get("doi")
        if doi is not None:
            assert isinstance(doi, str)
            mapping[doi] = e["id"]

        concept_doi: Any = e.get("concept_doi")
        if concept_doi is not None:
            assert isinstance(concept_doi, str)
            mapping[concept_doi] = e["id"]

    client.put_json("mapping_dois.json", mapping)


def generate_old_doi_mapping(
    client: Client,
    collection: Dict[
        str, Union[Any, Dict[str, Union[Any, List[Union[Any, Dict[str, Any]]]]]]
    ],
):
    mapping: Dict[str, str] = {}
    for e in collection["collection"]:
        assert isinstance(e, dict)
        direct_zenodo_upload_doi: Any = e.pop("direct_zenodo_upload_doi", None)
        if direct_zenodo_upload_doi is not None:
            assert isinstance(direct_zenodo_upload_doi, str)
            mapping[direct_zenodo_upload_doi] = e["id"]

    client.put_json("mapping_direct_zenodo_upload_dois.json", mapping)
