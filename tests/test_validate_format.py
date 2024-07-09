def test_resolve_v0_4_deps():
    from bioimageio_collection_backoffice.validate_format import (
        _validate_format_impl,  # pyright: ignore[reportPrivateUsage]
    )

    rd, _, conda_envs = _validate_format_impl(
        "https://uk1s3.embassy.ebi.ac.uk/public-datasets/bioimage.io/ambitious-sloth/1/files/rdf.yaml"
    )
    assert conda_envs, rd.validation_summary.format()
