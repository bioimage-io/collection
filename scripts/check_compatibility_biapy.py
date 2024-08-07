import biapy
from biapy.models import check_bmz_model_compatibility

from loguru import logger
from ruyaml import YAML

from bioimageio_collection_backoffice.db_structure.compatibility import (
    CompatiblityReport,
)
from bioimageio_collection_backoffice.remote_collection import Record, RemoteCollection
from bioimageio_collection_backoffice.s3_client import Client

yaml = YAML(typ="safe")


def check_compatibility_biapy_impl(
    record: Record,
    tool: str,
):
    report_path = record.get_compatibility_report_path(tool)
    if list(record.client.ls(report_path)):
        return

    rdf = record.get_rdf()
    if rdf.get("type") != "model":
        return CompatiblityReport(
            tool=tool,
            status="not-applicable",
            details="only 'model' resources can be used in biapy.",
        )

    # Check models compatibility using a function inside BiaPy
    _, error, error_message  = check_bmz_model_compatibility(rdf)
    status = "passed" if not error else "failed"
    return CompatiblityReport(
        tool=tool, status=status, details=error_message, links=["biapy/biapy"]
    )


def check_compatibility_biapy():
    collection = RemoteCollection(Client())
    for record in collection.get_published_versions():
        try:
            report = check_compatibility_biapy_impl(record, f"biapy_{biapy.__version__}")
        except Exception as e:
            logger.error(f"failed to check '{record.id}': {e}")
        else:
            if report is not None:
                record.set_compatibility_report(report)


if __name__ == "__main__":
    check_compatibility_biapy()
