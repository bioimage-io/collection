import json
from pathlib import Path

from bioimageio_collection_backoffice.collection_config import CollectionConfig

local_bioimageio_collection_config_json = (
    Path(__file__).parent.parent / "bioimageio_collection_config.json"
)


def test_bioimageio_collection_config():
    with local_bioimageio_collection_config_json.open() as f:
        config_data = json.load(f)

    _ = CollectionConfig.model_validate(config_data)
