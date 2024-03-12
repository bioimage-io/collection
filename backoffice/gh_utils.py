import json
import os
import uuid
from io import TextIOWrapper
from typing import Any, Union

from loguru import logger


def _set_gh_actions_output_impl(msg: Union[str, uuid.UUID], fh: TextIOWrapper):
    logger.info("GH actions output: {}", msg)
    print(msg, file=fh)


def set_gh_actions_output(name: str, output: Union[str, Any]):
    """set output of a github actions workflow step calling this script"""
    if isinstance(output, bool):
        output = "yes" if output else "no"

    if not isinstance(output, str):
        output = json.dumps(output, sort_keys=True)

    if "GITHUB_OUTPUT" not in os.environ:
        logger.error("GITHUB_OUTPUT env var not defined; output would be: {}", output)
        return

    if "\n" in output:
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            delimiter = uuid.uuid1()
            _set_gh_actions_output_impl(f"{name}<<{delimiter}", fh)
            _set_gh_actions_output_impl(output, fh)
            _set_gh_actions_output_impl(delimiter, fh)
    else:
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            _set_gh_actions_output_impl(f"{name}={output}", fh)


def set_multiple_gh_actions_outputs(outputs: dict[str, Union[str, Any]]):
    for name, out in outputs.items():
        set_gh_actions_output(name, out)
