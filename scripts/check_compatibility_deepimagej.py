import argparse
from pathlib import Path
from typing import List, Dict, Any
import os
import re

import urllib.request
import subprocess
from functools import partial
import traceback

from script_utils import CompatibilityReportDict, check_tool_compatibility, download_rdf


def test_model_deepimagej(rdf_url: str, fiji_executable: str, fiji_path: str):
    yaml_file = "rdf.yaml"
    try:
        urllib.request.urlretrieve(rdf_url, yaml_file)
    except Exception as e:
        report = CompatibilityReportDict(
                status="failed",
                error=f"unable to download the yaml file",
                details=traceback.format_exc(),
                links=["deepimagej/deepimagej"],
            ) 
        return report
    try:
        read_yaml = subprocess.run(
        [
            fiji_executable,
            "--headless",
            "--console",
            "scripts/deepimagej_jython_scripts/deepimagej_read_yaml.py",
            "-yaml_fpath",
            yaml_file
        ],
        check=True,
        stdout=subprocess.PIPE,
        text=True
        )
        print('hereeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee')
        printed_output = read_yaml.stdout
        print("Subprocess Output:\n", printed_output)
    except BaseException as e:
        report = CompatibilityReportDict(
                status="failed",
                error=f"unable to read the yaml file",
                details=traceback.format_exc(),
                links=["deepimagej/deepimagej"],
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
            os.path.join(fiji_path, 'models')
        ],
        check=True,
        stdout=subprocess.PIPE,
        text=True
        )
        model_dir = download_result.stdout.strip().splitlines()[-1]
    except BaseException as e:
        report = CompatibilityReportDict(
                status="failed",
                error=f"unable to download the model",
                details=traceback.format_exc(),
                links=["deepimagej/deepimagej"],
            ) 
        return report
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
            text=True
        )
    except BaseException as e:
        report = CompatibilityReportDict(
                status="failed",
                error=f"error running the model",
                details=traceback.format_exc(),
                links=["deepimagej/deepimagej"],
            ) 
        return report
    try:
        check_outputs = subprocess.run(
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
        text=True
        )
    except BaseException as e:
        report = CompatibilityReportDict(
                status="failed",
                error=f"error comparing expected outputs and actual outputs",
                details=traceback.format_exc(),
                links=["deepimagej/deepimagej"],
            ) 
        return report
    report = CompatibilityReportDict(
            status="passed",
            error=None,
            details=None,
            links=["deepimagej/deepimagej"],
        ) 
    return report






def check_compatibility_deepimagej_impl(
    rdf_url: str,
    sha256: str,
    fiji_executable: str = "",
    fiji_path: str = "fiji",
) -> CompatibilityReportDict:
    """Create a `CompatibilityReport` for a resource description.

    Args:
        rdf_url: URL to the rdf.yaml file
        sha256: SHA-256 value of **rdf_url** content
    """
    assert fiji_executable != "", "please provide the fiji executable path"

    rdf = download_rdf(rdf_url, sha256)

    if rdf["type"] != "model":
        report = CompatibilityReportDict(
            status="not-applicable",
            error=None,
            details="only 'model' resources can be used in deepimagej.",
            links=["deepimagej/deepimagej"],
        )

    elif len(rdf["inputs"]) > 1 or len(rdf["outputs"]) > 1:
        report = CompatibilityReportDict(
            status="failed",
            error=f"deepimagej only supports single tensor input/output (found {len(rdf['inputs'])}/{len(rdf['outputs'])})",
            details=None,
            links=["deepimagej/deepimagej"],
        )
    else:
        report = test_model_deepimagej(rdf_url, fiji_executable, fiji_path)

    return report


def check_compatibility_deepimagej(
    deepimagej_version: str, all_version_path: Path, output_folder: Path, fiji_executable: str, fiji_path: str,
):
    partial_impl = partial(
        check_compatibility_deepimagej_impl,
        fiji_executable=fiji_executable,
        fiji_path=fiji_path
    )
    check_tool_compatibility(
        "deepimagej",
        deepimagej_version,
        all_version_path=all_version_path,
        output_folder=output_folder,
        check_tool_compatibility_impl=partial_impl,
        applicable_types={"model"},
    )

def get_dij_version(fiji_path):
    plugins_path = os.path.join(fiji_path, "plugins")
    pattern = re.compile(r"^deepimagej-(\d+\.\d+\.\d+(?:-snapshot)?)\.jar$")

    matching_files = [
        file.lower()
        for file in os.listdir(plugins_path)
        if pattern.match(file.lower())
    ]
    assert len(matching_files) > 0, "No deepImageJ plugin found, review your installation"
    version = pattern.search(matching_files[0]).group(1)
    return version


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("all_versions", type=Path)
    _ = parser.add_argument("output_folder", type=Path)
    _ = parser.add_argument("fiji_executable", type=str)
    _ = parser.add_argument("fiji_path", type=str)

    args = parser.parse_args()
    check_compatibility_deepimagej(
        get_dij_version(args.fiji_path), args.all_versions, args.output_folder, fiji_executable=args.fiji_executable, fiji_path=args.fiji_path
    )
