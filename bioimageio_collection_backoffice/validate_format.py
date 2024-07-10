import warnings
from typing import Dict, List, Literal, Tuple, Union, cast

from bioimageio.spec import InvalidDescr, ResourceDescr, load_description
from bioimageio.spec.model import v0_4, v0_5
from bioimageio.spec.model.v0_5 import WeightsFormat
from bioimageio.spec.summary import ErrorEntry, ValidationDetail

from bioimageio_collection_backoffice.conda_env import CondaEnv, get_conda_env

from .db_structure.log import LogEntry
from .remote_collection import Record, RecordDraft


def validate_format(rv: Union[RecordDraft, Record]):
    if isinstance(rv, RecordDraft):
        rv.set_testing_status("Validating RDF format")

    rd, dynamic_test_cases, conda_envs = _validate_format_impl(rv.rdf_url)
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

    rv.add_log_entry(
        LogEntry(
            message=rd.validation_summary.name,
            details=rd.validation_summary,
        )
    )
    return dynamic_test_cases, conda_envs


def _validate_format_impl(rdf_source: str):
    rd = load_description(rdf_source, format_version="discover")
    dynamic_test_cases: List[Dict[Literal["weight_format"], WeightsFormat]] = []
    conda_envs: Dict[WeightsFormat, CondaEnv] = {}
    if not isinstance(rd, InvalidDescr):
        rd_latest = load_description(rdf_source, format_version="latest")
        if isinstance(rd_latest, InvalidDescr):
            dynamic_test_cases, conda_envs = _prepare_dynamic_test_cases(rd)
        else:
            dynamic_test_cases, conda_envs = _prepare_dynamic_test_cases(rd_latest)

        rd = rd_latest
        rd.validation_summary.status = "passed"  # passed in 'discover' mode

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
        if rd.license is None:
            # some older RDF specs have 'license' as an optional field
            rd.validation_summary.add_detail(
                ValidationDetail(
                    name="Check that RDF has a license field",
                    status="failed" if rd.license is None else "passed",
                    errors=[
                        ErrorEntry(
                            loc=("license",),
                            msg="missing license field",
                            type="error",
                        )
                    ],
                )
            )

    return rd, dynamic_test_cases, conda_envs


def _prepare_dynamic_test_cases(
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
