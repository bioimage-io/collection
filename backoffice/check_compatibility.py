import json
import traceback
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from backoffice.utils import get_tool_report_path

if TYPE_CHECKING:
    from ruyaml import YAML
else:
    try:
        from ruyaml import YAML
    except ImportError:
        from ruamel.yaml import YAML

try:
    from tqdm import tqdm
except ImportError:
    tqdm = list

try:
    from backoffice.compatibility import ToolCompatibilityReport
except ImportError:
    from backoffice.compatibility_fallback import (
        ToolCompatibilityReport as ToolCompatibilityReportDict,
    )

yaml = YAML(typ="safe")


def check_tool_compatibility(
    tool_name: str,
    tool_version: str,
    *,
    index_path: Path = Path("index.json"),
    check_tool_compatibility_impl: Callable[
        [str, str], "ToolCompatibilityReport | ToolCompatibilityReportDict"
    ],
    applicable_types: set[str],
):
    """helper to implement tool compatibility checks

    Args:
        tool_name: name of the tool (without version), e.g. "ilastik"
        tool_version: version of the tool, e.g. "1.4"
        index_path: Path to the `index.json` file.
        check_tool_compatibility_impl:
            Function accepting two positional arguments:
            URL to an rdf.yaml, SHA-256 of that rdf.yaml.
            And returning a compatibility report.
        applicable_types: Set of resource types
            **check_tool_compatibility_impl** is applicable to.
    """
    with index_path.open() as f:
        items = json.load(f)["items"]

    filtered_items = [item for item in items if item["type"] in applicable_types]

    for item in tqdm(filtered_items):
        for version in item["versions"]:
            rdf_url = version["source"]
            sha256 = version["sha256"]

            report_path = get_tool_report_path(
                item["id"], version["version"], tool_name, tool_version
            )
            if report_path.exists():
                continue

            try:
                report = check_tool_compatibility_impl(rdf_url, sha256)
            except Exception as e:
                traceback.print_exc()
                warnings.warn(f"failed to check '{rdf_url}': {e}")
            else:
                if not isinstance(report, dict):
                    report = report.model_dump(mode="json")

                report_path.parent.mkdir(parents=True, exist_ok=True)
                with report_path.open("wt", encoding="utf-8") as f:
                    json.dump(report, f)
