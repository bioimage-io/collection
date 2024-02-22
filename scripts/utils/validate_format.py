import json
import os
import uuid
import warnings
from pathlib import Path
from typing import Any, Optional, TypedDict, assert_never

import pooch
from bioimageio.spec import InvalidDescr, ResourceDescr, load_description
from bioimageio.spec.model import v0_4, v0_5
from packaging.version import Version
from ruyaml import YAML

from .remote_resource import StagedVersion

yaml = YAML(typ="safe")

SupportedWeightsEntry = (
    v0_4.OnnxWeightsDescr
    | v0_4.PytorchStateDictWeightsDescr
    | v0_4.TensorflowSavedModelBundleWeightsDescr
    | v0_4.TorchscriptWeightsDescr
    | v0_5.OnnxWeightsDescr
    | v0_5.PytorchStateDictWeightsDescr
    | v0_5.TensorflowSavedModelBundleWeightsDescr
    | v0_5.TorchscriptWeightsDescr
)


def set_multiple_gh_actions_outputs(outputs: dict[str, str | Any]):
    for name, out in outputs.items():
        set_gh_actions_output(name, out)


def set_gh_actions_output(name: str, output: str | Any):
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


class PipDeps(TypedDict):
    pip: list[str]


class CondaEnv(TypedDict):
    name: str
    channels: list[str]
    dependencies: list[str | PipDeps]


def get_base_env():
    return CondaEnv(
        name="env", channels=["conda-forge"], dependencies=["bioimageio.core"]
    )


def get_env_from_deps(deps: v0_4.Dependencies | v0_5.EnvironmentFileDescr):
    if isinstance(deps, v0_4.Dependencies):
        if deps.manager not in ("conda", "mamba"):
            return get_base_env()

        url = deps.file
        sha = None
    elif isinstance(deps, v0_5.EnvironmentFileDescr):
        url = deps.source
        sha = deps.sha256
    else:
        assert_never(deps)

    local = Path(pooch.retrieve(url, known_hash=sha))  # type: ignore
    conda_env = yaml.load(local)

    # add bioimageio.core to dependencies
    if not any(isinstance(d, str) and d.startswith("bioimageio.core") for d in deps):
        conda_env["dependencies"].append("conda-forge::bioimageio.core")

    return conda_env


def get_version_range(v: Version) -> str:
    return f"=={v.major}.{v.minor}.*"


def get_onnx_env(*, opset_version: Optional[int]):
    if opset_version is None:
        opset_version = 15

    conda_env = get_base_env()
    # note: we should not need to worry about the opset version,
    # see https://github.com/microsoft/onnxruntime/blob/master/docs/Versioning.md
    conda_env["dependencies"].append("onnxruntime")
    return conda_env


def get_pytorch_env(
    *,
    pytorch_version: Optional[Version] = None,
):
    if pytorch_version is None:
        pytorch_version = Version("1.10")

    conda_env = get_base_env()
    conda_env["channels"].insert(0, "pytorch")
    conda_env["dependencies"].extend(
        [f"pytorch {get_version_range(pytorch_version)}", "cpuonly"]
    )
    return conda_env


def get_tf_env(tensorflow_version: Optional[Version]):
    conda_env = get_base_env()
    if tensorflow_version is None:
        tensorflow_version = Version("1.15")

    # tensorflow 1 is not available on conda, so we need to inject this as a pip dependency
    if tensorflow_version.major == 1:
        tensorflow_version = max(
            tensorflow_version, Version("1.13")
        )  # tf <1.13 not available anymore
        conda_env["dependencies"] = [
            "pip",
            "python=3.7.*",
        ]  # tf 1.15 not available for py>=3.8
        # get bioimageio.core (and its dependencies) via pip as well to avoid conda/pip mix
        # protobuf pin: tf 1 does not pin an upper limit for protobuf,
        #               but fails to load models saved with protobuf 3 when installing protobuf 4.
        conda_env["dependencies"].append(
            PipDeps(
                pip=[
                    "bioimageio.core",
                    f"tensorflow {get_version_range(tensorflow_version)}",
                    "protobuf <4.0",
                ]
            )
        )
    elif tensorflow_version.major == 2 and tensorflow_version.minor < 11:
        # get older tf versions from defaults channel
        conda_env = CondaEnv(
            name="env",
            channels=["defaults"],
            dependencies=[
                "conda-forge::bioimageio.core",
                f"tensorflow {get_version_range(tensorflow_version)}",
            ],
        )
    else:  # use conda-forge otherwise
        conda_env["dependencies"].append(
            f"tensorflow {get_version_range(tensorflow_version)}"
        )

    return conda_env


