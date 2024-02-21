import typer
from utils.remote_resource import RemoteResource
from utils.s3_client import Client
from utils.validate_format import validate_format


def stage(resource_id: str, package_url: str):
    resource = RemoteResource(client=Client(), id=resource_id)
    staged = resource.stage_new_version(package_url)
    validate_format(staged)


if __name__ == "__main__":
    typer.run(stage)
