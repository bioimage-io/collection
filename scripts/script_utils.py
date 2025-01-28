import hashlib
import json
import traceback
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Sequence, Set, Union

import requests
from typing_extensions import Literal, NotRequired, TypedDict, TypeGuard

try:
    from ruyaml import YAML
except ImportError:
    from ruamel.yaml import YAML

try:
    from tqdm import tqdm
except ImportError:
    tqdm = list

if TYPE_CHECKING:
    from bioimageio_collection_backoffice.db_structure.compatibility import (
        CompatibilityReport,
    )

yaml = YAML(typ="safe")


class CompatibilityReportDict(TypedDict):
    """TypedDict version of
    `bioimageio_collection_backoffice.db_structure.compatibility.CompatibilityReport`
    for environments without `bioimageio_collection_backoffice`.
    """

    status: Literal["passed", "failed", "not-applicable"]
    """status of this tool for this resource"""

    error: Optional[str]
    """error message if `status`=='failed'"""

    details: Any
    """details to explain the `status`"""

    links: NotRequired[Sequence[str]]
    """the checked resource should link these other bioimage.io resources"""


def check_tool_compatibility(
    tool_name: str,
    tool_version: str,
    *,
    all_version_path: Path,
    output_folder: Path,
    check_tool_compatibility_impl: Callable[
        [str, str], Union[CompatibilityReportDict, "CompatibilityReport"]
    ],
    applicable_types: Set[str],
):
    """helper to implement tool compatibility checks

    Args:
        tool_name: name of the tool (without version), e.g. "ilastik"
        tool_version: version of the tool, e.g. "1.4"
        all_versions_path: Path to the `all_versions.json` file.
        output_folder: Folder to write compatibility reports to.
        check_tool_compatibility_impl:
            Function accepting two positional arguments:
            URL to an rdf.yaml, SHA-256 of that rdf.yaml.
            And returning a compatibility report.
        applicable_types: Set of resource types
            **check_tool_compatibility_impl** is applicable to.
    """
    if "_" in tool_name:
        raise ValueError("Underscore not allowed in tool_name")

    if "_" in tool_version:
        raise ValueError("Underscore not allowed in tool_version")

    with all_version_path.open() as f:
        all_versions = json.load(f)["entries"]

    filtered_versions = [
        entry for entry in all_versions if entry["type"] in applicable_types
    ]

    for entry in tqdm(filtered_versions):
        for version in entry["versions"]:
            rdf_url = version["source"]
            sha256 = version["sha256"]

            report_url = (
                "/".join(rdf_url.split("/")[:-2])
                + f"/compatibility/{tool_name}_{tool_version}.yaml"
            )
            r = requests.head(report_url)
            if r.status_code != 404:
                r.raise_for_status()  # raises if failed to check if report exists
                continue  # report already exists

            try:
                report = check_tool_compatibility_impl(rdf_url, sha256)
            except Exception as e:
                traceback.print_exc()
                warnings.warn(f"failed to check '{rdf_url}': {e}")
            else:
                if not isinstance(report, dict):
                    report = report.model_dump(mode="json")

                report_path = output_folder / (
                    "/".join(rdf_url.split("/")[-4:-2])
                    + f"/compatibility/{tool_name}_{tool_version}.json"
                )
                report_path.parent.mkdir(parents=True, exist_ok=True)
                with report_path.open("wt", encoding="utf-8") as f:
                    json.dump(report, f)


def download_and_check_hash(url: str, sha256: str) -> bytes:
    r = requests.get(url)
    r.raise_for_status()
    data = r.content

    actual = hashlib.sha256(data).hexdigest()
    if actual != sha256:
        raise ValueError(
            f"found sha256='{actual}' for downlaoded {url}, but exptected '{sha256}'"
        )

    return data


def _is_str_dict(d: Any) -> TypeGuard[Dict[str, Any]]:
    return isinstance(d, dict) and all(
        isinstance(k, str) for k in d  # pyright: ignore[reportUnknownVariableType]
    )


def download_rdf(rdf_url: str, sha256: str) -> Dict[str, Any]:
    rdf_data = download_and_check_hash(rdf_url, sha256)
    rdf: Any = yaml.load(rdf_data.decode())
    assert _is_str_dict(rdf)
    return rdf
