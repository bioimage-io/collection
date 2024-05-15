def test_resolve_v0_4_deps():
    from bioimageio_collection_backoffice.validate_format import validate_format_impl

    _, _, conda_envs = validate_format_impl(
        "https://uk1s3.embassy.ebi.ac.uk/public-datasets/bioimage.io/ambitious-sloth/staged/1/files/bioimageio.yaml"
    )
    assert conda_envs
