import os
from pathlib import Path

from bioimageio_collection_backoffice.backup import backup
from bioimageio_collection_backoffice.generate_collection_json import (
    generate_collection_json,
)
from bioimageio_collection_backoffice.remote_resource import (
    PublishedVersion,
    RemoteResource,
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
    resource = RemoteResource(client=client, id=package_id)
    staged = resource.stage_new_version(package_url)
    assert isinstance(staged, StagedVersion)
    staged_rdf_url = staged.rdf_url
    assert (
        staged_rdf_url
        == f"{s3_test_folder_url}frank-water-buffalo/staged/1/files/rdf.yaml"
    )
    # skipping test step here (tested in test_backoffice)
    published = staged.publish(reviewer="test")
    assert isinstance(published, PublishedVersion)
    published_rdf_url = published.rdf_url
    assert (
        published_rdf_url == f"{s3_test_folder_url}frank-water-buffalo/1/files/rdf.yaml"
    )

    generate_collection_json(client, collection_template_path)

    backed_up = backup(client, os.environ["ZENODO_TEST_URL"])
    assert backed_up == {"frank-water-buffalo", "collection.json"}
