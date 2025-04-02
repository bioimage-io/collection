from bioimageio_collection_backoffice import BackOffice
from bioimageio_collection_backoffice.settings import settings


def test_backoffice(backoffice: BackOffice, package_url: str, package_id: str):
    backoffice.generate_collection_json()  # create initial collection.json
    backoffice.draft(concept_id=package_id, package_url=package_url)
    backoffice.test(concept_id=package_id, version="draft")
    backoffice.publish(concept_id=package_id, reviewer="github|15139589")
    backoffice.generate_collection_json()
    backoffice.backup(settings.zenodo_test_url)
