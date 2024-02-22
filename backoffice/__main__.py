import os
from typing import Literal, Optional

import fire
from bioimageio.spec.model.v0_5 import WeightsFormat
from dotenv import load_dotenv

from .backup import backup
from .run_dynamic_tests import run_dynamic_tests
from .utils.remote_resource import PublishedVersion, RemoteResource, StagedVersion
from .utils.s3_client import Client
from .validate_format import validate_format

_ = load_dotenv()


class BackOffice:
    def __init__(self) -> None:
        super().__init__()
        self.client = Client()

    def stage(self, resource_id: str, package_url: str):
        resource = RemoteResource(client=Client(), id=resource_id)
        staged = resource.stage_new_version(package_url)
        validate_format(staged)

    def test(
        self,
        resource_id: str,
        version: int,
        weight_format: Optional[WeightsFormat] = None,
        create_env_outcome: Literal["success", ""] = "success",
    ):
        staged = StagedVersion(self.client, resource_id, version)
        run_dynamic_tests(
            staged=staged,
            weight_format=weight_format,
            create_env_outcome=create_env_outcome,
        )

    def await_review(self, resource_id: str, version: int):
        staged = StagedVersion(self.client, resource_id, version)
        staged.await_review()

    def publish(self, resource_id: str, stage_nr: int):
        staged = StagedVersion(client=self.client, id=resource_id, version=stage_nr)
        published = staged.publish()
        assert isinstance(published, PublishedVersion)

    def backup(self):
        _ = backup(self.client, os.environ["ZENODO_URL"])


if __name__ == "__main__":
    fire.Fire(BackOffice)
