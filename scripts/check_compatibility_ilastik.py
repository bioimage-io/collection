import argparse
import json
import traceback
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

import bioimageio.core
import requests

if bioimageio.core.__version__.startswith("0.5."):
    from bioimageio.core import test_resource as test_model
else:
    from bioimageio.core import test_model

from script_utils import CompatiblityReport, download_rdf

try:
    from tqdm import tqdm
except ImportError:
    tqdm = list


def check_compatibility_ilastik_impl(
    rdf_url: str,
    sha256: str,
    report_path: Path,
):
    report_path.parent.mkdir(parents=True, exist_ok=True)

    rdf = download_rdf(rdf_url, sha256)

    if rdf["type"] != "model":
        report = CompatiblityReport(
            status="not-applicable",
            error=None,
            details="only 'model' resources can be used in ilastik.",
        )

    elif len(rdf["inputs"]) > 1 or len(rdf["outputs"]) > 1:
        report = CompatiblityReport(
            status="failed",
            error=f"ilastik only supports single tensor input/output (found {len(rdf['inputs'])}/{len(rdf['outputs'])})",
            details=None,
        )
    else:
        # produce test summary with bioimageio.core
        summary = test_model(rdf_url)
        if not TYPE_CHECKING:
            if bioimageio.core.__version__.startswith("0.5."):
                summary = summary[-1]

        report = CompatiblityReport(
            status=summary.status,
            error=None if summary.status == "passed" else summary.format(),
            details=summary.model_dump(mode="json"),
            links=["ilastik/ilastik"],
        )

    with report_path.open("wt", encoding="utf-8") as f:
        json.dump(report, f)


def check_compatibility_ilastik(
    ilastik_version: str, all_version_path: Path, output_folder: Path
):
    """preliminary ilastik check

    only checks if test outputs are reproduced for onnx, torchscript, or pytorch_state_dict weights.
    # TODO: test with ilastik itself

    """
    with all_version_path.open() as f:
        all_versions = json.load(f)["entries"]

    all_model_versions = [entry for entry in all_versions if entry["type"] == "model"]

    for entry in tqdm(all_model_versions):
        for version in entry["versions"]:
            rdf_url = version["source"]
            sha256 = version["sha256"]

            report_url = (
                "/".join(rdf_url.split("/")[:-2])
                + f"/compatibility/ilastik_{ilastik_version}.yaml"
            )
            r = requests.head(report_url)
            if r.status_code != 404:
                r.raise_for_status()  # raises if failed to check if report exists
                continue  # report already exists

            report_path = (
                "/".join(rdf_url.split("/")[-4:-2])
                + f"/compatibility/ilastik_{ilastik_version}.json"
            )
            try:
                check_compatibility_ilastik_impl(
                    rdf_url, sha256, output_folder / report_path
                )
            except Exception as e:
                traceback.print_exc()
                warnings.warn(f"failed to check '{rdf_url}': {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("ilastik_version")
    _ = parser.add_argument("all_versions", type=Path)
    _ = parser.add_argument("output_folder", type=Path)

    args = parser.parse_args()
    check_compatibility_ilastik(
        args.ilastik_version, args.all_versions, args.output_folder
    )
