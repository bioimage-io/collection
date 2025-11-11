from dataclasses import dataclass
from functools import partial
from io import BytesIO
from typing import Any, Dict, Optional
from typing_extensions import Protocol

import json
import os
import re
import sys
import argparse
import subprocess
import traceback
import urllib.request

import requests
from ruamel.yaml import YAML

from backoffice.check_compatibility import check_tool_compatibility
from backoffice.compatibility_pure import ToolCompatibilityReportDict

try:
    from bioimageio.spec.common import Sha256
except ImportError:
    Sha256 = str


class HasContent(Protocol):
    @property
    def content(self) -> Optional[Dict[Any, Any]]: ...


yaml = YAML(typ="safe")  # type: ignore


@dataclass
class DownloadedRDF:
    content: Optional[Dict[Any, Any]]


def open_bioimageio_yaml(
    rdf_url: str,  # TODO: make 'rdf_url' positional only
    **kwargs: Any,
) -> HasContent:
    r = requests.get(rdf_url)
    return DownloadedRDF(yaml.load(BytesIO(r.content)))  # type: ignore


def find_expected_output(outputs_dir: str, name: str) -> bool:
    for ff in os.listdir(outputs_dir):
        if ff.endswith("_" + name + ".tif") or ff.endswith("_" + name + ".tiff"):
            return True
    return False


def check_dij_macro_generated_outputs(model_dir: str):
    json_outs_name = os.getenv("JSON_OUTS_FNAME")
    assert json_outs_name is not None, "JSON_OUTS_FNAME environment variable not set"
    with open(os.path.join(model_dir, json_outs_name), "r") as f:
        expected_outputs = json.load(f)

        for output in expected_outputs:
            name = output["name"]
            dij_output = output["dij"]
            if not os.path.exists(dij_output):
                return False
            if not find_expected_output(dij_output, name):
                return False
    return True


def remove_processing_and_halo(model_dir: str):
    data = None
    with open(os.path.join(model_dir, "rdf.yaml")) as stream:
        data = yaml.load(stream)
    for out in data["outputs"]:
        if not isinstance(out["axes"][0], dict):
            out.pop("halo", None)
            continue
        for ax in out["axes"]:
            ax.pop("halo", None)
    with open(os.path.join(model_dir, "rdf.yaml"), "w") as outfile:
        yaml.dump(data, outfile)


