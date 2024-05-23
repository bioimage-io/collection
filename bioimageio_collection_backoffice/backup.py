import traceback
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import quote_plus

import markdown
import requests
from bioimageio.spec import (
    InvalidDescr,
    ResourceDescr,
    ValidationContext,
    load_description,
)
from bioimageio.spec.common import HttpUrl, RelativeFilePath
from bioimageio.spec.utils import download
from loguru import logger
from ruyaml import YAML

from ._settings import settings
from .remote_collection import Record, RemoteCollection
from .requests_utils import put_file_from_url, raise_for_status_discretely
from .s3_client import Client

yaml = YAML(typ="safe")


class SkipForNow(NotImplementedError):
    pass


def backup(client: Client):
    """backup all published resources to their own zenodo records"""
    remote_collection = RemoteCollection(client=client)

    backed_up: List[str] = []
    for v in remote_collection.get_published_versions():
        if v.doi is not None:
            continue

        error = None
        try:
            backup_published_version(v)
        except SkipForNow as e:
            logger.warning("{}\n{}", e, traceback.format_exc())
        except Exception as e:
            error = e
            logger.error("{}\n{}", e, traceback.format_exc())

        if error is not None:
            raise error

        backed_up.append(f"{v.id}/{v.version}")

    logger.info("backed up {}", backed_up)


def backup_published_version(
    v: Record,
):
    with ValidationContext(perform_io_checks=False):
        rdf = load_description(v.rdf_url)
        rdf_file_name = download(v.rdf_url).original_file_name

    if isinstance(rdf, InvalidDescr):
        raise Exception(
            "Failed to load RDF from S3:\n" + rdf.validation_summary.format()
        )

    if rdf.id is None:
        raise ValueError("Missing bioimage.io `id`")

    if rdf.id.startswith("10.5281/zenodo"):
        # use legacy doi and concept doi
        parts = rdf.id.split("/")
        assert len(parts) == 3
        concept_doi = "/".join(parts[:2])
        doi = f"10.5281/zenodo{parts[2]}"
        v.set_dois(doi=doi, concept_doi=concept_doi)
        return

    if rdf.type == "application" and "notebook" not in rdf.tags:
        raise SkipForNow(
            "backup for (non-notebook) applications skipped for now."
        )  # TODO: start backing up applications

    if rdf.license is None:
        raise ValueError("Missing license")

    headers = {"Content-Type": "application/json"}
    params = {"access_token": settings.zenodo_api_access_token.get_secret_value()}

    # List the files at the model URL
    file_urls = v.get_file_urls()
    assert file_urls
    logger.info("Using file URLs:\n{}", "\n".join((str(obj) for obj in file_urls)))

    if v.concept.doi is None:
        # Create empty deposition
        r_create = requests.post(
            f"{settings.zenodo_url}/api/deposit/depositions",
            params=params,
            json={},
            headers=headers,
        )
    else:
        concept_id = v.concept.doi.split("/zenodo.")[1]
        # create a new deposition version with different deposition_id from the existing deposition
        r_create = requests.post(
            settings.zenodo_url
            + "/api/deposit/depositions/"
            + concept_id
            + "/actions/newversion",
            params=params,
        )

    raise_for_status_discretely(r_create)
    deposition_info = r_create.json()

    bucket_url = deposition_info["links"]["bucket"]

    # # use the new version's deposit link
    # newversion_draft_url = deposition_info["links"]['latest_draft']
    # assert isinstance(newversion_draft_url, str)
    # # Extract nes deposition_id from url
    # deposition_id = newversion_draft_url.split('/')[-1]

    # PUT files to the deposition
    for file_url in file_urls:
        put_file_from_url(file_url, bucket_url, params)

    # Report deposition URL
    deposition_id = str(deposition_info["id"])
    concept_id = str(deposition_info["conceptrecid"])
    doi = deposition_info["metadata"]["prereserve_doi"]["doi"]
    assert isinstance(doi, str)
    concept_doi = doi.replace(deposition_id, concept_id)

    # base_url = f"{settings.zenodo_url}/record/{concept_id}/files/"

    metadata = rdf_to_metadata(
        rdf,
        rdf_file_name=rdf_file_name,
        publication_date=v.info.created,
    )

    put_url = f"{settings.zenodo_url}/api/deposit/depositions/{deposition_id}"
    logger.debug("PUT {} with metadata: {}", put_url, metadata)
    r_metadata = requests.put(
        put_url,
        params=params,
        json={"metadata": metadata},
        headers=headers,
    )
    raise_for_status_discretely(r_metadata)

    publish_url = (
        f"{settings.zenodo_url}/api/deposit/depositions/{deposition_id}/actions/publish"
    )
    logger.debug("POST {}", publish_url)
    r_publish = requests.post(
        publish_url,
        params=params,
    )
    raise_for_status_discretely(r_publish)
    v.set_dois(doi=doi, concept_doi=concept_doi)


