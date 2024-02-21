from typer import run
from utils.s3_client import Client

from scripts.utils.remote_resource import StagedVersion


def conclude(
    resource_id: str,
    version: int,
):
    staged = StagedVersion(client=Client(), id=resource_id, version=version)
    staged.set_status(
        "awaiting review",
        description="Thank you for your contribution! Our bioimage.io maintainers will take a look soon.",
    )


if __name__ == "__main__":
    run(conclude)
