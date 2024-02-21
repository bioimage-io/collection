def test_lifecycle(package_url: str, package_id: str, s3_test_folder_url: str):
    from scripts.utils.remote_resource import (
        PublishedVersion,
        RemoteResource,
        StagedVersion,
    )
    from scripts.utils.s3_client import Client

    resource = RemoteResource(client=Client(), id=package_id)
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
        published_rdf_url == f"{s3_test_folder_url}frank-water-buffalo/3/files/rdf.yaml"
    )
