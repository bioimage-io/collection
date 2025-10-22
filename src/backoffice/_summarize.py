import json
import warnings
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any

from loguru import logger
from tqdm import tqdm

from backoffice.compatibility import (
    TOOL_NAMES,
    CompatibilityScores,
    CompatibilitySummary,
    ToolCompatibilityReport,
    ToolNameVersioned,
    ToolReportDetails,
)
from backoffice.index import IndexItem, IndexItemVersion, create_index
from backoffice.utils import (
    get_all_tool_report_paths,
    get_summary,
    get_summary_file_path,
)


def summarize_reports():
    index = create_index()
    with ThreadPoolExecutor() as executor:
        futures: list[Future[Any]] = []
        for item in index.items:
            for v in item.versions:
                futures.append(executor.submit(_summarize, item, v))

        for _ in tqdm(as_completed(futures), total=len(futures)):
            pass


def _summarize(item: IndexItem, v: IndexItemVersion):
    """Conflate all summaries for a given item version."""

    initial_summary = get_summary(item.id, v.version)

    reports: list[ToolCompatibilityReport] = []
    scores: dict[ToolNameVersioned, float] = {}
    status = "failed"
    metadata_completeness = 0.0
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
        else:
            if report.tool == "bioimageio.core" and status == "passed":
                status = "passed"

        reports.append(report)
        if report.tool == "bioimageio.spec" and isinstance(
            report.details, ToolReportDetails
        ):
            metadata_completeness = report.details.metadata_completeness or 0.0

    summary = CompatibilitySummary(
        rdf_content=initial_summary.rdf_content,
        rdf_yaml_sha256=initial_summary.rdf_yaml_sha256,
        status=status,
        scores=CompatibilityScores(
            tool_compatibility_version_specific=scores,
            metadata_completeness=metadata_completeness,
        ),
        tests={report.report_name: report for report in reports},
    )

    _ = get_summary_file_path(item.id, v.version).write_text(
        summary.model_dump_json(indent=4), encoding="utf-8"
    )
    logger.info(
        "summarized {} version {} with {} reports, status: {}, metadata completeness: {:.2f}",
        item.id,
        v.version,
        len(reports),
        status,
        metadata_completeness,
    )
