import argparse

import bioimageio.core
from loguru import logger
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


def check_compatibility_icy_impl(
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
            details="only 'model' resources can be used in icy.",
        )

    # produce test summaries for each weight format
    summary = test_model(record.client.get_file_url(record.rdf_path))

    return CompatiblityReport(
        tool=tool,
        status=summary.status,
        error=None if summary.status == "passed" else summary.format(),
        details=summary,
        links=["icy/icy"],
    )


def check_compatibility_icy(
    software_name: str,
    version: str,
    summaries_dir: str = "test_summaries",
):
    """preliminary icy check

    only checks if test outputs are reproduced for onnx, torchscript, or pytorch_state_dict weights.

    """
    collection = RemoteCollection(Client())
    for record in collection.get_published_versions():
        try:
            report = check_compatibility_icy_impl(
                record, f"{software_name}{version}"
            )
        except Exception as e:
            logger.error(f"failed to check '{record.id}': {e}")
        else:
            if report is not None:
                record.set_compatibility_report(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("software_name")
    _ = parser.add_argument("version")
    _ = parser.add_argument("--summaries_dir", default="test_summaries", help="Directory path where summaries are stored.")

    check_compatibility_icy(parser.parse_args().software_name, parser.parse_args().version, parser.parse_args().summaries_dir)
