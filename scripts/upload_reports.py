import json
import warnings
from pathlib import Path
from typing import Any, Dict, Union

import fire
from ruyaml import YAML

from bioimageio_collection_backoffice.db_structure.compatibility import (
    CompatiblityReport,
)
from bioimageio_collection_backoffice.remote_collection import (
    get_remote_resource_version,
)
from bioimageio_collection_backoffice.s3_client import Client

yaml = YAML(typ="safe")


def upload_reports(reports: Path):
    client = Client()
    for p in reports.glob("*/*/compatibility/*"):
        concept, version, _, tool_file_name = p.as_posix().split("/")
        tool = tool_file_name[: -len(".yaml")]

        if p.suffix in (".yml", ".yaml"):
            with p.open("rt", encoding="utf-8") as f:
                report_data: Union[Any, Dict[Any, Any]] = yaml.load(f)
        elif p.suffix in (".json"):
            with p.open("rt", encoding="utf-8") as f:
                report_data = json.load(f)
        else:
            warnings.warn(f"ignoring '{p}' for its unknown suffix.")
            continue

        assert isinstance(report_data, dict)
        report = CompatiblityReport(tool=tool, **report_data)

        record = get_remote_resource_version(
            client=client, concept_id=concept, version=version
        )
        record.set_compatibility_report(report)


if __name__ == "__main__":
    fire.Fire(upload_reports)
