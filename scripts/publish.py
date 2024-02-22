import typer
from utils.remote_resource import PublishedVersion, StagedVersion
from utils.s3_client import Client


def publish(resource_id: str, stage_nr: int):
    staged = StagedVersion(client=Client(), id=resource_id, version=stage_nr)
    published = staged.publish()
    assert isinstance(published, PublishedVersion)


if __name__ == "__main__":
    typer.run(publish)
