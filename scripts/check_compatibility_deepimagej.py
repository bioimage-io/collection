import argparse
from pathlib import Path
from typing import List, Dict, Any
import os
import re
import json

import urllib.request
import subprocess
from functools import partial
import traceback

from script_utils import CompatibilityReportDict, check_tool_compatibility, download_rdf

try:
    from ruyaml import YAML
except ImportError:
    from ruamel.yaml import YAML

yaml = YAML(typ="safe")


def find_expected_output(outputs_dir, name):
    for ff in os.listdir(outputs_dir):
        if ff.endswith("_" + name + ".tif") or ff.endswith("_" + name + ".tiff"):
            return True
    return False


def check_dij_macro_generated_outputs(model_dir: str):
    with open(os.path.join(model_dir, os.getenv("JSON_OUTS_FNAME")), 'r') as f:
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
    for inp in data["inputs"]:
        inp.pop('preprocessing', None)
    for out in data["outputs"]:
        out.pop('postprocessing', None)
        if not isinstance(out["axes"][0], dict):
            out.pop('halo', None)
            continue
        for ax in out["axes"]:
            ax.pop('halo', None)
    with open(os.path.join(model_dir, "rdf.yaml"), 'w') as outfile:
        yaml.dump(data, outfile)



def test_model_deepimagej(rdf_url: str, fiji_executable: str, fiji_path: str):
    yaml_file = os.path.abspath("rdf.yaml")
    try:
        urllib.request.urlretrieve(rdf_url, yaml_file)
    except Exception as e:
        report = CompatibilityReportDict(
                status="failed",
                error=f"unable to download the yaml file",
                details=e.stderr + os.linesep + e.stdout if isinstance(e, subprocess.CalledProcessError) else traceback.format_exc(),
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
        stderr=subprocess.PIPE,
        text=True
        )
    except BaseException as e:
        report = CompatibilityReportDict(
                status="failed",
                error=f"unable to read the yaml file",
                details=e.stderr + os.linesep + e.stdout if isinstance(e, subprocess.CalledProcessError) else traceback.format_exc(),
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
        stderr=subprocess.PIPE,
        text=True
        )
        model_dir = download_result.stdout.strip().splitlines()[-1]
    except BaseException as e:
        report = CompatibilityReportDict(
                status="failed",
                error=f"unable to download the model",
                details=e.stderr + os.linesep + e.stdout if isinstance(e, subprocess.CalledProcessError) else traceback.format_exc(),
                links=["deepimagej/deepimagej"],
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
            text=True
        )
        out_str = run.stdout
        if not check_dij_macro_generated_outputs(model_dir):
            report = CompatibilityReportDict(
                    status="failed",
                    error=f"error running the model",
                    details=out_str,
                    links=["deepimagej/deepimagej"],
                ) 
            return report
    except BaseException as e:
        report = CompatibilityReportDict(
                status="failed",
                error=f"error running the model",
                details=e.stderr + os.linesep + e.stdout if isinstance(e, subprocess.CalledProcessError) else traceback.format_exc(),
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
        stderr=subprocess.PIPE,
        text=True
        )
    except BaseException as e:
        report = CompatibilityReportDict(
                status="failed",
                error=f"error comparing expected outputs and actual outputs",
                details=e.stderr + os.linesep + e.stdout if isinstance(e, subprocess.CalledProcessError) else traceback.format_exc(),
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

    elif len(rdf["inputs"]) > 1 :#or len(rdf["outputs"]) > 1:
        report = CompatibilityReportDict(
            status="failed",
            #error=f"deepimagej only supports single tensor input/output (found {len(rdf['inputs'])}/{len(rdf['outputs'])})",
            error=f"deepimagej only supports single tensor input (found {len(rdf['inputs'])})",
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
    fiji_path = os.path.abspath(args.fiji_path)
    check_compatibility_deepimagej(
        get_dij_version(fiji_path), args.all_versions, args.output_folder, fiji_executable=args.fiji_executable, fiji_path=fiji_path
    )
