from __future__ import annotations

import traceback
from pathlib import Path
from typing import Protocol

import pydantic
from bioimageio.core.digest_spec import get_test_inputs
from bioimageio.spec import load_model_description
from bioimageio.spec.common import Sha256
from bioimageio.spec.model import AnyModelDescr
from bioimageio.spec.model.v0_5 import AxisId, ModelDescr
from careamics import CAREamist
from careamics import __version__ as CAREAMICS_VERSION

from backoffice.check_compatibility import check_tool_compatibility
from backoffice.compatibility_pure import ToolCompatibilityReportDict


class CompatibilityCheck_v0_5(Protocol):
    def __call__(
        self, model_desc: ModelDescr, rdf_url: str
    ) -> ToolCompatibilityReportDict | None: ...


def check_model_desc_v0_5(
    model_desc: AnyModelDescr,
) -> ToolCompatibilityReportDict | None:
    if not isinstance(model_desc, ModelDescr):
        return ToolCompatibilityReportDict(
            status="not-applicable",
            error=None,
            details=(
                "CAREamics compatibility check does not support `bioimageio.spec.v0.4` "
                + "model desciptions.",
            ),
            badge=None,
            links=[],
        )
    else:
        return None


def check_tagged_careamics(
    model_desc: ModelDescr, rdf_url: str
) -> ToolCompatibilityReportDict | None:
    if ("CAREamics" not in model_desc.tags) and ("careamics" not in model_desc.tags):
        return ToolCompatibilityReportDict(
            status="not-applicable",
            error=None,
            details="'Model' resource not tagged with 'CAREamics' or 'careamics'.",
            badge=None,
            links=[],
        )
    else:
        return None


def check_has_careamics_config(
    model_desc: ModelDescr, rdf_url: str
) -> ToolCompatibilityReportDict | None:
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
    if "careamics.yaml" not in attachment_file_names:
        return ToolCompatibilityReportDict(
            status="failed",
            error=None,
            details="CAREamics config file is not present in attachments.",
            badge=None,
            links=[],
        )
    else:
        return None


def check_careamics_can_load(
    model_desc: ModelDescr, rdf_url: str
) -> ToolCompatibilityReportDict | None:
    try:
        _ = CAREamist(bmz_path=rdf_url)
    except (ValueError, pydantic.ValidationError):
        report = ToolCompatibilityReportDict(
            status="failed",
            error=f"Error: {traceback.format_exc()}",
            details=("Could not load CAREamics configuration or model."),
            badge=None,
            links=[],
        )
        return report
    else:
        return None


def check_careamics_can_predict(
    model_desc: ModelDescr, rdf_url: str
) -> ToolCompatibilityReportDict | None:
    careamist = CAREamist(bmz_path=rdf_url)
    config = careamist.config

    # get input tensor
    input_sample = get_test_inputs(model_desc)
    input_tensor = next(iter(input_sample.members.values()))
    input_tensor = input_tensor.transpose(
        [AxisId("batch"), AxisId("channel"), AxisId("z"), AxisId("y"), AxisId("x")]
        if "Z" in config.data_config.axes
        else [AxisId("batch"), AxisId("channel"), AxisId("y"), AxisId("x")]
    )
    input_array = input_tensor.data.to_numpy()

    try:
        _ = careamist.predict(
            pred_data=input_array,
            data_type="array",
            axes="SCZYX" if "Z" in config.data_config.axes else "SCYX",
        )
    except Exception:
        report = ToolCompatibilityReportDict(
            status="failed",
            error=f"Error: {traceback.format_exc()}",
            details=(
                "Calling prediction failed.\nModel created with CAREamics version: "
                f"{config.version}."
            ),
            badge=None,
            links=[],
        )
        return report
    else:
        return None


def check_compatibility_careamics_impl(
    item_id: str,
    version: str,
    rdf_url: str,
    sha256: str,
) -> ToolCompatibilityReportDict:
    """Create a `CompatibilityReport` for a resource description.

    Args:
        rdf_url: URL to the rdf.yaml file
        sha256: SHA-256 value of **rdf_url** content
    """
    model_desc: AnyModelDescr = load_model_description(rdf_url, sha256=Sha256(sha256))
    report = check_model_desc_v0_5(model_desc)
    if report is not None:
        return report
    assert isinstance(model_desc, ModelDescr)

    careamics_compatibility_checks: list[CompatibilityCheck_v0_5] = [
        check_tagged_careamics,
        check_has_careamics_config,
        check_careamics_can_load,
        check_careamics_can_predict,
    ]
    for check in careamics_compatibility_checks:
        report = check(model_desc, rdf_url)
        if report is not None:
            return report

    return ToolCompatibilityReportDict(
        tool="careamics",
        status="passed",
        error=None,
        details="CAREamics compatibility checks completed successfully!",
        badge=None,
        links=[],
    )


def check_compatibility_careamics() -> None:
    """CAREamics compatibility check."""
    check_tool_compatibility(
        "careamics",
        CAREAMICS_VERSION,
        check_tool_compatibility_impl=check_compatibility_careamics_impl,
        applicable_types={"model"},
    )


if __name__ == "__main__":
    model_path = "CAREamics/saved_models/Noise2Void_2D_careamics_n2v"
    # model_path = "CAREamics/saved_models/Noise2Void_2D_careamics_n2v.zip"
    model_desc = load_model_description(model_path)
    check_has_careamics_config(model_desc, rdf_url=None)
    check_careamics_can_load(model_desc, model_path)
    check_careamics_can_predict(model_desc, model_path)