def rdf_authors_to_metadata_creators(rdf: ResourceDescr):
    creators: List[Dict[str, str]] = []
    for author in rdf.authors:
        creator = {"name": str(author.name)}
        if author.affiliation:
            creator["affiliation"] = author.affiliation

        if author.orcid:
            creator["orcid"] = str(author.orcid)

        creators.append(creator)
    return creators


def rdf_to_metadata(
    rdf: ResourceDescr,
    *,
    additional_note: str = "\n(Uploaded via https://bioimage.io)",
    publication_date: datetime,
    rdf_file_name: str,
) -> Dict[str, Any]:

    creators = rdf_authors_to_metadata_creators(rdf)
    docstring = ""
    if rdf.documentation is not None:
        docstring = download(rdf.documentation).path.read_text()

    description_md = f'[View on bioimage.io]("https://bioimage.io/#/?id={rdf.id}") # {rdf.name} \n\n{docstring}'
    logger.debug("markdown descriptoin:\n{}", description_md)
    description = markdown.markdown(description_md)
    logger.debug("html descriptoin:\n{}", description_md)
    keywords = ["backup.bioimage.io", "bioimage.io", "bioimage.io:" + rdf.type]
    # related_identifiers = generate_related_identifiers_from_rdf(rdf, rdf_file_name)  # TODO: add related identifiers

    # for debugging: check if license id is valid:
    # license_response = requests.get(
    #     f"https://zenodo.org/api/vocabularies/licenses/{rdf.license.lower()}"
    # )
    # raise_for_status_discretely(license_response)

    return {
        "title": f"bioimage.io upload: {rdf.id}",
        "description": description,
        "access_right": "open",
        "license": rdf.license,
        "upload_type": "dataset" if rdf.type == "dataset" else "software",
        "creators": creators,
        "publication_date": publication_date.date().isoformat(),
        "keywords": keywords + rdf.tags,
        "notes": rdf.description + additional_note,
        # "related_identifiers": related_identifiers,
        # "communities": [],
    }


def generate_related_identifiers_from_rdf(rdf: ResourceDescr, rdf_file_name: str):
    related_identifiers: List[Dict[str, str]] = []
    covers = []
    for cover in rdf.covers:
        if isinstance(cover, RelativeFilePath):
            cover = cover.absolute

        assert isinstance(cover, HttpUrl)
        covers.append(str(cover))

        related_identifiers.append(
            {
                "relation": "hasPart",  # is part of this upload
                "identifier": cover,
                "resource_type": "image-figure",
                "scheme": "url",
            }
        )

    for link in rdf.links:
        related_identifiers.append(
            {
                "identifier": f"https://bioimage.io/#/r/{quote_plus(link)}",
                "relation": "references",  # // is referenced by this upload
                "resource_type": "other",
                "scheme": "url",
            }
        )

    related_identifiers.append(
        {
            "identifier": rdf_file_name,
            "relation": "isCompiledBy",  # // compiled/created this upload
            "resource_type": "other",
            "scheme": "url",
        }
    )

    if rdf.documentation is not None:
        related_identifiers.append(
            {
                "identifier": (
                    str(rdf.documentation.absolute)
                    if isinstance(rdf.documentation, RelativeFilePath)
                    else str(rdf.documentation)
                ),
                "relation": "isDocumentedBy",  # is referenced by this upload
                "resource_type": "publication-technicalnote",
                "scheme": "url",
            }
        )
    return related_identifiers
