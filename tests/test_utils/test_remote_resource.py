from bioimageio_collection_backoffice.backup import backup
from bioimageio_collection_backoffice.remote_collection import (
    Record,
    RecordConcept,
    RecordDraft,
    RemoteCollection,
    draft_new_version,
)
from bioimageio_collection_backoffice.s3_client import S3Client


def test_lifecycle(
    client: S3Client,
    package_url: str,
    package_id: str,
    s3_test_folder_url: str,
):
    remote_collection = RemoteCollection(client)
    remote_collection.generate_collection_json()
    concept = RecordConcept(client=client, concept_id=package_id)
    draft = draft_new_version(remote_collection, package_url)
    assert isinstance(draft, RecordDraft)
    assert (
        draft.rdf_url == f"{s3_test_folder_url}frank-water-buffalo/draft/files/rdf.yaml"
    )
    # skipping test step here (tested in test_backoffice)
    published = draft.publish("github|15139589")
    assert isinstance(published, Record)
    published_rdf_url = published.rdf_url
    assert (
        published_rdf_url == f"{s3_test_folder_url}frank-water-buffalo/1/files/rdf.yaml"
    )

    remote_collection.generate_collection_json()

    backup(client)

    assert concept.doi is not None
    assert published.doi is not None
