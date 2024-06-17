import argparse
import warnings
from typing import Any, Dict, Optional, Sequence, Union

import bioimageio.core
from ruyaml import YAML
from typing_extensions import Literal, TypedDict

if bioimageio.core.__version__.startswith("0.5."):
    from bioimageio.core import test_resource as test_model
else:
    from bioimageio.core import test_model

yaml = YAML(typ="safe")


class CompatiblityReport(TypedDict):
    status: Literal["passed", "failed", "not-applicable"]
    """status of this tool for this resource"""

    error: Optional[str]
    """error message if `status`=='failed'"""

    details: Any
    """details to explain the `status`"""

    links: Sequence[str]
    """the checked resource should link these other bioimage.io resources"""


def check_compatibility_ilastik_impl(
    record: Record,
    tool: str,
):
    report_path = record.get_compatibility_report_path(tool)
    if list(record.client.ls(report_path)):
        return

    rdf_data = record.client.load_file(record.rdf_path)
    assert rdf_data is not None
    rdf: Union[Any, Dict[str, Any]] = yaml.load(rdf_data)
    assert isinstance(rdf, dict)
    if rdf.get("type") != "model":
        return CompatiblityReport(
            tool=tool,
            status="not-applicable",
            error=None,
            details="only 'model' resources can be used in ilastik.",
        )

    if len(rdf["inputs"]) > 1 or len(rdf["outputs"]) > 1:
        return CompatiblityReport(
            tool=tool,
            status="failed",
            error=f"ilastik only supports single tensor input/output (found {len(rdf['inputs'])}/{len(rdf['outputs'])})",
            details=None,
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
