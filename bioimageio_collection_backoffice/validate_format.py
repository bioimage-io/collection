import warnings
from typing import Dict, List, Literal, Optional, Tuple, TypedDict, Union, cast

from bioimageio.spec import InvalidDescr, ResourceDescr, load_description
from bioimageio.spec.common import RelativeFilePath
from bioimageio.spec.model import v0_4, v0_5
from bioimageio.spec.model.v0_5 import Version, WeightsFormat
from bioimageio.spec.summary import ErrorEntry, ValidationDetail
from bioimageio.spec.utils import download
from ruyaml import YAML
from typing_extensions import assert_never

from .db_structure.log import BioimageioLog, BioimageioLogEntry, Log
from .remote_collection import Record, RecordDraft

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


def ensure_min_env(env: CondaEnv, env_name: Optional[str] = None):
    """update a conda env such that we have bioimageio.core and the collection backoffice available"""
    if env_name is None:
        env["name"] = ensure_valid_conda_env_name(env.get("name", ""))
    else:
        env["name"] = env_name

    if "name" not in env:
        env["name"] = "env"

    if "channels" not in env:
        env["channels"] = []

    if "dependencies" not in env:
        env["dependencies"] = []

    if "conda-forge" not in env["channels"]:
        env["channels"].append("conda-forge")

    if "pip" not in env["dependencies"]:
        env["dependencies"].append("pip")

    pip_section: PipDeps = {"pip": []}
    for d in env["dependencies"]:
        if isinstance(d, dict) and "pip" in d:
            pip_section = d
            break
    else:
        env["dependencies"].append(pip_section)

    if (
        collection_main := "git+https://github.com/bioimage-io/collection.git@main"
    ) not in pip_section["pip"]:
        pip_section["pip"].append(collection_main)

    if (
        "bioimageio.core" not in env["dependencies"]
        or "conda-forge::bioimageio.core" not in env["dependencies"]
        or "bioimageio.core" not in pip_section["pip"]
    ):
        env["dependencies"].append("conda-forge::bioimageio.core")


def get_base_env():
    return CondaEnv(
        name="env",
        channels=[],
        dependencies=[],
    )


def get_env_from_deps(
    deps: Union[v0_4.Dependencies, v0_5.EnvironmentFileDescr],
) -> CondaEnv:
    if isinstance(deps, v0_4.Dependencies):
        if deps.manager == "pip":
            conda_env = get_base_env()
            conda_env["dependencies"].append("pip")
            pip_deps = [
                d.strip() for d in download(deps.file).path.read_text().split("\n")
            ]
            if "bioimageio.core" not in pip_deps:
                pip_deps.append("bioimageio.core")

            conda_env["dependencies"].append(PipDeps({"pip": pip_deps}))
        elif deps.manager not in ("conda", "mamba"):
            raise ValueError(f"Dependency manager {deps.manager} not supported")
        else:
            deps_source = (
                deps.file.absolute
                if isinstance(deps.file, RelativeFilePath)
                else deps.file
            )
            local = download(deps_source).path
            conda_env = CondaEnv(**yaml.load(local))
    elif isinstance(deps, v0_5.EnvironmentFileDescr):
        local = download(deps.source).path
        conda_env = CondaEnv(**yaml.load(local))
    else:
        assert_never(deps)

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
        [
            f"pytorch {get_version_range(pytorch_version)}",
            "cpuonly",
            "mkl !=2024.1.0",  #  avoid https://github.com/pytorch/pytorch/issues/123097
        ]
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
        conda_env["dependencies"].extend(
            [
                "pip",
                "python=3.7.*",
            ]
        )  # tf 1.15 not available for py>=3.8
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

    ensure_min_env(conda_env, env_name)
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
            if entry is None:
                continue

            # we skip the keras validation for now, see
            # https://github.com/bioimage-io/collection-bioimage-io/issues/16
            if wf == "keras_hdf5":
                warnings.warn(f"{wf} weights are currently not validated")
                continue

            wf = cast(WeightsFormat, wf)
            conda_envs[wf] = get_conda_env(entry=entry, env_name=wf)
            validation_cases.append({"weight_format": wf})

    return validation_cases, conda_envs


def validate_format(rv: Union[RecordDraft, Record]):
    if isinstance(rv, RecordDraft):
        rv.set_testing_status("Validating RDF format")

    rd, dynamic_test_cases, conda_envs = validate_format_impl(rv.rdf_url)
    if not isinstance(rd, InvalidDescr):
        if rd.version is not None:
            error = None
            if isinstance(rv, RecordDraft):
                published = rv.concept.get_published_versions()
                if str(rd.version) in {v.version for v in published}:
                    error = ErrorEntry(
                        loc=("version",),
                        msg=f"Version '{rd.version}' is already published!",
                        type="error",
                    )

            rd.validation_summary.add_detail(
                ValidationDetail(
                    name="Enforce that RDF has unpublished semantic `version`",
                    status="passed" if error is None else "failed",
                    errors=[] if error is None else [error],
                )
            )

        rd.validation_summary.add_detail(
            ValidationDetail(
                name="Check `id_emoji`",
                status="failed" if rd.id_emoji is None else "passed",
                errors=(
                    [ErrorEntry(loc=("id_emoji",), msg="missing", type="error")]
                    if rd.id_emoji is None
                    else []
                ),
            )
        )

    rv.extend_log(
        Log(
            bioimageio_spec=[
                BioimageioLog(
                    log=BioimageioLogEntry(
                        message=rd.validation_summary.name,
                        details=rd.validation_summary,
                    )
                )
            ]
        )
    )
    return dynamic_test_cases, conda_envs


def validate_format_impl(rdf_source: str):
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

    return rd, dynamic_test_cases, conda_envs
