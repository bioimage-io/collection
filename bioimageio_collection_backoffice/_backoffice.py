import os
from pathlib import Path
from typing import Literal, Optional, Union

from bioimageio.spec.model.v0_5 import WeightsFormat
from dotenv import load_dotenv
from loguru import logger

from backoffice.backup import backup
from backoffice.generate_collection_json import generate_collection_json
from backoffice.gh_utils import set_gh_actions_outputs
from backoffice.mailroom import notify_uploader
from backoffice.remote_resource import (
    PublishedVersion,
    RemoteResource,
    get_remote_resource_version,
)
from backoffice.run_dynamic_tests import run_dynamic_tests
from backoffice.s3_client import Client
from backoffice.validate_format import validate_format

_ = load_dotenv()


class BackOffice:
    """This backoffice aids to maintain the bioimage.io collection"""

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
        """stage a new resourse (version) from `package_url`"""
        resource = RemoteResource(self.client, resource_id)
        staged = resource.stage_new_version(package_url)
        set_gh_actions_outputs(version=staged.version)

    def validate_format(self, resource_id: str, version: str):
        """validate a (staged) resource version's bioimageio.yaml"""
        rv = get_remote_resource_version(self.client, resource_id, version)
        if isinstance(rv, PublishedVersion):
            logger.error("Revalidation of published resources is not implemented")
            return

        dynamic_test_cases, conda_envs = validate_format(rv)
        set_gh_actions_outputs(
            has_dynamic_test_cases=bool(dynamic_test_cases),
            dynamic_test_cases={"include": dynamic_test_cases},
            conda_envs=conda_envs,
        )

    def test(
        self,
        resource_id: str,
        version: str,
        weight_format: Optional[Union[WeightsFormat, Literal[""]]] = None,
        create_env_outcome: Literal["success", ""] = "success",
    ):
        """run dynamic tests for a (staged) resource version"""
        rv = get_remote_resource_version(self.client, resource_id, version)
        if isinstance(rv, PublishedVersion):
            raise ValueError(
                f"Testing of already published {resource_id} {version} is not implemented"
            )

        run_dynamic_tests(
            staged=rv,
            weight_format=weight_format or None,
            create_env_outcome=create_env_outcome,
        )

    def await_review(self, resource_id: str, version: str):
        """mark a (staged) resource version is awaiting review"""
        rv = get_remote_resource_version(self.client, resource_id, version)
        if isinstance(rv, PublishedVersion):
            raise ValueError(
                f"Cannot await review for already published {resource_id} {version}"
            )
        rv.await_review()
        notify_uploader(
            rv,
            "is awaiting review ⌛",
            f"Thank you for proposing {rv.id} {rv.version}!\n"
            + "Our maintainers will take a look shortly!",
        )

    def request_changes(self, resource_id: str, version: str, reason: str):
        """mark a (staged) resource version as needing changes"""
        rv = get_remote_resource_version(self.client, resource_id, version)
        if isinstance(rv, PublishedVersion):
            raise ValueError(
                f"Requesting changes of already published  {resource_id} {version} is not implemented"
            )

        rv.request_changes(reason=reason)
        notify_uploader(
            rv,
            "needs changes 📑",
            f"Thank you for proposing {rv.id} {rv.version}!\n"
            + "We kindly ask you to upload an updated version, because: \n"
            + f"{reason}\n",
        )

    def publish(self, resource_id: str, version: str):
        """publish a (staged) resource version"""
        rv = get_remote_resource_version(self.client, resource_id, version)
        if isinstance(rv, PublishedVersion):
            raise ValueError(
                f"Cannot publish already published {resource_id} {version}"
            )

        published: PublishedVersion = rv.publish()
        assert isinstance(published, PublishedVersion)
        self.generate_collection_json()
        notify_uploader(
            rv,
            "was published! 🎉",
            f"Thank you for contributing {published.id} {published.version} to bioimage.io!\n"
            + "Check it out at https://bioimage.io/#/?id={published.id}\n",  # TODO: link to version
        )

    def backup(self, destination: Optional[str] = None):
        """backup the whole collection (to zenodo.org)"""
        _ = backup(self.client, destination or os.environ["ZENODO_URL"])

    def generate_collection_json(
        self, collection_template: Path = Path("collection_template.json")
    ):
        """generate the collection.json file --- a summary of the whole collection"""
        generate_collection_json(self.client, collection_template=collection_template)

    def forward_emails_to_chat(self):
        logger.error("disabled")
        # forward_emails_to_chat(self.client, last_n_days=7)
