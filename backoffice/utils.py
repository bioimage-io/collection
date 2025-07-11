import os
from pathlib import Path

try:
    import dotenv
except ImportError:
    pass
else:
    _ = dotenv.load_dotenv()


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


def get_summary_file_path(item_id: str, version: str) -> Path:
    return get_report_path(item_id, version) / "summary.json"


def get_log_file(item_id: str, version: str) -> Path:
    return get_report_path(item_id, version) / "log.txt"


def get_local_rdf_path(item_id: str, version: str) -> Path:
    """Get the local path to the RDF file for a specific item version."""
    return get_report_path(item_id, version) / "rdf.yaml"