def write_conda_env_file(
    *,
    entry: SupportedWeightsEntry,
    path: Path,
    env_name: str,
):
    if isinstance(entry, (v0_4.OnnxWeightsDescr, v0_5.OnnxWeightsDescr)):
        conda_env = get_onnx_env(opset_version=entry.opset_version)
    elif isinstance(
        entry,
        (
            v0_4.PytorchStateDictWeightsDescr,
            v0_5.PytorchStateDictWeightsDescr,
            v0_4.TorchscriptWeightsDescr,
            v0_5.TorchscriptWeightsDescr,
        ),
    ):
        if (
            isinstance(entry, v0_5.TorchscriptWeightsDescr)
            or entry.dependencies is None
        ):
            conda_env = get_pytorch_env(pytorch_version=entry.pytorch_version)
        else:
            conda_env = get_env_from_deps(entry.dependencies)

    elif isinstance(
        entry,
        (
            v0_4.TensorflowSavedModelBundleWeightsDescr,
            v0_5.TensorflowSavedModelBundleWeightsDescr,
        ),
    ):
        if entry.dependencies is None:
            conda_env = get_tf_env(tensorflow_version=entry.tensorflow_version)
        else:
            conda_env = get_env_from_deps(entry.dependencies)
    else:
        assert_never(entry)

    conda_env["name"] = ensure_valid_conda_env_name(env_name)

    path.parent.mkdir(parents=True, exist_ok=True)
    yaml.dump(conda_env, path)


def ensure_valid_conda_env_name(name: str) -> str:
    for illegal in ("/", " ", ":", "#"):
        name = name.replace(illegal, "")

    return name or "empty"


def prepare_dynamic_test_cases(rd: ResourceDescr) -> list[dict[str, str]]:
    validation_cases: list[dict[str, str]] = []
    # construct test cases based on resource type
    if isinstance(rd, (v0_4.ModelDescr, v0_5.ModelDescr)):
        # generate validation cases per weight format
        for wf, entry in rd.weights:
            # we skip the keras validation for now, see
            # https://github.com/bioimage-io/collection-bioimage-io/issues/16
            if not isinstance(entry, SupportedWeightsEntry):
                warnings.warn(f"{wf} weights are currently not validated")
                continue

            write_conda_env_file(
                entry=entry,
                path=Path(f"conda_env_{wf}.yaml"),
                env_name=wf,
            )
            validation_cases.append({"weight_format": wf})

    return validation_cases


def validate_format(staged: StagedVersion):
    staged.set_status("testing", "Testing RDF format")
    rdf_source = staged.get_rdf_url()
    rd = load_description(rdf_source, format_version="discover")
    dynamic_test_cases: list[dict[str, str]] = []
    if not isinstance(rd, InvalidDescr):
        rd_latest = load_description(rdf_source, format_version="latest")
        if isinstance(rd_latest, InvalidDescr):
            dynamic_test_cases += prepare_dynamic_test_cases(rd)
        else:
            dynamic_test_cases += prepare_dynamic_test_cases(rd_latest)

        rd = rd_latest
        rd.validation_summary.status = "passed"  # passed in 'discover' mode

    summary = rd.validation_summary.model_dump(mode="json")
    staged.add_log_entry("bioimageio.spec", summary)

    set_multiple_gh_actions_outputs(
        dict(
            has_dynamic_test_cases=bool(dynamic_test_cases),
            dynamic_test_cases={"include": dynamic_test_cases},
            version=staged.version,
        )
    )
