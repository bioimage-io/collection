import json
import warnings
from typing import Dict

from loguru import logger
from packaging.version import Version
from tqdm import tqdm

from backoffice.compatibility import (
    TOOL_NAMES,
    CompatibilityScores,
    CompatibilitySummary,
    ToolCompatibilityReport,
    ToolName,
    ToolNameVersioned,
    ToolReportDetails,
)
from backoffice.index import IndexItem, IndexItemVersion, load_index
from backoffice.utils import (
    get_all_tool_report_paths,
    get_summary,
    get_summary_file_path,
)


def summarize_reports():
    index = load_index()
    for item in tqdm(index.items):
        for v in item.versions:
            _summarize(item, v)

    # TODO: Parallelize?
    # with ThreadPoolExecutor() as executor:
    #     futures: list[Future[Any]] = []
    #     for item in index.items:
    #         for v in item.versions:
    #             futures.append(executor.submit(_summarize, item, v))

    #     for _ in tqdm(as_completed(futures), total=len(futures)):
    #         pass


def _summarize(item: IndexItem, v: IndexItemVersion):
    """Conflate all summaries for a given item version."""

    initial_summary = get_summary(item.id, v.version)

    reports: list[ToolCompatibilityReport] = []
    scores: dict[ToolNameVersioned, float] = {}
    metadata_completeness = 0.0
    metadata_format_score = 0.0
    metadata_format_version = Version(
        "0.0.0"
    )  # to track the latest core version with valid format
    for report_path in get_all_tool_report_paths(item.id, v.version):
        tool, tool_version = report_path.stem.split("_", 1)
        tool = tool.lower()
        if tool not in TOOL_NAMES:
            warnings.warn(f"Report {report_path} has unknown tool name '{tool}'.")
            continue
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            report = ToolCompatibilityReport(
                tool=tool, tool_version=tool_version, **data
            )
        except Exception as e:
            report = ToolCompatibilityReport(
                tool=tool,
                tool_version=tool_version,
                status="failed",
                error=str(e),
                score=0.0,
                details="Failed to parse compatibility report.",
            )

        scores[f"{tool}_{tool_version}"] = report.score
        reports.append(report)
        if report.tool == "bioimageio.core" and isinstance(
            report.details, ToolReportDetails
        ):
            # select the best completeness score among core reports
            metadata_completeness = max(
                metadata_completeness, report.details.metadata_completeness or 0.0
            )
            # determine metadata format score
            # - valid-format for latest core report: 1.0
            # - valid-format for older core report: 0.5
            # - invalid format for all core reports: 0.0
            core_version = Version(tool_version)
            if core_version >= metadata_format_version:
                metadata_format_version = core_version
                if report.details.status in ("passed", "valid-format"):
                    metadata_format_score = 1.0
                else:
                    metadata_format_score = 0.5 if metadata_format_score else 0.0

            elif not metadata_format_score and report.details.status in (
                "passed",
                "valid-format",
            ):
                metadata_format_score = 0.5

    tests: Dict[ToolName, Dict[str, ToolCompatibilityReport]] = {}
    for r in reports:
        tests.setdefault(r.tool, {})[r.tool_version] = r

    compatibility_scores = CompatibilityScores(
        tool_compatibility_version_specific=scores,
        metadata_completeness=metadata_completeness,
        metadata_format=metadata_format_score,
    )

    compatibility_status = (
        "passed"
        if compatibility_scores.tool_compatibility
        and max(compatibility_scores.tool_compatibility.values()) >= 0.5
        else "failed"
    )
    summary = CompatibilitySummary(
        rdf_content=initial_summary.rdf_content,
        rdf_yaml_sha256=initial_summary.rdf_yaml_sha256,
        status=compatibility_status,
        scores=compatibility_scores,
        tests=tests,
    )

    json_dict = summary.model_dump(mode="json")
    with get_summary_file_path(item.id, v.version).open("wt", encoding="utf-8") as f:
        json.dump(json_dict, f, indent=4, sort_keys=True, ensure_ascii=False)
    # TODO: use .model_dump_json once it supports 'sort_keys' argument for a potential speed gain
    # _ = get_summary_file_path(item.id, v.version).write_text(
    #     summary.model_dump_json(indent=4), encoding="utf-8"
    # )

    logger.info(
        "summarized {} version {} with {} reports, status: {}, metadata completeness: {:.2f}",
        item.id,
        v.version,
        len(reports),
        compatibility_status,
        metadata_completeness,
    )


if __name__ == "__main__":
    summarize_reports()
