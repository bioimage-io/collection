import datetime
from typing import Optional

from loguru import logger
from typer import Argument, run
from typing_extensions import Annotated
from utils.s3_client import Client


def update_status(
    resource_id: str,
    version: int,
    message: Annotated[str, Argument(help="status message")],
    step: Annotated[
        Optional[int], Argument(help="optional step in multi-step process")
    ] = None,
    num_steps: Annotated[int, Argument(help="total steps of multi-step process")] = 6,
):
    assert step is None or step <= num_steps, (step, num_steps)
    timenow = datetime.datetime.now().isoformat()

    resource_path, version = version_from_resource_path_or_s3(resource_path, client)
    status = client.get_status(resource_path, version)

    if "messages" not in status:
        status["messages"] = []
    if step is not None:
        status["step"] = step
    if num_steps is not None:
        status["num_steps"] = num_steps
    status["last_message"] = message
    status["messages"].append({"timestamp": timenow, "text": message})
    client.put_status(resource_path, version, status)


if __name__ == "__main__":
    run(update_status)
