import os

from bioimageio_collection_backoffice import BackOffice


def test_backoffice(
    backoffice: BackOffice, package_url: str, package_id: str, s3_test_folder_url: str
):
    backoffice.stage(resource_id=package_id, package_url=package_url)
    backoffice.test(resource_id=package_id, version="staged/1")
    backoffice.await_review(resource_id=package_id, version="staged/1")
    backoffice.publish(resource_id=package_id, version="staged/1")
    backoffice.generate_collection_json()
    backoffice.backup(os.environ["ZENODO_TEST_URL"])
