from pathlib import Path

from bioimageio_collection_backoffice._settings import settings
from bioimageio_collection_backoffice.backup import backup
from bioimageio_collection_backoffice.db_structure.versions import PublishNumber
from bioimageio_collection_backoffice.generate_collection_json import (
    generate_collection_json,
)
from bioimageio_collection_backoffice.remote_resource import (
    PublishedVersion,
    ResourceConcept,
    StagedVersion,
)
from bioimageio_collection_backoffice.s3_client import Client


def test_lifecycle(
    client: Client,
    package_url: str,
    package_id: str,
    s3_test_folder_url: str,
    collection_template_path: Path,
):
    resource = ResourceConcept(client=client, id=package_id)
    staged = resource.stage_new_version(package_url)
    assert isinstance(staged, StagedVersion)
    staged_rdf_url = staged.rdf_url
    assert (
        staged_rdf_url
        == f"{s3_test_folder_url}frank-water-buffalo/staged/1/files/bioimageio.yaml"
    )
    # skipping test step here (tested in test_backoffice)
    published = staged.publish("github|15139589")
    assert isinstance(published, PublishedVersion)
    published_rdf_url = published.rdf_url
    assert (
        published_rdf_url
        == f"{s3_test_folder_url}frank-water-buffalo/1/files/bioimageio.yaml"
    )

    generate_collection_json(client, collection_template_path)

    backup(client, settings.zenodo_test_url)

    concept_doi = resource.versions.doi
    assert concept_doi is not None
    doi = resource.versions.published[PublishNumber(1)].doi
    assert doi is not None
