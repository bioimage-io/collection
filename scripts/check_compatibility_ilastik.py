import argparse
from pathlib import Path
from typing import TYPE_CHECKING

import bioimageio.core
from typing_extensions import Literal

if bioimageio.core.__version__.startswith("0.5."):
    from bioimageio.core import test_resource as test_model
else:
    from bioimageio.core import test_model

from script_utils import CompatibilityReportDict, check_tool_compatibility, download_rdf


def check_compatibility_ilastik_impl(
    rdf_url: str,
    sha256: str,
) -> CompatibilityReportDict:
    """Create a `CompatibilityReport` for a resource description.

    Args:
        rdf_url: URL to the rdf.yaml file
        sha256: SHA-256 value of **rdf_url** content
    """

    rdf = download_rdf(rdf_url, sha256)

    if rdf["type"] != "model":
        report = CompatibilityReportDict(
            status="not-applicable",
            error=None,
            details="only 'model' resources can be used in ilastik.",
        )

    elif len(rdf["inputs"]) > 1 or len(rdf["outputs"]) > 1:
        report = CompatibilityReportDict(
            status="failed",
            error=f"ilastik only supports single tensor input/output (found {len(rdf['inputs'])}/{len(rdf['outputs'])})",
            details=None,
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
        report = CompatibilityReportDict(
            status=status,
            error=error,
            details=details,
            links=["ilastik/ilastik"],
        )

    return report


def check_compatibility_ilastik(
    ilastik_version: str, all_version_path: Path, output_folder: Path
):
    """preliminary ilastik check

    only checks if test outputs are reproduced for onnx, torchscript, or pytorch_state_dict weights.
    # TODO: test with ilastik itself

    """
    check_tool_compatibility(
        "ilastik",
        ilastik_version,
        all_version_path=all_version_path,
        output_folder=output_folder,
        check_tool_compatibility_impl=check_compatibility_ilastik_impl,
        applicable_types={"model"},
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("ilastik_version")
    _ = parser.add_argument("all_versions", type=Path)
    _ = parser.add_argument("output_folder", type=Path)

    args = parser.parse_args()
    check_compatibility_ilastik(
        args.ilastik_version, args.all_versions, args.output_folder
    )
