import traceback
from functools import partialmethod
from pathlib import Path
from typing import Optional

import bioimageio.core
import bioimageio.spec
from bioimageio.spec.model.v0_5 import WeightsFormat
from bioimageio.spec.summary import ErrorEntry, InstalledPackage, ValidationDetail
from bioimageio.spec.utils import download
from ruyaml import YAML

from bioimageio_collection_backoffice.db_structure.compatibility import (
    CompatiblityReport,
)

from .db_structure.log import LogEntry
from .remote_collection import Record, RecordDraft

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
    staged: RecordDraft,
    weight_format: Optional[WeightsFormat],  # "weight format to test model with."
    create_env_outcome: str,
):
    staged.set_testing_status(
        "Testing" + ("" if weight_format is None else f" {weight_format} weights"),
    )
    summary = _run_dynamic_tests_impl(staged.rdf_url, weight_format, create_env_outcome)
    if summary is not None:
        staged.add_log_entry(
            LogEntry(
                message=f"bioimageio.core {bioimageio.core.__version__} test {summary.status}",
                details=summary,
            )
        )


def rerun_dynamic_tests(
    published: Record,
    weight_format: Optional[WeightsFormat],  # "weight format to test model with."
    create_env_outcome: str,
):
    summary = _run_dynamic_tests_impl(
        published.rdf_url, weight_format, create_env_outcome
    )
    if summary is not None:
        published.add_log_entry(LogEntry(message=summary.name, details=summary))
        report = CompatiblityReport(
            tool="bioimageio.core",
            status=summary.status,
            error=None if summary.status == "passed" else f"'{summary.name}' failed",
            details=summary,
        )
        published.set_compatibility_report(report)


def _run_dynamic_tests_impl(
    rdf_url: str, weight_format: Optional[WeightsFormat], create_env_outcome: str
):
    if weight_format is None:
        # no dynamic tests for non-model resources yet...
        return

    def get_basic_summary():
        summary = bioimageio.spec.load_description(rdf_url).validation_summary
        summary.name = "bioimageio.core.test_description"
        summary.env.append(
            InstalledPackage(
                name="bioimageio.core", version=bioimageio.core.__version__
            )
        )
        return summary

    if create_env_outcome == "success":
        try:
            from bioimageio.core import test_description
        except Exception as e:
            summary = get_basic_summary()
            summary.add_detail(
                get_summary_detail_from_exception(
                    "import test_description from test environment", e
                )
            )
        else:
            try:
                rdf = yaml.load(download(rdf_url).path)
                test_kwargs = (
                    rdf.get("config", {})
                    .get("bioimageio", {})
                    .get("test_kwargs", {})
                    .get(weight_format, {})
                )
            except Exception as e:
                summary = get_basic_summary()
                summary.add_detail(
                    get_summary_detail_from_exception("check for test kwargs", e)
                )
            else:
                try:
                    summary = test_description(
                        rdf_url, weight_format=weight_format, **test_kwargs
                    )
                except Exception as e:
                    summary = get_basic_summary()
                    summary.add_detail(
                        get_summary_detail_from_exception("call 'test_resource'", e)
                    )

    else:
        env_path = Path(f"conda_env_{weight_format}.yaml")
        if env_path.exists():
            error = "Failed to install conda environment:\n" + env_path.read_text()
        else:
            error = f"Conda environment yaml file not found: {env_path}"

        summary = get_basic_summary()
        summary.add_detail(
            ValidationDetail(
                name="install test environment",
                status="failed",
                errors=[ErrorEntry(loc=(), msg=error, type="env")],
            )
        )

    return summary
