import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from respx import MockRouter

from backoffice.compatibility import (
    CompatibilityScores,
    ToolCompatibilityReportWithToolInfo,
)
from scripts.check_compatibility_eosc import (
    LOADER_URL,
    RESULTS_URL,
    check_compatibility_eosc,
    check_compatibility_eosc_impl,
)


@pytest.mark.parametrize(
    "item_id,version,sha256,expected",
    [
        ("bioimage-io/example", "v1", "a" * 64, "passed"),
        ("bioimage-io/example", "v0", "a" * 64, "failed"),
        ("bioimage-io/example", "v1", "b" * 64, "failed"),
        ("other/example", "v1", "a" * 64, "failed"),
    ],
)
def test_eosc_matches_exact_resource(
    item_id: str, version: str, sha256: str, expected: str
):
    report = check_compatibility_eosc_impl(
        item_id,
        version,
        "https://example.com/rdf.yaml",
        sha256,
        compatible_models={("bioimage-io/example", "v1", "a" * 64)},
    )
    assert report.status == expected
    assert report.score == (1.0 if expected == "passed" else 0.0)
    assert (report.error is None) == (expected == "passed")


@pytest.fixture
def eosc_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    reports = tmp_path / "reports"
    monkeypatch.setenv("REPORTS", str(reports))
    item = {
        "id": "bioimage-io/example",
        "type": "model",
        "versions": [
            {
                "version": version,
                "source": "https://example.com/rdf.yaml",
                "sha256": "a" * 64,
            }
            for version in ("v1", "v0")
        ],
    }
    _ = (tmp_path / "index.json").write_text(
        json.dumps({"items": [item, dict(item, id="example-app", type="application")]}),
        encoding="utf-8",
    )
    return reports


def test_eosc_import_and_refresh(eosc_reports: Path, respx_mock: MockRouter):
    _ = respx_mock.get(f"{LOADER_URL}/VERSION").respond(200, text="0.0.1\n")
    results = respx_mock.get(RESULTS_URL).respond(
        200,
        json={
            "example 🦀": {
                "id": "example",
                "collection_id": "bioimage-io/example",
                "version": "v1",
                "sha256": "a" * 64,
                "weight_formats": ["pytorch_state_dict"],
            }
        },
    )

    check_compatibility_eosc()

    path = eosc_reports / "bioimage-io/example/v1/reports/eosc_0.0.1.json"
    report = ToolCompatibilityReportWithToolInfo.model_validate_json(path.read_text())
    assert report.tool == "eosc"
    assert report.tool_version == "0.0.1"
    assert report.status == "passed"
    scores = CompatibilityScores(
        tool_compatibility_version_specific={report.report_name: report.score}
    )
    assert scores.tool_compatibility["eosc"] == 1.0
    assert scores.overall_partner_tool_compatibility == pytest.approx(1 / 3)
    previous_version = path.parents[2] / "v0/reports/eosc_0.0.1.json"
    assert json.loads(previous_version.read_text())["status"] == "failed"
    assert not (eosc_reports / "example-app").exists()

    _ = results.respond(200, json={})
    check_compatibility_eosc()
    assert json.loads(path.read_text())["status"] == "failed"


@pytest.mark.parametrize(
    "status_code,payload,error",
    [
        (503, {}, httpx.HTTPStatusError),
        (200, [], ValidationError),
        (200, {"example 🦀": {"id": "example"}}, ValidationError),
    ],
)
def test_eosc_rejects_invalid_results_before_writing_reports(
    eosc_reports: Path,
    respx_mock: MockRouter,
    status_code: int,
    payload: object,
    error: type[Exception],
):
    _ = respx_mock.get(f"{LOADER_URL}/VERSION").respond(200, text="0.0.1")
    _ = respx_mock.get(RESULTS_URL).respond(status_code, json=payload)
    with pytest.raises(error):
        check_compatibility_eosc()

    assert not eosc_reports.exists()