def test_model_deepimagej(
    rdf_url: str, fiji_executable: str, fiji_path: str, deepimagej_version: str
) -> ToolCompatibilityReportDict:
    yaml_file = os.path.abspath("rdf.yaml")
    try:
        _ = urllib.request.urlretrieve(rdf_url, yaml_file)
    except Exception as e:
        report = ToolCompatibilityReportDict(
            status="failed",
            error="unable to download the yaml file",
            details=f"{e.stderr}{os.linesep}{e.stdout}"
            if isinstance(e, subprocess.CalledProcessError)
            else traceback.format_exc(),
            links=["deepimagej/deepimagej"],
            badge=None,
        )
        return report
    try:
        _ = subprocess.run(
            [
                fiji_executable,
                "--headless",
                "--console",
                "scripts/deepimagej_jython_scripts/deepimagej_read_yaml.py",
                "-yaml_fpath",
                yaml_file,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except BaseException as e:
        report = ToolCompatibilityReportDict(
            status="failed",
            error="unable to read the yaml file",
            details=f"{e.stderr}{os.linesep}{e.stdout}"
            if isinstance(e, subprocess.CalledProcessError)
            else traceback.format_exc(),
            links=["deepimagej/deepimagej"],
            badge=None,
        )
        return report
    model_dir = None
    try:
        download_result = subprocess.run(
            [
                fiji_executable,
                "--headless",
                "--console",
                "scripts/deepimagej_jython_scripts/deepimagej_download_model.py",
                "-yaml_fpath",
                yaml_file,
                "-models_dir",
                os.path.join(fiji_path, "models"),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        model_dir = download_result.stdout.strip().splitlines()[-1]
    except BaseException as e:
        report = ToolCompatibilityReportDict(
            status="failed",
            error="unable to download the model",
            details=f"{e.stderr}{os.linesep}{e.stdout}"
            if isinstance(e, subprocess.CalledProcessError)
            else traceback.format_exc(),
            links=["deepimagej/deepimagej"],
            badge=None,
        )
        return report
    remove_processing_and_halo(model_dir)
    macro_path = os.path.join(model_dir, str(os.getenv("MACRO_NAME")))
    try:
        run = subprocess.run(
            [
                fiji_executable,
                "--headless",
                "--console",
                "-macro",
                macro_path,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out_str = run.stdout
        if not check_dij_macro_generated_outputs(model_dir):
            report = ToolCompatibilityReportDict(
                status="failed",
                error="error running the model",
                details=out_str,
                links=["deepimagej/deepimagej"],
                badge=None,
            )
            return report
    except BaseException as e:
        report = ToolCompatibilityReportDict(
            status="failed",
            error="error running the model",
            details=f"{e.stderr}{os.linesep}{e.stdout}"
            if isinstance(e, subprocess.CalledProcessError)
            else traceback.format_exc(),
            links=["deepimagej/deepimagej"],
            badge=None,
        )
        return report
    try:
        _ = subprocess.run(
            [
                fiji_executable,
                "--headless",
                "--console",
                "scripts/deepimagej_jython_scripts/deepimagej_check_outputs.py",
                "-model_dir",
                model_dir,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except BaseException as e:
        report = ToolCompatibilityReportDict(
            status="failed",
            error="error comparing expected outputs and actual outputs",
            details=f"{e.stderr}{os.linesep}{e.stdout}"
            if isinstance(e, subprocess.CalledProcessError)
            else traceback.format_exc(),
            links=["deepimagej/deepimagej"],
            badge=None,
        )
        return report
    report = ToolCompatibilityReportDict(
        status="passed",
        error=None,
        details=None,
        links=["deepimagej/deepimagej"],
        badge=None,
    )
    return report


def check_compatibility_deepimagej_impl(
    item_id: str,
    item_version: str,
    rdf_url: str,
    sha256: str,
    fiji_executable: str,
    fiji_path: str,
    deepimagej_version: str,
) -> ToolCompatibilityReportDict:
    """Create a `CompatibilityReport` for a resource description.

    Args:
        rdf_url: URL to the rdf.yaml file
        sha256: SHA-256 value of **rdf_url** content
    """
    print(item_id, item_version, file=sys.stderr)
    assert fiji_executable != "", "please provide the fiji executable path"

    rdf = open_bioimageio_yaml(rdf_url, sha256=Sha256(sha256)).content

    if rdf["type"] != "model":
        report = ToolCompatibilityReportDict(
            status="not-applicable",
            error=None,
            details="only 'model' resources can be used in deepimagej.",
            links=["deepimagej/deepimagej"],
            badge=None,
        )

    elif len(rdf["inputs"]) > 1:  # or len(rdf["outputs"]) > 1:
        report = ToolCompatibilityReportDict(
            status="failed",
            # error=f"deepimagej only supports single tensor input/output (found {len(rdf['inputs'])}/{len(rdf['outputs'])})",
            error=f"deepimagej only supports single tensor input (found {len(rdf['inputs'])})",
            details=None,
            links=["deepimagej/deepimagej"],
            badge=None,
        )
    else:
        report = test_model_deepimagej(
            rdf_url, fiji_executable, fiji_path, deepimagej_version
        )

    return report


def check_compatibility_deepimagej(
    deepimagej_version: str,
    fiji_executable: str,
    fiji_path: str,
):
    partial_impl = partial(
        check_compatibility_deepimagej_impl,
        fiji_executable=fiji_executable,
        fiji_path=fiji_path,
        deepimagej_version=deepimagej_version,
    )
    check_tool_compatibility(
        "deepimagej",
        deepimagej_version,
        check_tool_compatibility_impl=partial_impl,
        applicable_types={"model"},
    )


def get_dij_version(fiji_path: str):
    plugins_path = os.path.join(fiji_path, "plugins")
    pattern = re.compile(r"^deepimagej-(\d+\.\d+\.\d+(?:-snapshot)?)\.jar$")

    matching_files = [
        file.lower() for file in os.listdir(plugins_path) if pattern.match(file.lower())
    ]
    assert len(matching_files) > 0, (
        "No deepImageJ plugin found, review your installation"
    )
    version_match = pattern.search(matching_files[0])
    assert version_match is not None, "Could not extract deepImageJ version"
    version = version_match.group(1)
    return version


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("fiji_executable", type=str)
    _ = parser.add_argument("fiji_path", type=str)

    args = parser.parse_args()
    fiji_path = os.path.abspath(args.fiji_path)
    check_compatibility_deepimagej(
        get_dij_version(fiji_path),
        fiji_executable=args.fiji_executable,
        fiji_path=fiji_path,
    )
