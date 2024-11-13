import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from typing_extensions import Literal

import numpy as np
import pydantic
from careamics import CAREamist
from careamics.model_io import load_pretrained
from careamics.model_io.bmz_io import load_from_bmz
from bioimageio.spec import load_model_description, ModelDescr
from bioimageio.spec.generic.v0_2 import AttachmentsDescr
import bioimageio.core

if bioimageio.core.__version__.startswith("0.5."):
    from bioimageio.core import test_resource as test_model
else:
    from bioimageio.core import test_model

from .script_utils import CompatibilityReportDict, check_tool_compatibility, download_rdf


def check_compatibility_careamics_impl(
    rdf_url: str,
    sha256: str,
) -> CompatibilityReportDict:
    """Create a `CompatibilityReport` for a resource description.

    Args:
        rdf_url: URL to the rdf.yaml file
        sha256: SHA-256 value of **rdf_url** content
    """
    model_desc = load_model_description(rdf_url)
    if isinstance(model_desc.attachments, AttachmentsDescr):
        attachment_file_names = [file.path.name for file in model_desc.attachments.files]
    elif isinstance(model_desc.attachments, list):
        attachment_file_names = [
            attachment.source.path.name for attachment in model_desc.attachments
        ]
    else:
        # TODO: confirm all types of attachments
        report = CompatibilityReportDict(
            status="failed",
            error=None,
            details="Could not process attachments.",
        )
    # check type is model
    if model_desc.type != "model":
        report = CompatibilityReportDict(
            status="not-applicable",
            error=None,
            details="Only 'model' resources can be used in CAREamics.",
        )
    # check type is tagged as CAREamics
    elif ("CAREamics" not in model_desc.tags) and ("careamics" not in model_desc.tags):
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
        except (ValueError, pydantic.ValidationError) as e:
            report = CompatibilityReportDict(
                status="failed",
                error=None,
                details=(
                    "Could not load CAREamics configuration or model.\n",
                    "Error: {}".format(e)
                )
            )
            return report
        
        # no failure mode as config is already a Configuration object
        careamist = CAREamist(config) 
        # TODO: make a model loading method, why doesn't this exist
        careamist.model = model

        # get input tensor
        input_path = model_desc.inputs[0].test_tensor.download().path
        input_array = np.load(input_path)

        try:
            _ = careamist.predict(
                source=input_array,
                data_type="array",
                axes="SCZYX" if "Z" in config.data_config.axes else "SCYX",
            )
        except Exception as e: 
            report = CompatibilityReportDict(
                status="failed",
                error=None,
                details="Calling prediction failed.\nError {}".format(e),
            )
            return report

        report = CompatibilityReportDict(
                status="passed",
                error=None,
                details="CAREamics compatibility checks completed successfully!",
            )

    return report
