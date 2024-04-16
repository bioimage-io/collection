import json
import uuid
from io import TextIOWrapper
from typing import Any, Dict, Union, no_type_check

from loguru import logger

from ._settings import settings


def _set_gh_actions_output_impl(msg: Union[str, uuid.UUID], fh: TextIOWrapper):
    logger.info("GH actions output: {}", msg)
    print(msg, file=fh)


def set_gh_actions_outputs(**outputs: Union[str, Any]):
    for name, output in outputs.items():
        """set output of a github actions workflow step calling this script"""
        if isinstance(output, bool):
            output = "yes" if output else "no"

        if not isinstance(output, str):
            output = json.dumps(output, sort_keys=True)

        if settings.github_output is None:
            logger.error("output would be: {}", output)
            return

        with open(settings.github_output, "a") as fh:
            if "\n" in output:
                delimiter = uuid.uuid1()
                _set_gh_actions_output_impl(f"{name}<<{delimiter}", fh)
                _set_gh_actions_output_impl(output, fh)
                _set_gh_actions_output_impl(delimiter, fh)
            else:
                _set_gh_actions_output_impl(f"{name}={output}", fh)


@no_type_check
def workflow_dispatch(workflow_name: str, inputs: Dict[str, Any]):
    import github

    g = github.Github(login_or_token=settings.github_pat)

    repo = g.get_repo("bioimage-io/collection")

    workflow = repo.get_workflow(workflow_name)

    ref = repo.get_branch("main")
    workflow.create_dispatch(ref=ref, inputs=inputs)
