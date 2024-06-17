import argparse
import warnings

import bioimageio.core
from ruyaml import YAML

from bioimageio_collection_backoffice.db_structure.compatibility import (
    CompatiblityReport,
)
from bioimageio_collection_backoffice.remote_collection import Record, RemoteCollection
from bioimageio_collection_backoffice.s3_client import Client

if bioimageio.core.__version__.startswith("0.5."):
    from bioimageio.core import test_resource as test_model
else:
    from bioimageio.core import test_model

yaml = YAML(typ="safe")


def check_compatibility_ilastik_impl(
    record: Record,
    tool: str,
):
    report_path = record.get_compatibility_report_path(tool)
    if list(record.client.ls(report_path)):
        return

    rdf_data = record.client.load_file(record.rdf_path)
    assert rdf_data is not None
    rdf = yaml.load(rdf_data)
    assert isinstance(rdf, dict)
    if rdf.get("type") != "model":
        return CompatiblityReport(
            tool=tool,
            status="not-applicable",
            error=None,
            details="only 'model' resources can be used in ilastik.",
        )

    # produce test summaries for each weight format
    summary = test_model(record.client.get_file_url(record.rdf_path))
    if bioimageio.core.__version__.startswith("0.5."):
        summary = summary[-1]  # type: ignore

    return CompatiblityReport(
        tool=tool,
        status=summary.status,
        error=None if summary.status == "passed" else summary.format(),
        details=summary,
        links=["ilastik/ilastik"],
    )


def check_compatibility_ilastik(
    ilastik_version: str,
):
    """preliminary ilastik check

    only checks if test outputs are reproduced for onnx, torchscript, or pytorch_state_dict weights.

    """
    collection = RemoteCollection(Client())
    for record in collection.get_published_versions():
        try:
            report = check_compatibility_ilastik_impl(
                record, f"ilastik_{ilastik_version}"
            )
        except Exception as e:
            warnings.warn(f"failed to check '{record.id}': {e}")
        else:
            if report is not None:
                record.set_compatibility_report(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("ilastik_version")

    check_compatibility_ilastik(parser.parse_args().ilastik_version)
