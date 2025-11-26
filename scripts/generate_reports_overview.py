"""Generate a markdown overview page of all compatibility reports."""

import html
import json
from pathlib import Path
from typing import Any

from backoffice.index import load_index
from backoffice.utils_pure import get_summary_file_path


def generate_html_table(
    rows: list[dict[str, Any]],
    table_id: str = "reportsTable",
    search_id: str = "searchInput",
    type_filter_id: str = "typeFilter",
    status_filter_id: str = "statusFilter",
) -> str:
    """Generate an HTML table with sorting and filtering capabilities.

    Args:
        rows: List of row dictionaries with resource data
        table_id: Unique ID for the table element
        search_id: Unique ID for the search input
        type_filter_id: Unique ID for the type filter
        status_filter_id: Unique ID for the status filter

    Returns:
        HTML string with table and JavaScript
    """
    # Start HTML with styles and filter controls
    html_parts = [
        '<div class="reports-table-container">',
        "<style>",
        ".reports-table-container { margin: 20px 0; }",
        ".filter-controls { margin-bottom: 15px; display: flex; gap: 10px; flex-wrap: wrap; }",
        ".filter-controls input, .filter-controls select { padding: 5px 10px; border: 1px solid var(--md-default-fg-color--lighter, #ccc); border-radius: 4px; background: var(--md-default-bg-color, white); color: var(--md-default-fg-color, black); }",
        ".reports-table { width: 100%; border-collapse: collapse; font-size: 14px; }",
        ".reports-table th { background: var(--md-code-bg-color, #f5f5f5); color: var(--md-default-fg-color, black); padding: 10px; text-align: left; cursor: pointer; user-select: none; border-bottom: 2px solid var(--md-default-fg-color--lighter, #ddd); }",
        ".reports-table th:hover { background: var(--md-code-hl-color, #e8e8e8); }",
        '.reports-table th.sorted-asc::after { content: " ↑"; }',
        '.reports-table th.sorted-desc::after { content: " ↓"; }',
        ".reports-table td { padding: 8px 10px; border-bottom: 1px solid var(--md-default-fg-color--lightest, #eee); }",
        ".reports-table tr:hover { background: var(--md-code-bg-color, #f9f9f9); }",
        ".status-passed { color: #22863a; font-weight: 600; }",
        ".status-failed { color: #cb2431; font-weight: 600; }",
        ".status-untested { color: #6a737d; }",
        ".score-high { color: #22863a; font-weight: 600; }",
        ".score-med { color: #e36209; }",
        ".score-low { color: #cb2431; }",
        "@media (prefers-color-scheme: dark) {",
        "  .reports-table th { background: #2d2d2d; color: #e8e8e8; }",
        "  .reports-table th:hover { background: #3d3d3d; }",
        "  .reports-table tr:hover { background: #2d2d2d; }",
        "  .filter-controls input, .filter-controls select { background: #2d2d2d; color: #e8e8e8; border-color: #555; }",
        "}",
        "</style>",
        "",
        '<div class="filter-controls">',
        f'  <input type="text" id="{search_id}" placeholder="Search resources..." style="flex: 1; min-width: 200px;">',
        f'  <select id="{type_filter_id}">',
        '    <option value="">All Types</option>',
        '    <option value="model">Model</option>',
        '    <option value="application">Application</option>',
        '    <option value="dataset">Dataset</option>',
        '    <option value="notebook">Notebook</option>',
        "  </select>",
        f'  <select id="{status_filter_id}">',
        '    <option value="">All Statuses</option>',
        '    <option value="passed">Passed</option>',
        '    <option value="failed">Failed</option>',
        '    <option value="untested">Untested</option>',
        "  </select>",
        "</div>",
        "",
        f'<table class="reports-table" id="{table_id}">',
        "  <thead>",
        "    <tr>",
        '      <th data-sort="id">Resource ID / Version</th>',
        '      <th data-sort="type">Type</th>',
        '      <th data-sort="status">Status</th>',
        '      <th data-sort="metadata">Metadata</th>',
        '      <th data-sort="core">Core</th>',
        '      <th data-sort="overall">Overall</th>',
        '      <th data-sort="tools">Partner Tools</th>',
        "    </tr>",
        "  </thead>",
        "  <tbody>",
    ]

    # Add table rows
    for row in rows:
        status_class = f"status-{row['status']}"

        # Determine score color classes
        core_val = row["core"]
        core_class = (
            "score-high"
            if core_val >= 0.7
            else ("score-med" if core_val >= 0.3 else "score-low")
        )

        overall_val = row["overall"]
        overall_class = (
            "score-high"
            if overall_val >= 0.7
            else ("score-med" if overall_val >= 0.3 else "score-low")
        )

        metadata_val = row["metadata"]
        metadata_class = (
            "score-high"
            if metadata_val >= 0.7
            else ("score-med" if metadata_val >= 0.3 else "score-low")
        )

        # Create hyperlink to bioimage.io with version
        resource_link = f"https://bioimage.io/#/artifacts/{html.escape(row['id'])}/{html.escape(row['version'])}"
        id_html = f'<a href="{resource_link}" target="_blank">{html.escape(row["id"])}/{html.escape(row["version"])}</a>'

        html_parts.extend(
            [
                "    <tr>",
                f"      <td>{id_html}</td>",
                f"      <td>{html.escape(row['type'])}</td>",
                f'      <td class="{status_class}">{html.escape(row["status"])}</td>',
                f'      <td class="{metadata_class}" data-value="{metadata_val}">{html.escape(row["metadata_str"])}</td>',
                f'      <td class="{core_class}" data-value="{core_val}">{html.escape(row["core_str"])}</td>',
                f'      <td class="{overall_class}" data-value="{overall_val}">{html.escape(row["overall_str"])}</td>',
                f"      <td>{html.escape(row['tools'])}</td>",
                "    </tr>",
            ]
        )

    # Close table and add JavaScript
    html_parts.extend(
        [
            "  </tbody>",
            "</table>",
            "",
            "<script>",
            "(function() {",
            f'  const table = document.getElementById("{table_id}");',
            '  const tbody = table.querySelector("tbody");',
            '  const headers = table.querySelectorAll("th[data-sort]");',
            f'  const searchInput = document.getElementById("{search_id}");',
            f'  const typeFilter = document.getElementById("{type_filter_id}");',
            f'  const statusFilter = document.getElementById("{status_filter_id}");',
            "  ",
            '  let currentSort = { column: null, direction: "asc" };',
            '  let allRows = Array.from(tbody.querySelectorAll("tr"));',
            "  ",
            "  // Sorting functionality",
            "  headers.forEach(header => {",
            '    header.addEventListener("click", () => {',
            "      const sortKey = header.dataset.sort;",
            '      const direction = currentSort.column === sortKey && currentSort.direction === "asc" ? "desc" : "asc";',
            "      ",
            '      headers.forEach(h => h.className = "");',
            '      header.className = direction === "asc" ? "sorted-asc" : "sorted-desc";',
            "      ",
            "      currentSort = { column: sortKey, direction };",
            "      sortTable(sortKey, direction);",
            "    });",
            "  });",
            "  ",
            "  function sortTable(column, direction) {",
            "    const sortedRows = [...allRows].sort((a, b) => {",
            "      let aVal, bVal;",
            "      const aCell = a.children[getColumnIndex(column)];",
            "      const bCell = b.children[getColumnIndex(column)];",
            "      ",
            '      if (column === "core" || column === "overall" || column === "metadata") {',
            "        aVal = parseFloat(aCell.dataset.value) || 0;",
            "        bVal = parseFloat(bCell.dataset.value) || 0;",
            "      } else {",
            "        aVal = aCell.textContent.toLowerCase();",
            "        bVal = bCell.textContent.toLowerCase();",
            "      }",
            "      ",
            '      if (aVal < bVal) return direction === "asc" ? -1 : 1;',
            '      if (aVal > bVal) return direction === "asc" ? 1 : -1;',
            "      return 0;",
            "    });",
            "    ",
            '    tbody.innerHTML = "";',
            "    sortedRows.forEach(row => tbody.appendChild(row));",
            "    allRows = sortedRows;",
            "  }",
            "  ",
            "  function getColumnIndex(column) {",
            "    const map = { id: 0, type: 1, status: 2, metadata: 3, core: 4, overall: 5, tools: 6 };",
            "    return map[column];",
            "  }",
            "  ",
            "  // Filtering functionality",
            "  function filterTable() {",
            "    const searchTerm = searchInput.value.toLowerCase();",
            "    const typeValue = typeFilter.value;",
            "    const statusValue = statusFilter.value;",
            "    ",
            "    allRows.forEach(row => {",
            "      const id = row.children[0].textContent.toLowerCase();",
            "      const type = row.children[1].textContent.toLowerCase();",
            "      const status = row.children[2].textContent.toLowerCase();",
            "      ",
            "      const matchesSearch = id.includes(searchTerm);",
            "      const matchesType = !typeValue || type === typeValue;",
            "      const matchesStatus = !statusValue || status === statusValue;",
            "      ",
            '      row.style.display = matchesSearch && matchesType && matchesStatus ? "" : "none";',
            "    });",
            "  }",
            "  ",
            '  searchInput.addEventListener("input", filterTable);',
            '  typeFilter.addEventListener("change", filterTable);',
            '  statusFilter.addEventListener("change", filterTable);',
            "})();",
            "</script>",
            "",
            "</div>",
        ]
    )

    return "\n".join(html_parts)


