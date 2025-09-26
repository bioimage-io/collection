import argparse
from typing import TYPE_CHECKING

import bioimageio.core
from bioimageio.spec.common import Sha256
from typing_extensions import Literal

if bioimageio.core.__version__.startswith("0.5."):
    from bioimageio.core import test_resource as test_model
else:
    from bioimageio.core import test_model

from bioimageio.spec._internal.io_utils import open_bioimageio_yaml

from backoffice.check_compatibility import check_tool_compatibility
from backoffice.compatibility_pure import ToolCompatibilityReport


def check_compatibility_ilastik_impl(
    idem_id: str,
    version: str,
    rdf_url: str,
    sha256: str,
) -> ToolCompatibilityReport:
    """Create a `ToolCompatibilityReport` for a resource description.

    Args:
        rdf_url: URL to the rdf.yaml file
        sha256: SHA-256 value of **rdf_url** content
    """

    rdf = open_bioimageio_yaml(rdf_url, sha256=Sha256(sha256)).content

    input_len = "unknown number of inputs"
    output_len = "unknown number of outputs"
    if rdf["type"] != "model":
        report = ToolCompatibilityReport(
            tool="ilastik",
            status="not-applicable",
            error=None,
            details="only 'model' resources can be used in ilastik.",
            badge=None,
            links=[],
        )

    elif (
        not isinstance(rdf["inputs"], list)
        or not isinstance(rdf["outputs"], list)
        or (input_len := len(rdf["inputs"])) > 1
        or (output_len := len(rdf["outputs"])) > 1
    ):
        report = ToolCompatibilityReport(
            tool="ilastik",
            status="failed",
            error=f"ilastik only supports single tensor input/output (found {input_len}/{output_len})",
            details=None,
            badge=None,
            links=[],
        )
    else:
        # produce test summary with bioimageio.core
        summary = test_model(rdf_url)
        if not TYPE_CHECKING:
            if bioimageio.core.__version__.startswith("0.5."):
                summary = summary[-1]

        status: Literal["passed", "failed"]
        status = summary["status"] if isinstance(summary, dict) else summary.status  # type: ignore
        assert status == "passed" or status == "failed", status

        details = (
            summary if isinstance(summary, dict) else summary.model_dump(mode="json")
        )
        error = (
            None
            if status == "passed"
            else (
                (
                    str(summary["error"])  # pyright: ignore[reportUnknownArgumentType]
                    if "error" in summary
                    else str(summary)
                )
                if isinstance(summary, dict)
                else summary.format()
            )
        )
        report = ToolCompatibilityReport(
            tool="ilastik",
            status=status,
            error=error,
            details=details,
            links=["ilastik/ilastik"],
            badge=None,
        )

    return report


def check_compatibility_ilastik(ilastik_version: str):
    """preliminary ilastik check

    only checks if test outputs are reproduced for onnx, torchscript, or pytorch_state_dict weights.
    # TODO: test with ilastik itself

    """
    check_tool_compatibility(
        "ilastik",
        ilastik_version,
        check_tool_compatibility_impl=check_compatibility_ilastik_impl,
        applicable_types={"model"},
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("ilastik_version")

    args = parser.parse_args()
    check_compatibility_ilastik(args.ilastik_version)
