import pytest

from bioimageio_collection_backoffice.s3_client import Client


def test_validate_concept_id(client: Client):
    from bioimageio_collection_backoffice.remote_collection import RemoteCollection

    rc = RemoteCollection(client)
    assert rc.validate_concept_id("affable-shark", type_="model") is None


def test_validate_concept_id_direct():
    from bioimageio_collection_backoffice.collection_config import CollectionConfig

    config = CollectionConfig.load()
    assert config.id_parts["model"].validate_concept_id("affable-shark") is None


@pytest.mark.parametrize("type_", ["model", "dataset", "notebook"])
def test_generate_resource_id(client: Client, type_: str):
    from bioimageio_collection_backoffice.remote_collection import RemoteCollection

    rc = RemoteCollection(client)

    cid = rc.generate_concpet_id(type_)
    assert rc.validate_concept_id(cid, type_=type_) is None
