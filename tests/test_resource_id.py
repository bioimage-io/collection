import pytest

from bioimageio_collection_backoffice.s3_client import Client


def test_validate_resource_id():
    from bioimageio_collection_backoffice.resource_id import validate_resource_id

    assert validate_resource_id("affable-shark", type_="model") is None


@pytest.mark.parametrize("type_", ["model", "dataset", "notebook"])
def test_generate_resource_id(client: Client, type_: str):
    from bioimageio_collection_backoffice.resource_id import (
        generate_resource_id,
        validate_resource_id,
    )

    rid = generate_resource_id(client, type_)
    assert validate_resource_id(rid, type_=type_) is None
