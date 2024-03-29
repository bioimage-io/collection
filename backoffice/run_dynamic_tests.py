import traceback
from functools import partialmethod
from pathlib import Path
from typing import Optional

import bioimageio.core
import bioimageio.spec
from bioimageio.spec.model.v0_5 import WeightsFormat
from bioimageio.spec.summary import (
    ErrorEntry,
    InstalledPackage,
    ValidationDetail,
    ValidationSummary,
)
from ruyaml import YAML

from backoffice.remote_resource import StagedVersion
from backoffice.s3_structure.log import BioimageioLog, Logs

try:
    from tqdm import tqdm
except ImportError:
    pass
else:
    # silence tqdm
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore

yaml = YAML(typ="safe")


def get_summary_detail_from_exception(name: str, exception: Exception):
    return ValidationDetail(
        name=name,
        status="failed",
        errors=[
            ErrorEntry(
                loc=(),
                msg=str(exception),
                type="exception",
                traceback=traceback.format_tb(exception.__traceback__),
            )
        ],
    )


def run_dynamic_tests(
    staged: StagedVersion,
    weight_format: Optional[WeightsFormat],  # "weight format to test model with."
    create_env_outcome: str,
):
    staged.set_testing_status(
        "Testing" + ("" if weight_format is None else f" {weight_format} weights"),
    )
    rdf_source = staged.rdf_url
    if weight_format is None:
        # no dynamic tests for non-model resources yet...
        return

    summary = ValidationSummary(
        name="bioimageio.core.test_description",
        status="passed",
        details=[],
        env=[
            InstalledPackage(
                name="bioimageio.spec", version=bioimageio.spec.__version__
            ),
            InstalledPackage(
                name="bioimageio.core", version=bioimageio.core.__version__
            ),
        ],
        source_name=rdf_source,
    )

    if create_env_outcome == "success":
        try:
            from bioimageio.core import test_description
        except Exception as e:
            summary.add_detail(
                get_summary_detail_from_exception(
                    "import test_description from test environment", e
                )
            )
        else:
            try:
                rdf = yaml.load(rdf_source)
                test_kwargs = (
                    rdf.get("config", {})
                    .get("bioimageio", {})
                    .get("test_kwargs", {})
                    .get(weight_format, {})
                )
            except Exception as e:
                summary.add_detail(
                    get_summary_detail_from_exception("check for test kwargs", e)
                )
            else:
                try:
                    summary = test_description(
                        rdf_source, weight_format=weight_format, **test_kwargs
                    )
                except Exception as e:
                    summary.add_detail(
                        get_summary_detail_from_exception("call 'test_resource'", e)
                    )

    else:
        env_path = Path(f"conda_env_{weight_format}.yaml")
        if env_path.exists():
            error = "Failed to install conda environment:\n" + env_path.read_text()
        else:
            error = f"Conda environment yaml file not found: {env_path}"

        summary.add_detail(
            ValidationDetail(
                name="install test environment",
                status="failed",
                errors=[ErrorEntry(loc=(), msg=error, type="env")],
            )
        )

    staged.extend_log(Logs(bioimageio_core=[BioimageioLog(log=summary)]))