def generate_reports_overview(
    index_path: Path = Path("gh-pages/index.json"),
    output_path: Path = Path("docs/reports_overview.md"),
) -> None:
    """Generate a markdown page with compatibility report overview.

    Args:
        index_path: Path to index.json
        output_path: Path to write the markdown overview
    """
    index = load_index(index_path)

    items = index.items

    # Start building markdown
    lines = [
        "<!-- This file is auto-generated by scripts/generate_reports_overview.py. Do not edit manually. -->",
        "",
        "# Compatibility Reports Overview",
        "",
        f"This page provides an overview of all {index.total} resources in the bioimage.io collection.",
        "",
        f"*Last updated: {index.timestamp.isoformat(timespec='minutes')}*",
        "",
    ]

    # Group resources by prefix and collect statistics by type
    resources_by_prefix: dict[str, list[dict[str, Any]]] = {}
    stats_by_type: dict[str, dict[str, Any]] = {}

    for item in items:
        item_id = item.id
        item_type = item.type

        # Get latest version
        if not item.versions:
            continue

        latest_version = item.versions[0].version

        # Load summary
        summary_path = get_summary_file_path(item_id, latest_version)
        assert summary_path.exists(), summary_path
        with summary_path.open(encoding="utf-8") as f:
            summary: dict[str, Any] = json.load(f)

        # Extract scores
        scores = summary.get("scores", {})
        status = summary.get("status", "unknown")

        core_compat = scores.get("core_compatibility", 0.0)
        overall_compat = scores.get("overall_compatibility", 0.0)
        metadata_completeness = scores.get("metadata_completeness", 0.0)

        # Collect statistics by type
        if item_type not in stats_by_type:
            stats_by_type[item_type] = {
                "count": 0,
                "passed": 0,
                "metadata_scores": [],
                "core_scores": [],
                "overall_scores": [],
                "biapy_scores": [],
                "careamics_scores": [],
                "ilastik_scores": [],
            }
        stats_by_type[item_type]["count"] += 1
        if status == "passed":
            stats_by_type[item_type]["passed"] += 1
        stats_by_type[item_type]["metadata_scores"].append(metadata_completeness)
        stats_by_type[item_type]["core_scores"].append(core_compat)
        stats_by_type[item_type]["overall_scores"].append(overall_compat)

        # Get tool compatibility summary
        tool_compat = scores.get("tool_compatibility", {})
        tool_summary_parts: list[str] = []
        for tool_name in ["biapy", "careamics", "ilastik"]:
            if tool_name in tool_compat:
                score = tool_compat[tool_name]
                tool_summary_parts.append(f"{tool_name}: {score:.2f}")
                stats_by_type[item_type][f"{tool_name}_scores"].append(score)

        tool_summary = ", ".join(tool_summary_parts) if tool_summary_parts else "—"

        # Extract prefix and short ID
        if "/" in item_id:
            prefix, short_id = item_id.split("/", 1)
        else:
            prefix = ""
            short_id = item_id

        row_data = {
            "id": short_id,  # Use short ID without prefix
            "full_id": item_id,  # Keep full ID for reference
            "type": item_type,
            "version": latest_version,
            "status": status,
            "metadata": metadata_completeness,
            "metadata_str": f"{metadata_completeness:.2f}",
            "core": core_compat,
            "core_str": f"{core_compat:.2f}",
            "overall": overall_compat,
            "overall_str": f"{overall_compat:.2f}",
            "tools": tool_summary,
        }

        if prefix not in resources_by_prefix:
            resources_by_prefix[prefix] = []
        resources_by_prefix[prefix].append(row_data)

    # Generate summary by type table
    lines.extend(
        [
            "## Summary by Type",
            "",
            "| Type | Count | % Passed | Avg Metadata | Avg Core | Avg Overall | Avg BiaPy | Avg CAREamics | Avg ilastik |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for resource_type in sorted(stats_by_type.keys()):
        stats = stats_by_type[resource_type]
        count = stats["count"]
        passed = stats["passed"]
        pass_percentage = (passed / count * 100) if count > 0 else 0

        metadata_scores = stats["metadata_scores"]
        avg_metadata = (
            sum(metadata_scores) / len(metadata_scores) if metadata_scores else 0
        )

        core_scores = stats["core_scores"]
        avg_core = sum(core_scores) / len(core_scores) if core_scores else 0

        overall_scores = stats["overall_scores"]
        avg_overall = sum(overall_scores) / len(overall_scores) if overall_scores else 0

        biapy_scores = stats["biapy_scores"]
        avg_biapy = sum(biapy_scores) / len(biapy_scores) if biapy_scores else 0

        careamics_scores = stats["careamics_scores"]
        avg_careamics = (
            sum(careamics_scores) / len(careamics_scores) if careamics_scores else 0
        )

        ilastik_scores = stats["ilastik_scores"]
        avg_ilastik = sum(ilastik_scores) / len(ilastik_scores) if ilastik_scores else 0

        lines.append(
            f"| {resource_type} | {count} | {pass_percentage:.1f}% | {avg_metadata:.2f} | {avg_core:.2f} | {avg_overall:.2f} | {avg_biapy:.2f} | {avg_careamics:.2f} | {avg_ilastik:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Compatibility by Resource",
            "",
            "The following tables show compatibility test results for each resource. Click column headers to sort.",
            "",
        ]
    )

    # Generate a table for each prefix
    for idx, (prefix, rows) in enumerate(sorted(resources_by_prefix.items())):
        prefix_display = prefix if prefix else "No Prefix"
        lines.append(f"### {prefix_display}")
        lines.append("")
        lines.append(f"*{len(rows)} resources*")
        lines.append("")

        # Generate unique IDs for this table's elements
        table_id = f"reportsTable{idx}"
        search_id = f"searchInput{idx}"
        type_filter_id = f"typeFilter{idx}"
        status_filter_id = f"statusFilter{idx}"

        html_table = generate_html_table(
            rows, table_id, search_id, type_filter_id, status_filter_id
        )
        lines.append(html_table)
        lines.append("")

    lines.extend(
        [
            "",
            "## Legend",
            "",
            "- **Metadata**: Metadata completeness score (0.0-1.0)",
            "- **Core**: bioimageio.core compatibility score (0.0-1.0)",
            "- **Overall**: Overall compatibility score across all tools (0.0-1.0)",
            "- **Partner Tools**: Compatibility scores for partner tools (biapy, careamics, ilastik)",
            "",
        ]
    )

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _ = output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated reports overview at {output_path}")


if __name__ == "__main__":
    generate_reports_overview()
