import traceback
from datetime import datetime
from io import BytesIO
from pathlib import PurePosixPath
from typing import Dict, List
from urllib.parse import quote_plus, urlparse

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


from ._settings import settings
from .remote_collection import Record, RemoteCollection
from .s3_client import Client
import bioimageio_collection_backoffice.zenodo as zd

class SkipForNow(NotImplementedError):
    pass


def backup(client: Client):
    """backup all published resources to their own zenodo records"""
    remote_collection = RemoteCollection(client=client)
    zenodo_client = zd.Client(
        session=requests.Session(),
        access_token=settings.zenodo_api_access_token.get_secret_value(),
        api_hostname=urlparse(settings.zenodo_url).netloc,
    )

    backed_up: List[str] = []
    error = None
    for v in remote_collection.get_published_versions()[::-1]:
        if v.doi is not None:
            continue

        try:
            backup_published_version(v, zenodo_client=zenodo_client)
        except SkipForNow as e:
            logger.warning("{}\n{}", e, traceback.format_exc())
        except Exception as e:
            error = e
            logger.error("{}\n{}", e, traceback.format_exc())
        else:
            backed_up.append(f"{v.id}/{v.version}")

    logger.info("backed up {}", backed_up)
    if error is not None:
        raise error


def backup_published_version(
    v: Record, zenodo_client: zd.Client
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
        # ignore legacy model
        return

    if rdf.type == "application" and "notebook" not in rdf.tags:
        raise SkipForNow(
            "backup for (non-notebook) applications skipped for now."
        )  # TODO: start backing up applications

    if rdf.license is None:
        raise ValueError(f"Missing license for {v.id}")

    if v.concept.doi is None:
        deposition_info = zenodo_client.create_new_concept()
    else:
        concept_doi = zd.ZenodoDoi[zd.ConceptId].model_validate(v.concept.doi)
        # create a new deposition version with different deposition_id from the existing deposition
        deposition_info: zd.Record = zenodo_client.create_new_concept_version(concept_id=concept_doi.id)

    # # use the new version's deposit link
    # newversion_draft_url = deposition_info["links"]['latest_draft']
    # assert isinstance(newversion_draft_url, str)
    # # Extract nes deposition_id from url
    # deposition_id = newversion_draft_url.split('/')[-1]

    # PUT files to the deposition
    for file_path in v.get_file_paths():
        file_data = v.client.load_file(file_path)
        assert file_data is not None
        filename = PurePosixPath(file_path).name
        zenodo_client.add_file_to_record(record=deposition_info, file_name=filename, data=BytesIO(file_data))

    metadata = rdf_to_zenodo_metadata(
        rdf,
        rdf_file_name=rdf_file_name,
        publication_date=v.info.created,
    )

    zenodo_client.add_metadata_to_record(record_id=deposition_info.id, metadata=metadata)

    published_record = zenodo_client.publish(record_id=deposition_info.id)
    if published_record.doi is None:
        raise TypeError("Expected published record to have a DOI, found None")
    if published_record.conceptdoi is None:
        raise TypeError("Expected published record to have a concept DOI, found None")
    v.set_dois(
        doi=published_record.doi.as_str(),
        concept_doi=published_record.conceptdoi.as_str(),
    )


def rdf_to_zenodo_metadata(
    rdf: ResourceDescr,
    *,
    additional_note: str = "\n(Uploaded via https://bioimage.io)",
    publication_date: datetime,
    rdf_file_name: str,
) -> "zd.OpenAccessSoftwareMetadataArgs | zd.OpenAccessDatasetMetadataArgs":
    if rdf.license is None:
        raise ValueError(f"Missing license for {rdf.id}")
    license = str(rdf.license).lower()
    if not zd.is_zenodo_license(license):
        message = f"License '{rdf.license}' not known to Zenodo."
        logger.error(
            (
                message
                + " Please add manually as custom license"
                + " (as this is currently not supported to do via REST API)"
            )
        )
        raise ValueError(message)

    creators = [
        zd.RecordCreator(
            name=str(author.name),
            affiliation=None if author.affiliation is None else str(author.affiliation),
            orcid = None if author.orcid is None else str(author.orcid),
        )
        for author in rdf.authors
    ]

    docstring = ""
    if rdf.documentation is not None:
        docstring = download(rdf.documentation).path.read_text()

    description_md = f'[View on bioimage.io]("https://bioimage.io/#/?id={rdf.id}") # {rdf.name} \n\n{docstring}'
    logger.debug("markdown descriptoin:\n{}", description_md)
    description = markdown.markdown(description_md)
    logger.debug("html description:\n{}", description_md)
    keywords = ["backup.bioimage.io", "bioimage.io", "bioimage.io:" + rdf.type]

    if rdf.type == "dataset":
        return zd.OpenAccessDatasetMetadataArgs(
            title=f"bioimage.io upload: {rdf.id}",
            description=description,
            access_right="open",
            upload_type="dataset",
            creators=creators,
            publication_date=publication_date.date(),
            keywords=keywords + rdf.tags,
            notes=rdf.description + additional_note,
            license=license,
            prereserve_doi=True,
        )
    else:
        return zd.OpenAccessSoftwareMetadataArgs(
            title=f"bioimage.io upload: {rdf.id}",
            description=description,
            access_right="open",
            upload_type="software",
            creators=creators,
            publication_date=publication_date.date(),
            keywords=keywords + rdf.tags,
            notes=rdf.description + additional_note,
            license=license,
            prereserve_doi=True,
        )

def generate_related_identifiers_from_rdf(rdf: ResourceDescr, rdf_file_name: str):
    related_identifiers: List[Dict[str, str]] = []
    covers = []
    for cover in rdf.covers:
        if isinstance(cover, RelativeFilePath):
            cover = cover.absolute()

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
