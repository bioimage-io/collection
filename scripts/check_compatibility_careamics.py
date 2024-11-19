from typing import Protocol, Optional, Union, Tuple, List
import argparse
from pathlib import Path
import traceback
from functools import lru_cache

import pydantic
from careamics import __version__ as CAREAMICS_VERSION
from careamics import CAREamist
from careamics.lightning import FCNModule, VAEModule
from careamics.config import Configuration
from careamics.model_io.bmz_io import load_from_bmz
from bioimageio.spec import load_model_description
from bioimageio.spec.common import HttpUrl
from bioimageio.core.digest_spec import get_test_inputs
from bioimageio.spec.model import AnyModelDescr
from bioimageio.spec.model.v0_5 import ModelDescr, AxisId

from .script_utils import CompatibilityReportDict, check_tool_compatibility


@lru_cache
def careamics_load_from_bmz(
    rdf_url: Union[HttpUrl, pydantic.DirectoryPath],
) -> Tuple[Union[FCNModule, VAEModule], Configuration]:
    return load_from_bmz(rdf_url)


class CompatibilityCheck_v0_5(Protocol):

    def __call__(
        self, model_desc: ModelDescr, rdf_url: str
    ) -> Optional[CompatibilityReportDict]: ...


def check_model_desc_v0_5(
    model_desc: AnyModelDescr,
) -> Optional[CompatibilityReportDict]:
    if not isinstance(model_desc, ModelDescr):
        return CompatibilityReportDict(
            status="failed",
            error=None,
            details=(
                "CAREamics compatibility check does not support `bioimageio.spec.v0.4` "
                + "model desciptions.",
            ),
        )
    else:
        return None


def check_tagged_careamics(
    model_desc: ModelDescr, rdf_url: str
) -> Optional[CompatibilityReportDict]:
    if ("CAREamics" not in model_desc.tags) and ("careamics" not in model_desc.tags):
        return CompatibilityReportDict(
            status="not-applicable",
            error=None,
            details="'Model' resource not tagged with 'CAREamics' or 'careamics'.",
        )
    else:
        return None


def check_has_careamics_config(
    model_desc: ModelDescr, rdf_url: str
) -> Optional[CompatibilityReportDict]:
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
    # TODO: update to careamics.yaml once files have been updated
    if not ("careamics.yaml" in attachment_file_names):
        return CompatibilityReportDict(
            status="failed",
            error=None,
            details="CAREamics config file is not present in attachments.",
        )
    else:
        return None


def check_careamics_can_load(
    model_desc: ModelDescr, rdf_url: str
) -> Optional[CompatibilityReportDict]:
    try:
        _ = careamics_load_from_bmz(rdf_url)
    except (ValueError, pydantic.ValidationError):
        report = CompatibilityReportDict(
            status="failed",
            error="Error: {}".format(traceback.format_exc()),
            details=("Could not load CAREamics configuration or model."),
        )
        return report
    else:
        return None


def check_careamics_can_predict(
    model_desc: ModelDescr, rdf_url: str
) -> Optional[CompatibilityReportDict]:
    model, config = careamics_load_from_bmz(rdf_url)

    # initialise CAREamist
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
            details=(
                "Calling prediction failed.\nModel created with CAREamics version: "
                f"{config.version}."
            ),
        )
        return report
    else:
        return None


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
    report = check_model_desc_v0_5(model_desc)
    if report is not None:
        return report
    assert isinstance(model_desc, ModelDescr)

    careamics_compatibility_checks: List[CompatibilityCheck_v0_5] = [
        check_tagged_careamics,
        check_has_careamics_config,
        check_careamics_can_load,
        check_careamics_can_predict,
    ]
    for check in careamics_compatibility_checks:
        report = check(model_desc, rdf_url)
        if report is not None:
            return report

    return CompatibilityReportDict(
        status="passed",
        error=None,
        details="CAREamics compatibility checks completed successfully!",
    )


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
