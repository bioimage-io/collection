"""utility functions available in backoffice without dependencies"""

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

try:
    import dotenv
except ImportError:
    pass
else:
    _ = dotenv.load_dotenv()

if TYPE_CHECKING:
    import httpx


def get_report_path(
    item_id: str,
    version: str,
) -> Path:
    return Path(os.getenv("REPORTS", "reports")) / item_id.replace(":", "_") / version


def get_tool_report_path(
    item_id: str,
    version: str,
    tool_name: str,
    tool_version: str,
):
    """Get the path to the report for a specific item version and tool."""
    if "_" in tool_name:
        raise ValueError("Underscore not allowed in tool_name")

    if "_" in tool_version:
        raise ValueError("Underscore not allowed in tool_version")

    return (
        get_report_path(item_id, version)
        / "reports"
        / f"{tool_name}_{tool_version}.json"
    )


def get_all_tool_report_paths(
    item_id: str,
    version: str,
):
    return list((get_report_path(item_id, version) / "reports").glob("*.json"))


def get_summary_data(item_id: str, version: str) -> Optional[dict[str, Any]]:
    """Get the summary data of a specific item version."""
    summary_file_path = get_summary_file_path(item_id, version)
    if not summary_file_path.exists():
        return None

    with summary_file_path.open() as f:
        return json.load(f)


def get_summary_file_path(item_id: str, version: str) -> Path:
    return get_report_path(item_id, version) / "summary.json"


def get_log_file(item_id: str, version: str) -> Path:
    return get_report_path(item_id, version) / "log.txt"


def cached_download(url: str, sha256: str) -> Path:
    """Download a file from the given URL and cache it locally."""
    import httpx

    local_path = Path("cache") / sha256
    if not local_path.exists():
        local_path.parent.mkdir(parents=True, exist_ok=True)
        response = httpx.get(
            url, timeout=float(os.environ.get("HTTP_TIMEOUT", "30"))
        ).raise_for_status()
        with local_path.open("wb") as f:
            _ = f.write(response.content)

    return local_path


def get_rdf_content_from_id(item_id: str, version: str) -> dict[str, Any]:
    """Get the RDF file content of a specific item version."""
    with get_summary_file_path(item_id, version).open() as f:
        return json.load(f)["rdf_content"]


def raise_for_status_discretely(response: "httpx.Response"):
    """Raises :class:`httpx.HTTPError` for 4xx or 5xx responses,
    **but** hides any query and userinfo from url to avoid leaking sensitive data.
    """
    import httpx

    http_error_msg = ""
    reason = response.reason_phrase

    discrete_url = response.url.copy_with(
        query=(b"***query*hidden***" if response.url.query else b""),
        userinfo=(b"***userinfo*hidden***" if response.url.userinfo else b""),
    )

    if 400 <= response.status_code < 500:
        http_error_msg = (
            f"{response.status_code} Client Error: {reason} for url: {discrete_url}"
        )

    elif 500 <= response.status_code < 600:
        http_error_msg = (
            f"{response.status_code} Server Error: {reason} for url: {discrete_url}"
        )

    if http_error_msg:
        raise httpx.HTTPError(http_error_msg)
