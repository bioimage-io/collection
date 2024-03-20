import json
import os
import uuid
from io import TextIOWrapper
from typing import Any, Union

from loguru import logger


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

        if "GITHUB_OUTPUT" not in os.environ:
            logger.error(
                "GITHUB_OUTPUT env var not defined; output would be: {}", output
            )
            return

        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            if "\n" in output:
                delimiter = uuid.uuid1()
                _set_gh_actions_output_impl(f"{name}<<{delimiter}", fh)
                _set_gh_actions_output_impl(output, fh)
                _set_gh_actions_output_impl(delimiter, fh)
            else:
                _set_gh_actions_output_impl(f"{name}={output}", fh)
