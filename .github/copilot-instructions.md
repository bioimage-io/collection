# Copilot instructions for bioimage-io/collection

Purpose and architecture
- This repo hosts the “backoffice” CLI that indexes bioimage.io resources from Hypha and aggregates tool-compatibility reports. Code lives in `src/backoffice` and exposes `backoffice` as a console script.
- Data flow:
  1) `backoffice index` calls Hypha list API and creates `index.json` with all items and versions, fetching each `rdf.yaml` and seeding a per-version `summary.json` under a report folder.
  2) Tool jobs write JSON reports to `reports/<id>/<version>/reports/<tool>_<version>.json` (see `utils_pure.get_tool_report_path`).
  3) `backoffice summarize` reads those reports and rewrites each `<id>/<version>/summary.json` with scores and details.
- Environment variables: `HYPHA_API_TOKEN` (required), `REPORTS` (defaults to `reports`; CI uses `gh-pages/reports`), `HTTP_TIMEOUT`.

Key modules and contracts (Python)
- CLI: `backoffice.__main__` -> `_cli.Backoffice` with subcommands:
  - `index` -> `index.create_index()`; writes `index.json` and initializes report dirs.
  - `summarize` -> `_summarize.summarize_reports()`; aggregates per-tool reports into scores (`CompatibilitySummary`).
- Report format: `compatibility.py` defines `ToolCompatibilityReport`, `CompatibilityScores`, `CompatibilitySummary` (pydantic). Use `.model_dump(mode="json")` when writing.
- Paths: `utils_pure.get_report_path(id, ver)` and `get_tool_report_path(id, ver, tool, tool_ver)` build locations. Note: tool name/version must not contain `_` (enforced).
- Networking: `index._initialize_report_directory` fetches `rdf.yaml`; use `utils_pure.raise_for_status_discretely` to log HTTP errors without leaking query/userinfo.

Tool compatibility scripts (examples)
- bioimageio.core: `scripts/check_compatibility_bioimageio_core.py` uses `bioimageio.core.test_description` and `check_compatibility.check_tool_compatibility` helper.
- ilastik: `scripts/check_compatibility_ilastik.py` validates single-input/output and delegates tests to `bioimageio.core.test_model` (with fallbacks for older core).
- BiaPy: `scripts/check_compatibility_biapy.py` loads RDF via `utils.get_rdf_content_from_url` and calls `biapy.models.check_bmz_model_compatibility`.
- CAREamics: `scripts/check_compatibility_careamics.py` loads BMZ, checks attachments (expects `careamics.yaml`), attempts predict via `CAREamist`.

Local workflows
- Install dev env: `pip install -e .[dev]` (ruff, pyright, pytest) or minimal CLI: `pip install .`.
- Export token: add `.env` with `HYPHA_API_TOKEN=...` or export in shell. Optional: `REPORTS=gh-pages/reports` to mirror CI layout.
- Generate index: `backoffice index` (writes `index.json` and initializes `<reports>/<id>/<ver>/summary.json`).
- Run a tool check: e.g. `python scripts/check_compatibility_bioimageio_core.py` (writes JSON under `reports/.../reports/`).
- Summarize: `backoffice summarize` to aggregate scores into each `summary.json`.
# Compatibility Reports Overview

This page displays compatibility reports for all resources in the bioimage.io collection.

The overview is dynamically generated from the latest index and summary reports.

```python exec="1" source="above"
import sys
from pathlib import Path

# Ensure the script can find backoffice module
project_root = Path(__file__).parent.parent if hasattr(__file__, 'parent') else Path.cwd()

# Add src to path so we can import backoffice
sys.path.insert(0, str(project_root / "src"))

# Now we can import from scripts
exec(open(project_root / "scripts" / "generate_reports_overview.py").read())

# Generate the overview
generate_reports_overview(
    index_path=project_root / "gh-pages" / "index.json",
    output_path=project_root / "docs" / "_reports_generated.md",
)

# Display the content (skip first header)
with open(project_root / "docs" / "_reports_generated.md", encoding="utf-8") as f:
    lines = f.readlines()
    # Skip title since we have one above
    print("".join(lines[2:]))
```
- Generate docs overview: `python scripts/generate_reports_overview.py` to create `docs/reports_overview.md` from index and summaries.
- Tests/lint/typecheck: `ruff check`; `pyright -p pyproject.toml`; `pytest` (see `tests/test_utils_plain.py`).
- Docs: `pip install -e .[docs]` then `mkdocs serve` locally; CI deploys with `mike` (see `mkdocs.yml`).

CI/CD overview (GitHub Actions)
- `index.yaml`: builds fresh `index.json` and stages report deletions when RDF hashes change.
- `check_compatibility_*.yaml`: run tool-specific scripts, restore prior reports via composite action `.github/actions/restore_reports`, and stage new ones.
- `check_compatibility.yaml`: orchestrates index -> tool checks -> `backoffice summarize` -> deploy to `gh-pages`.

Conventions and pitfalls
- Report naming: `<tool>_<semver>.json`; underscores in names/versions are rejected by `get_tool_report_path`.
- Only operate on supported resource `type`s (scripts typically filter to `model`). Respect SHA-256 validation when loading RDF.
- Disk space guard: `check_tool_compatibility` aborts if free space < 5GB.
- When adding a partner: add a workflow, a `scripts/check_compatibility_<tool>.py`, and integrate via `check_tool_compatibility(...)` following the existing examples.

Useful entry points/examples
- Build index: `src/backoffice/index.py:create_index`
- Aggregate: `src/backoffice/_summarize.py:summarize_reports`
- Report writing helper: `src/backoffice/check_compatibility.py:check_tool_compatibility`
- Settings and Hypha headers: `src/backoffice/_settings.py:Settings`
