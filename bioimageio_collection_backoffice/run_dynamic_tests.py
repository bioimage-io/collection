import traceback
from functools import partialmethod
from pathlib import Path
from typing import Optional, Union

import bioimageio.core
import bioimageio.spec
from bioimageio.spec.model.v0_5 import WeightsFormat
from bioimageio.spec.summary import ErrorEntry, InstalledPackage, ValidationDetail
from bioimageio.spec.utils import download
from loguru import logger

from .common import yaml
from .db_structure.compatibility import CompatiblityReport
from .db_structure.log import LogEntry
from .gh_utils import render_summary
from .remote_collection import Record, RecordDraft

try:
    from tqdm import tqdm
except ImportError:
    pass
else:
    # silence tqdm
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore


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
    record: Union[Record, RecordDraft],
    weight_format: Optional[WeightsFormat],  # "weight format to test model with."
    create_env_outcome: str,
    conda_env_file: Path,
):
    summary = _run_dynamic_tests_impl(
        record.rdf_url, weight_format, create_env_outcome, conda_env_file
    )
    if summary is not None:
        summary_formatted = summary.format()
        record.add_log_entry(
            LogEntry(
                message=f"bioimageio.core {bioimageio.core.__version__} test {summary.status}",
                details=summary,
                details_formatted=summary_formatted,
            )
        )
        render_summary(summary_formatted)

        report = CompatiblityReport(
            tool=f"bioimageio.core_{bioimageio.core.__version__}",
            status=summary.status,
            error=(
                None
                if summary.status == "passed"
                else f"'{summary.name}' failed, check details"
            ),
            details=summary,
        )
        record.set_compatibility_report(report)


def _run_dynamic_tests_impl(
    rdf_url: str,
    weight_format: Optional[WeightsFormat],
    create_env_outcome: str,
    conda_env_file: Path,
):
    if weight_format is None:
        # no dynamic tests for non-model resources yet...
        return

    def get_basic_summary():
        summary = bioimageio.spec.load_description(rdf_url).validation_summary
        summary.name = "bioimageio.core.test_description"
        add = summary.env.add if isinstance(summary.env, set) else summary.env.append
        add(
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
                logger.debug("extracted 'test_kwargs': {}", test_kwargs)
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
        if conda_env_file.exists():
            error = f"Failed to install conda environment:\n```yaml\n{conda_env_file.read_text()}\n```"
        else:
            error = f"Conda environment yaml file not found: {conda_env_file}"

        summary = get_basic_summary()
        summary.add_detail(
            ValidationDetail(
                name="install test environment",
                status="failed",
                errors=[ErrorEntry(loc=(), msg=error, type="env")],
            )
        )

    return summary
