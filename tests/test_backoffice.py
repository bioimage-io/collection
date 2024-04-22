from bioimageio_collection_backoffice import BackOffice
from bioimageio_collection_backoffice._settings import settings


def test_backoffice(backoffice: BackOffice, package_url: str, package_id: str):
    backoffice.stage(resource_id=package_id, package_url=package_url)
    backoffice.test(resource_id=package_id, version="staged/1")
    backoffice.await_review(resource_id=package_id, version="staged/1")
    backoffice.publish(
        resource_id=package_id, version="staged/1", reviewer="github|15139589"
    )
    backoffice.generate_collection_json()
    backoffice.backup(settings.zenodo_test_url)
