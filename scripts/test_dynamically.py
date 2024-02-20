import traceback
from functools import partialmethod
from pathlib import Path
from typing import Optional

import typer
from bioimageio.spec import load_description
from ruyaml import YAML
from utils.remote_resource import StagedVersion
from utils.s3_client import Client

yaml = YAML(typ="ssafe")
try:
    from tqdm import tqdm
except ImportError:
    pass
else:
    # silence tqdm
    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore


def test_summary_from_exception(name: str, exception: Exception):
    return dict(
        name=name,
        status="failed",
        error=str(exception),
        traceback=traceback.format_tb(exception.__traceback__),
    )


def test_dynamically(
    resource_id: str,
    version: int,
    weight_format: Optional[str] = typer.Argument(
        ..., help="weight format to test model with."
    ),
    create_env_outcome: str = "success",
):
    staged = StagedVersion(client=Client(), id=resource_id, version=version)
    rdf_source = staged.get_rdf_url()
    if weight_format is None:
        # no dynamic tests for non-model resources yet...
        return

    if create_env_outcome == "success":
        try:
            from bioimageio.core import test_resource
        except Exception as e:
            summaries = [
                test_summary_from_exception(
                    "import test_resource from test environment", e
                )
            ]
        else:
            try:
                rdf = yaml.load(rdf_source)
                test_kwargs = (
                    rdf.get("config", {})
                    .get("bioimageio", {})
                    .get("test_kwargs", {})
                    .get(weight_format, {})
                )
            except Exception as e:
                summaries = [test_summary_from_exception("check for test kwargs", e)]
            else:
                try:
                    rd = load_description(rdf_source)
                    summaries = test_resource(
                        rd, weight_format=weight_format, **test_kwargs
                    )
                except Exception as e:
                    summaries = [test_summary_from_exception("call 'test_resource'", e)]

    else:
        env_path = Path(f"conda_env_{weight_format}.yaml")
        if env_path.exists():
            error = "Failed to install conda environment:\n" + env_path.read_text()
        else:
            error = f"Conda environment yaml file not found: {env_path}"

        summaries = [
            dict(name="install test environment", status="failed", error=error)
        ]

    staged.add_log_entry("validation_summaries", summaries)


if __name__ == "__main__":
    typer.run(test_dynamically)
