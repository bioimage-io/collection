def test_collection_config():
    from bioimageio_collection_backoffice.collection_config import CollectionConfig

    config = CollectionConfig.load()
    assert config

    # test id parts
    assert "🐼" == config.id_parts.get_icon("philosophical-panda")
