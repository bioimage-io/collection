import warnings
from typing import Dict, List, Literal, Optional, Tuple, TypedDict, Union, cast

from bioimageio.spec import InvalidDescr, ResourceDescr, load_description
from bioimageio.spec.common import Sha256
from bioimageio.spec.model import v0_4, v0_5
from bioimageio.spec.model.v0_5 import Version, WeightsFormat
from bioimageio.spec.summary import ErrorEntry, ValidationDetail
from bioimageio.spec.utils import download
from ruyaml import YAML
from typing_extensions import assert_never, get_args

from .db_structure.log import BioimageioLog, Log
from .remote_resource import PublishedVersion, StagedVersion

yaml = YAML(typ="safe")

SupportedWeightsEntry = Union[
    v0_4.OnnxWeightsDescr,
    v0_4.PytorchStateDictWeightsDescr,
    v0_4.TensorflowSavedModelBundleWeightsDescr,
    v0_4.TorchscriptWeightsDescr,
    v0_5.OnnxWeightsDescr,
    v0_5.PytorchStateDictWeightsDescr,
    v0_5.TensorflowSavedModelBundleWeightsDescr,
    v0_5.TorchscriptWeightsDescr,
]


class PipDeps(TypedDict):
    pip: List[str]


class CondaEnv(TypedDict):
    name: str
    channels: List[str]
    dependencies: List[Union[str, PipDeps]]


def get_base_env():
    return CondaEnv(
        name="env", channels=["conda-forge"], dependencies=["bioimageio.core"]
    )


def get_env_from_deps(deps: Union[v0_4.Dependencies, v0_5.EnvironmentFileDescr]):
    if isinstance(deps, v0_4.Dependencies):
        if deps.manager not in ("conda", "mamba"):
            return get_base_env()

        deps_source = deps.file
        sha: Optional[Sha256] = None
    elif isinstance(deps, v0_5.EnvironmentFileDescr):
        deps_source = deps.source
        sha = deps.sha256
    else:
        assert_never(deps)

    local = download(deps_source, sha256=sha).path
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


def get_conda_env(
    *,
    entry: SupportedWeightsEntry,
    env_name: str,
) -> CondaEnv:
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

    return conda_env


def ensure_valid_conda_env_name(name: str) -> str:
    for illegal in ("/", " ", ":", "#"):
        name = name.replace(illegal, "")

    return name or "empty"


def prepare_dynamic_test_cases(
    rd: ResourceDescr,
) -> Tuple[
    List[Dict[Literal["weight_format"], WeightsFormat]], Dict[WeightsFormat, CondaEnv]
]:
    validation_cases: List[Dict[Literal["weight_format"], WeightsFormat]] = []
    # construct test cases based on resource type
    conda_envs: Dict[WeightsFormat, CondaEnv] = {}
    if isinstance(rd, (v0_4.ModelDescr, v0_5.ModelDescr)):
        # generate validation cases per weight format
        for wf, entry in rd.weights:
            # we skip the keras validation for now, see
            # https://github.com/bioimage-io/collection-bioimage-io/issues/16
            if not isinstance(entry, get_args(SupportedWeightsEntry)):
                warnings.warn(f"{wf} weights are currently not validated")
                continue

            wf = cast(WeightsFormat, wf)
            conda_envs[wf] = get_conda_env(
                entry=entry,
                env_name=wf,
            )
            validation_cases.append({"weight_format": wf})

    return validation_cases, conda_envs


def validate_format(rv: Union[StagedVersion, PublishedVersion]):
    if not rv.exists:
        raise ValueError(f"{rv} not found")

    if isinstance(rv, StagedVersion):
        rv.set_testing_status("Validating RDF format")

    rdf_source = rv.rdf_url
    rd = load_description(rdf_source, format_version="discover")
    if not isinstance(rd, InvalidDescr):
        rd.validation_summary.add_detail(
            ValidationDetail(
                name="Check that uploader is specified",
                status="failed" if rd.uploader is None else "passed",
                errors=[
                    ErrorEntry(
                        loc=("uploader", "email"),
                        msg="missing uploader email",
                        type="error",
                    )
                ],
            )
        )
    dynamic_test_cases: List[Dict[Literal["weight_format"], WeightsFormat]] = []
    conda_envs: Dict[WeightsFormat, CondaEnv] = {}
    if not isinstance(rd, InvalidDescr):
        rd_latest = load_description(rdf_source, format_version="latest")
        if isinstance(rd_latest, InvalidDescr):
            dynamic_test_cases, conda_envs = prepare_dynamic_test_cases(rd)
        else:
            dynamic_test_cases, conda_envs = prepare_dynamic_test_cases(rd_latest)

        rd = rd_latest
        rd.validation_summary.status = "passed"  # passed in 'discover' mode
        if not isinstance(rd, InvalidDescr) and rd.version is not None:
            error = None
            if isinstance(rv, StagedVersion):
                published = rv.concept.versions.published
                if str(rd.version) in {v.sem_ver for v in published.values()}:
                    error = ErrorEntry(
                        loc=("version",),
                        msg=f"Trying to publish version {rd.version} again!",
                        type="error",
                    )

            rd.validation_summary.add_detail(
                ValidationDetail(
                    name="Enforce that RDF has unpublished semantic `version`",
                    status="passed" if error is None else "failed",
                    errors=[] if error is None else [error],
                )
            )

    summary = rd.validation_summary
    rv.extend_log(Log(bioimageio_spec=[BioimageioLog(log=summary)]))
    return dynamic_test_cases, conda_envs
