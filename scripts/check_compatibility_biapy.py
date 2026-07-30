from argparse import ArgumentParser

import biapy
from biapy.models import check_bmz_model_compatibility

from backoffice.check_compatibility import check_tool_compatibility
from backoffice.compatibility import ToolCompatibilityReport
from backoffice.utils import get_rdf_content_from_url


def check_compatibility_biapy_impl(
    item_id: str,
    version: str,
    source: str,
    sha256: str,
):
    rdf = get_rdf_content_from_url(source, sha256)
    if rdf.get("type") != "model":
        return ToolCompatibilityReport(
            score=0,
            error=None,
            status="not-applicable",
            details="only 'model' resources can be used in biapy.",
        )

    # Check models compatibility using a function inside BiaPy
    if biapy.__version__ == "3.6.5":
        _, error, error_message = check_bmz_model_compatibility(
            {"raw": {"manifest": rdf}}
        )
    else:
        # From BiaPy 3.6.8 on, the function returns a dict, so new keys can be
        # added in the future without breaking this script. Only "error" and
        # "reason_message" are needed here.
        compatibility_report = check_bmz_model_compatibility(rdf)
        error = compatibility_report["error"]
        error_message = compatibility_report["reason_message"]

    status = "passed" if not error else "failed"
    if error:
        print(f"Reason why BiaPy is not compatible: {error_message}")

    return ToolCompatibilityReport(
        status=status,
        score=1.0 if status == "passed" else 0.0,
        details=error_message,
        links=["biapy/biapy"],
        error=error_message,
    )


def check_compatibility(id_startswith: str):
    check_tool_compatibility(
        tool_name="biapy",
        tool_version=biapy.__version__,
        check_tool_compatibility_impl=check_compatibility_biapy_impl,
        applicable_types={"model"},
        id_startswith=id_startswith,
    )


if __name__ == "__main__":
    parser = ArgumentParser()
    _ = parser.add_argument("--id-startswith", default="", help="Filter by ID prefix")
    args = parser.parse_args()

    check_compatibility(id_startswith=args.id_startswith)
