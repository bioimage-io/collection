import os
from typing import Literal, Optional, Union

from bioimageio.spec.model.v0_5 import WeightsFormat
from dotenv import load_dotenv

from backoffice.backup import backup
from backoffice.remote_resource import (
    PublishedVersion,
    RemoteResource,
    StagedVersion,
)
from backoffice.run_dynamic_tests import run_dynamic_tests
from backoffice.s3_client import Client
from backoffice.s3_structure.versions import StageNr
from backoffice.validate_format import validate_format

_ = load_dotenv()


class BackOffice:
    def __init__(
        self,
        host: str = os.environ["S3_HOST"],
        bucket: str = os.environ["S3_BUCKET"],
        prefix: str = os.environ["S3_FOLDER"],
    ) -> None:
        super().__init__()
        self.client = Client(host=host, bucket=bucket, prefix=prefix)

    def wipe(self, subfolder: str = ""):
        """DANGER ZONE: wipes `subfolder` completely, only use for test folders!"""
        url = self.client.get_file_url(subfolder)
        key_parts = ("sandbox", "testing")
        if not all(p in url for p in key_parts):
            raise RuntimeError(f"Refusing to wipe {url} (missing {key_parts})")

        self.client.rm_dir(subfolder)

    def stage(self, resource_id: str, package_url: str):
        resource = RemoteResource(self.client, resource_id)
        staged = resource.stage_new_version(package_url)
        validate_format(staged)

    def test(
        self,
        resource_id: str,
        stage_nr: StageNr,
        weight_format: Optional[Union[WeightsFormat, Literal[""]]] = None,
        create_env_outcome: Literal["success", ""] = "success",
    ):
        staged = StagedVersion(self.client, resource_id, stage_nr)
        run_dynamic_tests(
            staged=staged,
            weight_format=weight_format or None,
            create_env_outcome=create_env_outcome,
        )

    def await_review(self, resource_id: str, stage_nr: StageNr):
        staged = StagedVersion(self.client, resource_id, stage_nr)
        staged.await_review()

    def request_changes(self, resource_id: str, stage_nr: StageNr, reason: str):
        staged = StagedVersion(self.client, resource_id, stage_nr)
        staged.request_changes(reason=reason)

    def publish(self, resource_id: str, stage_nr: StageNr):
        staged = StagedVersion(self.client, resource_id, stage_nr)
        published = staged.publish()
        assert isinstance(published, PublishedVersion)

    def backup(self, destination: Optional[str] = None):
        _ = backup(self.client, destination or os.environ["ZENODO_URL"])
