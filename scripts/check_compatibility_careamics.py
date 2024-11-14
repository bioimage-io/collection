import argparse
from pathlib import Path
import traceback

import numpy as np
import pydantic
from careamics import __version__ as CAREAMICS_VERSION
from careamics import CAREamist
from careamics.model_io.bmz_io import load_from_bmz
from bioimageio.spec import load_model_description
from bioimageio.core.digest_spec import get_test_inputs
from bioimageio.spec.model import AnyModelDescr
from bioimageio.spec.model.v0_5 import ModelDescr, AxisId

from .script_utils import CompatibilityReportDict, check_tool_compatibility


def check_compatibility_careamics_impl(
    rdf_url: str,
    sha256: str,
) -> CompatibilityReportDict:
    """Create a `CompatibilityReport` for a resource description.

    Args:
        rdf_url: URL to the rdf.yaml file
        sha256: SHA-256 value of **rdf_url** content
    """
    model_desc: AnyModelDescr = load_model_description(rdf_url)
    if not isinstance(model_desc, ModelDescr):
        report = CompatibilityReportDict(
            status="failed",
            error=None,
            details=(
                "CAREamics compatibility check does not support `bioimageio.spec.v0.4` "
                + "model desciptions.",
            ),
        )
        return report

    attachment_file_paths = [
        (
            attachment.source
            if isinstance(attachment.source, Path)
            else attachment.source.path
        )
        for attachment in model_desc.attachments
    ]
    attachment_file_names = [
        Path(path).name for path in attachment_file_paths if path is not None
    ]
    # check type is tagged as CAREamics
    if ("CAREamics" not in model_desc.tags) and ("careamics" not in model_desc.tags):
        report = CompatibilityReportDict(
            status="not-applicable",
            error=None,
            details="'Model' resource not tagged with 'CAREamics' or 'careamics'.",
        )
    # check config file is present in attachments
    # TODO: update to careamics.yaml once files have been updated
    elif not "config.yml" in attachment_file_names:
        report = CompatibilityReportDict(
            status="failed",
            error=None,
            details="CAREamics config file is not present in attachments.",
        )
    # download and test
    else:
        try:
            model, config = load_from_bmz(rdf_url)
        except (ValueError, pydantic.ValidationError):
            report = CompatibilityReportDict(
                status="failed",
                error="Error: {}".format(traceback.format_exc()),
                details=("Could not load CAREamics configuration or model."),
            )
            return report

        # no failure mode as config is already a Configuration object
        careamist = CAREamist(config)
        # TODO (CAREamics): make a model loading method, why doesn't this exist
        careamist.model = model

        # get input tensor
        input_sample = get_test_inputs(model_desc)
        input_tensor = list(input_sample.members.values())[0]
        input_tensor = input_tensor.transpose(
            [AxisId("batch"), AxisId("channel"), AxisId("z"), AxisId("y"), AxisId("x")]
            if "Z" in config.data_config.axes
            else [AxisId("batch"), AxisId("channel"), AxisId("y"), AxisId("x")]
        )
        input_array = input_tensor.data.to_numpy()

        try:
            _ = careamist.predict(
                source=input_array,
                data_type="array",
                axes="SCZYX" if "Z" in config.data_config.axes else "SCYX",
            )
        except Exception:
            report = CompatibilityReportDict(
                status="failed",
                error="Error: {}".format(traceback.format_exc()),
                details="Calling prediction failed.",
            )
            return report

        report = CompatibilityReportDict(
            status="passed",
            error=None,
            details="CAREamics compatibility checks completed successfully!",
        )

    return report


def check_compatibility_careamics(all_version_path: Path, output_folder: Path) -> None:
    """CAREamics compatibility check."""
    check_tool_compatibility(
        "CAREamics",
        CAREAMICS_VERSION,
        all_version_path=all_version_path,
        output_folder=output_folder,
        check_tool_compatibility_impl=check_compatibility_careamics_impl,
        applicable_types={"model"},
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("all_versions", type=Path)
    _ = parser.add_argument("output_folder", type=Path)

    args = parser.parse_args()
    check_compatibility_careamics(args.all_versions, args.output_folder)
