import json
import os
import uuid
import warnings
from functools import partialmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
from bioimageio.spec import load_raw_resource_description, validate  # type: ignore
from bioimageio.spec.model.raw_nodes import Model, WeightsFormat  # type: ignore
from bioimageio.spec.rdf.raw_nodes import RDF_Base  # type: ignore
from bioimageio.spec.shared import yaml  # type: ignore
from bioimageio.spec.shared.raw_nodes import URI, Dependencies  # type: ignore
from marshmallow import missing
from marshmallow.utils import _Missing
from packaging.version import Version
from tqdm import tqdm

from .remote_resource import StagedVersion

tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # silence tqdm


def set_multiple_gh_actions_outputs(outputs: Dict[str, Union[str, Any]]):
    for name, out in outputs.items():
        set_gh_actions_output(name, out)


def set_gh_actions_output(name: str, output: Union[str, Any]):
    """set output of a github actions workflow step calling this script"""
    if isinstance(output, bool):
        output = "yes" if output else "no"

    if not isinstance(output, str):
        output = json.dumps(output, sort_keys=True)

    if "GITHUB_OUTPUT" not in os.environ:
        print(output)
        return

    if "\n" in output:
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            delimiter = uuid.uuid1()
            print(f"{name}<<{delimiter}", file=fh)
            print(output, file=fh)
            print(delimiter, file=fh)
    else:
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            print(f"{name}={output}", file=fh)


def get_base_env():
    return {"channels": ["conda-forge"], "dependencies": ["bioimageio.core"]}


def get_env_from_deps(deps: Dependencies):
    conda_env = get_base_env()
    try:
        if deps.manager in ["conda", "pip"]:
            if isinstance(deps.file, Path):
                raise TypeError(
                    f"File path for remote source? {deps.file} should be a url"
                )
            elif not isinstance(deps.file, URI):
                raise TypeError(deps.file)

            r = requests.get(str(deps.file))
            r.raise_for_status()
            dep_file_content = r.text
            if deps.manager == "conda":
                conda_env = yaml.load(dep_file_content)

                # add bioimageio.core to dependencies
                deps = conda_env.get("dependencies", [])
                if not isinstance(deps, list):
                    raise TypeError(
                        f"expected dependencies in conda environment.yaml to be a list, but got: {deps}"
                    )
                if not any(
                    isinstance(d, str) and d.startswith("bioimageio.core") for d in deps
                ):
                    conda_env["dependencies"] = deps + ["conda-forge::bioimageio.core"]
            elif deps.manager == "pip":
                pip_req = [
                    d
                    for d in dep_file_content.split("\n")
                    if not d.strip().startswith("#")
                ]
                if not any(r.startswith("bioimageio.core") for r in pip_req):
                    pip_req.append("bioimageio.core")

                conda_env = dict(
                    channels=["conda-forge"],
                    dependencies=["python=3.9", "pip", {"pip": pip_req}],
                )
            else:
                raise NotImplementedError(deps.manager)

    except Exception as e:
        warnings.warn(f"Failed to resolve dependencies: {e}")

    return conda_env


def get_version_range(v: Version) -> str:
    return f"=={v.major}.{v.minor}.*"


def get_default_env(
    *,
    opset_version: Optional[int] = None,
    pytorch_version: Optional[Version] = None,
    tensorflow_version: Optional[Version] = None,
):
    conda_env: Dict[str, Union[Any, List[Any]]] = get_base_env()
    if opset_version is not None:
        conda_env["dependencies"].append("onnxruntime")
        # note: we should not need to worry about the opset version,
        # see https://github.com/microsoft/onnxruntime/blob/master/docs/Versioning.md

    if pytorch_version is not None:
        conda_env["channels"].insert(0, "pytorch")
        conda_env["dependencies"].extend(
            [f"pytorch {get_version_range(pytorch_version)}", "cpuonly"]
        )

    if tensorflow_version is not None:
        # tensorflow 1 is not available on conda, so we need to inject this as a pip dependency
        if tensorflow_version.major == 1:
            tensorflow_version = max(
                tensorflow_version, Version("1.13")
            )  # tf <1.13 not available anymore
            assert opset_version is None
            assert pytorch_version is None
            conda_env["dependencies"] = [
                "pip",
                "python=3.7.*",
            ]  # tf 1.15 not available for py>=3.8
            # get bioimageio.core (and its dependencies) via pip as well to avoid conda/pip mix
            # protobuf pin: tf 1 does not pin an upper limit for protobuf,
            #               but fails to load models saved with protobuf 3 when installing protobuf 4.
            conda_env["dependencies"].append(
                {
                    "pip": [
                        "bioimageio.core",
                        f"tensorflow {get_version_range(tensorflow_version)}",
                        "protobuf <4.0",
                    ]
                }
            )
        elif tensorflow_version.major == 2 and tensorflow_version.minor < 11:
            # get older tf versions from defaults channel
            conda_env = {
                "channels": ["defaults"],
                "dependencies": [
                    "conda-forge::bioimageio.core",
                    f"tensorflow {get_version_range(tensorflow_version)}",
                ],
            }
        else:  # use conda-forge otherwise
            conda_env["dependencies"].append(
                f"tensorflow {get_version_range(tensorflow_version)}"
            )

    return conda_env


