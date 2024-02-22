import os

from backoffice.backup import backup
from backoffice.utils.remote_resource import (
    PublishedVersion,
    RemoteResource,
    StagedVersion,
)
from backoffice.utils.s3_client import Client


def test_lifecycle(
    client: Client, package_url: str, package_id: str, s3_test_folder_url: str
):
    resource = RemoteResource(client=client, id=package_id)
    staged = resource.stage_new_version(package_url)
    assert isinstance(staged, StagedVersion)
    staged_rdf_url = staged.get_rdf_url()
    assert (
        staged_rdf_url
        == f"{s3_test_folder_url}frank-water-buffalo/staged/1/files/rdf.yaml"
    )
    published = staged.publish()
    assert isinstance(published, PublishedVersion)
    published_rdf_url = published.get_rdf_url()
    assert (
        published_rdf_url == f"{s3_test_folder_url}frank-water-buffalo/1/files/rdf.yaml"
    )

    backed_up = backup(client, os.environ["ZENODO_TEST"])
    assert backed_up == ["frank-water-buffalo"]
