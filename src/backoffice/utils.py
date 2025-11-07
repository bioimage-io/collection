"""utility functions"""

import json
from typing import TYPE_CHECKING, Any

try:
    from pydantic import ValidationError
except ImportError as e:
    raise ImportError(
        "pydantic is required for backoffice.utils. "
        "Please install `backoffice[dev]` or use backoffice.utils_plain."
    ) from e

from backoffice.compatibility import CompatibilitySummary, InitialSummary
from backoffice.utils_pure import cached_download as cached_download
from backoffice.utils_pure import (
    get_all_tool_report_paths as get_all_tool_report_paths,
)
from backoffice.utils_pure import get_summary_file_path

if TYPE_CHECKING:
    from ruyaml import YAML
else:
    try:
        from ruyaml import YAML
    except ImportError:
        from ruamel.yaml import YAML

yaml = YAML(typ="safe")


def get_rdf_content_from_url(url: str, sha256: str) -> dict[str, Any]:
    local_path = cached_download(url, sha256)
    return yaml.load(local_path)


def get_summary(item_id: str, version: str) -> "InitialSummary | CompatibilitySummary":
    """Retrieve the summary for a specific item and version."""
    summary_path = get_summary_file_path(item_id, version)
    if not summary_path.exists():
        return InitialSummary(
            rdf_content={},
            rdf_yaml_sha256="",
            status="untested",
        )

    with summary_path.open(encoding="utf-8") as f:
        data = json.load(f)

    try:
        return CompatibilitySummary.model_validate(data)
    except ValidationError:
        return InitialSummary.model_validate(data)
