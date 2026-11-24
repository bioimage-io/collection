"""Import published AI4EOSC compatibility results without running inference."""

from __future__ import annotations

from argparse import ArgumentParser
from functools import partial

import httpx
from packaging.version import Version
from pydantic import BaseModel, TypeAdapter

from backoffice.check_compatibility import check_tool_compatibility
from backoffice.compatibility import ToolCompatibilityReport

LOADER_URL = "https://raw.githubusercontent.com/ai4os/ai4os-ai4life-loader/main"
RESULTS_URL = f"{LOADER_URL}/models/filtered_models.json"


class CompatibleModel(BaseModel):
    collection_id: str
    version: str
    sha256: str


def check_compatibility_eosc_impl(
    item_id: str,
    version: str,
    source: str,
    sha256: str,
    *,
    compatible_models: set[tuple[str, str, str]],
) -> ToolCompatibilityReport:
    compatible = (item_id, version, sha256) in compatible_models
    return ToolCompatibilityReport(
        status="passed" if compatible else "failed",
        score=1.0 if compatible else 0.0,
        error=None
        if compatible
        else (
            "Model version and RDF SHA-256 are not listed as compatible with AI4EOSC."
        ),
        details=f"Model is listed as AI4EOSC's compatible in {RESULTS_URL}. ",
    )


def check_compatibility_eosc(id_startswith: str = "") -> None:
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        tool_version = str(
            Version(client.get(f"{LOADER_URL}/VERSION").raise_for_status().text.strip())
        )
        models = TypeAdapter(dict[str, CompatibleModel]).validate_json(
            client.get(RESULTS_URL).raise_for_status().content
        )

    compatible_models = {
        (model.collection_id, model.version, model.sha256) for model in models.values()
    }
    check_tool_compatibility(
        tool_name="eosc",
        tool_version=tool_version,
        check_tool_compatibility_impl=partial(
            check_compatibility_eosc_impl, compatible_models=compatible_models
        ),
        applicable_types={"model"},
        id_startswith=id_startswith,
        overwrite=True,
    )


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    _ = parser.add_argument("--id-startswith", default="", help="Filter by ID prefix")
    args = parser.parse_args()
    check_compatibility_eosc(id_startswith=args.id_startswith)
