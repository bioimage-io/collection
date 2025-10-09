from argparse import ArgumentParser

import bioimageio.core
from bioimageio.core import test_description
from bioimageio.spec.common import Sha256

from backoffice.check_compatibility import check_tool_compatibility
from backoffice.compatibility import ToolCompatibilityReport
from backoffice.utils_pure import get_log_file


def check_compatibility_core_impl(item_id: str, version: str, source: str, sha256: str):
    core_summary = test_description(
        source,
        sha256=Sha256(sha256),
        determinism="full",
        runtime_env="as-described",
    )

    log_file = get_log_file(item_id, version)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    return ToolCompatibilityReport(
        tool="bioimageio.core",
        tool_version=bioimageio.core.__version__,
        status=(
            "failed" if core_summary.status == "valid-format" else core_summary.status
        ),
        score={"passed": 1.0, "valid-format": 0.5}.get(core_summary.status, 0.0),
        details=core_summary.model_dump(mode="json"),
        links=["bioimageio/bioimageio.core"] if core_summary.status == "passed" else [],
        error=(
            None
            if core_summary.status == "passed"
            else "\n\n".join(
                error_msgs
                if len(
                    error_msgs := [
                        de.msg
                        for d in core_summary.details
                        for de in d.errors
                        if d.status == "failed"
                    ]
                )
                <= 3
                else error_msgs[:3] + ["..."]
            )
        ),
    )


def check_compatibility(id_startswith: str):
    check_tool_compatibility(
        tool_name="bioimageio.core",
        tool_version=bioimageio.core.__version__,
        check_tool_compatibility_impl=check_compatibility_core_impl,
        applicable_types={"model"},
        id_startswith=id_startswith,
    )


if __name__ == "__main__":
    parser = ArgumentParser()
    _ = parser.add_argument("--id-startswith", default="", help="Filter by ID prefix")
    args = parser.parse_args()

    check_compatibility(id_startswith=args.id_startswith)