def write_conda_env_file(
    *, rd: Model, weight_format: WeightsFormat, path: Path, env_name: str
):
    assert isinstance(rd, Model)
    given_versions: Dict[str, Union[_Missing, Version]] = {}
    default_versions = dict(
        pytorch_version=Version("1.10"),
        tensorflow_version=Version("1.15"),
        opset_version=15,
    )
    if weight_format in ["pytorch_state_dict", "torchscript"]:
        given_versions["pytorch_version"] = rd.weights[weight_format].pytorch_version
    elif weight_format in ["tensorflow_saved_model_bundle", "keras_hdf5"]:
        given_versions["tensorflow_version"] = rd.weights[
            weight_format
        ].tensorflow_version
    elif weight_format in ["onnx"]:
        given_versions["opset_version"] = rd.weights[weight_format].opset_version
    else:
        raise NotImplementedError(weight_format)

    deps = rd.weights[weight_format].dependencies
    if deps is missing:
        conda_env = get_default_env(
            **{vn: v or default_versions[vn] for vn, v in given_versions.items()}
        )
    else:
        if any(given_versions.values()):
            warnings.warn(
                f"Using specified dependencies; ignoring given versions: {given_versions}"
            )

        conda_env = get_env_from_deps(deps)

    conda_env["name"] = env_name

    path.parent.mkdir(parents=True, exist_ok=True)
    yaml.dump(conda_env, path)


def ensure_valid_conda_env_name(name: str) -> str:
    for illegal in ("/", " ", ":", "#"):
        name = name.replace(illegal, "")

    return name or "empty"


def prepare_dynamic_test_cases(rd: RDF_Base) -> List[Dict[str, str]]:
    validation_cases: List[Dict[str, str]] = []
    # construct test cases based on resource type
    if isinstance(rd, Model):
        # generate validation cases per weight format
        for wf in rd.weights:
            # we skip the keras validation for now, see
            # https://github.com/bioimage-io/collection-bioimage-io/issues/16
            if wf in ("keras_hdf5", "tensorflow_js"):
                warnings.warn(f"{wf} weights are currently not validated")
                continue

            write_conda_env_file(
                rd=rd,
                weight_format=wf,
                path=Path(f"conda_env_{wf}.yaml"),
                env_name=wf,
            )
            validation_cases.append({"weight_format": wf})
    elif isinstance(rd, RDF_Base):
        pass
    else:
        raise TypeError(rd)

    return validation_cases


def validate_format(staged: StagedVersion):
    rdf_source = staged.get_rdf_url()
    summaries = [validate(rdf_source)]

    dynamic_test_cases: List[Dict[str, str]] = []
    if summaries[0]["status"] == "passed":
        # validate rdf using the latest format version
        latest_static_summary = validate(rdf_source, update_format=True)
        if latest_static_summary["status"] == "passed":
            rd = load_raw_resource_description(rdf_source, update_to_format="latest")
            assert isinstance(rd, RDF_Base)
            dynamic_test_cases += prepare_dynamic_test_cases(rd)

        if "name" not in latest_static_summary:
            latest_static_summary["name"] = (
                "bioimageio.spec static validation with auto-conversion to latest format"
            )
        summaries.append(latest_static_summary)

    set_multiple_gh_actions_outputs(
        dict(
            has_dynamic_test_cases=bool(dynamic_test_cases),
            dynamic_test_cases={"include": dynamic_test_cases},
        )
    )
