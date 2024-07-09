"""implements the Backoffice CLI"""

import warnings
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, Union

from bioimageio.spec.model.v0_5 import WeightsFormat
from loguru import logger

from ._settings import settings
from .backup import backup
from .db_structure.chat import Chat, Message
from .db_structure.log import Log, LogEntry
from .gh_utils import set_gh_actions_outputs
from .mailroom.send_email import notify_uploader
from .remote_collection import (
    Record,
    RecordConcept,
    RecordDraft,
    RemoteCollection,
    get_remote_resource_version,
)
from .run_dynamic_tests import run_dynamic_tests
from .s3_client import Client
from .validate_format import validate_format


class BackOffice:
    """This backoffice aids to maintain the bioimage.io collection"""

    def __init__(
        self,
        host: str = settings.s3_host,
        bucket: str = settings.s3_bucket,
        prefix: str = settings.s3_folder,
    ) -> None:
        super().__init__()
        self.client = Client(host=host, bucket=bucket, prefix=prefix)
        logger.info("created backoffice with client {}", self.client)

    def download(self, in_collection_path: str, output_path: Optional[Path] = None):
        """downlaod a file from the collection (using the MinIO client)"""
        data = self.client.load_file(in_collection_path)
        if data is None:
            raise FileNotFoundError(
                f"failed to download {self.client.get_file_url(in_collection_path)}"
            )

        if output_path is None:
            output_path = Path(in_collection_path)

        _ = output_path.write_bytes(data)

    def log(self, message: str, concept_id: str, version: str):
        """log a message"""

        if not settings.run_url:
            raise ValueError("'RUN_URL' not set")

        rv = get_remote_resource_version(self.client, concept_id, version)
        rv.extend_log(Log(entries=[LogEntry(message=message)]))

    def wipe(self, subfolder: str = ""):
        """DANGER ZONE: wipes `subfolder` completely, only use for test folders!"""
        url = self.client.get_file_url(subfolder)
        key_parts = ("sandbox", "testing")
        if not any(p in url for p in key_parts):
            raise RuntimeError(f"Refusing to wipe {url} (missing any of {key_parts})")

        self.client.rm_dir(subfolder)

    def draft(self, concept_id: str, package_url: str):
        """stage a new resourse version draft from `package_url`"""
        resource = RecordConcept(self.client, concept_id)
        _ = resource.draft_new_version(package_url)
        self.generate_collection_json(mode="draft")

    stage = draft

    def validate_format(self, concept_id: str, version: str):
        """validate a resource version's rdf.yaml"""
        rv = get_remote_resource_version(self.client, concept_id, version)
        dynamic_test_cases, conda_envs = validate_format(rv)
        set_gh_actions_outputs(
            has_dynamic_test_cases=bool(dynamic_test_cases),
            dynamic_test_cases={"include": dynamic_test_cases},
            conda_envs=conda_envs,
        )

    def test(
        self,
        concept_id: str,
        version: str,
        weight_format: Optional[Union[WeightsFormat, Literal[""]]] = None,
        create_env_outcome: Literal["success", ""] = "success",
    ):
        """run dynamic tests for a (staged) resource version"""
        rv = get_remote_resource_version(self.client, concept_id, version)
        if (
            isinstance(rv, RecordDraft)
            and (rv_status := rv.info.status) is not None
            and rv_status.name == "unpacked"
        ):
            rv.set_testing_status(
                "Testing"
                + ("" if weight_format is None else f" {weight_format} weights"),
            )

        run_dynamic_tests(
            record=rv,
            weight_format=weight_format or None,
            create_env_outcome=create_env_outcome,
        )

        if (
            isinstance(rv, RecordDraft)
            and (rv_status := rv.info.status) is not None
            and rv_status.name == "testing"
        ):
            rv.await_review()
            notify_uploader(
                rv,
                "is awaiting review ⌛",
                f"Thank you for submitting {rv.concept_id}!\n"
                + "Our maintainers will take a look shortly.\n"
                + f"A preview is available [here]({rv.bioimageio_url})",
            )

    def request_changes(
        self,
        resource_id: str,
        version: Literal["deprecated"] = "deprecated",
        reviewer: str = "",
        reason: str = "",
    ):
        """mark a (staged) resource version as needing changes"""
        if version != "deprecated":
            warnings.warn("`version` argument is depcrecated and will be removed soon")

        if not reviewer:
            raise ValueError("Missing `reviewer`")

        if not reason:
            raise ValueError("Missing `reason`")

        rv = RecordDraft(client=self.client, concept_id=resource_id)
        if not rv.exists():
            raise ValueError(f"'{rv.id}' not found")

        rv.request_changes(reviewer, reason=reason)
        notify_uploader(
            rv,
            "needs changes 📑",
            f"Thank you for submitting {rv.concept_id}!\n"
            + "We kindly ask you to upload an updated version, because: \n"
            + f"{reason}\n",  # TODO: add link to chat
        )

    def publish(
        self,
        concept_id: str,
        version: Literal["deprecated"] = "deprecated",
        reviewer: str = "",
    ):  # TODO: remove version and make reviewer mandatory
        """publish a (staged) resource version"""
        if version != "deprecated":
            warnings.warn("`version` argument is deprecated and will be removed soon")

        if not reviewer:
            raise ValueError("Missing `reviewer`")

        rv = RecordDraft(client=self.client, concept_id=concept_id)

        if isinstance(rv, Record):
            raise ValueError(f"Cannot publish already published {concept_id} {version}")

        published: Record = rv.publish(reviewer)
        assert isinstance(published, Record)
        self.generate_collection_json(mode="published")
        notify_uploader(
            published,
            "was published! 🎉",
            f"Thank you for contributing {published.id} to bioimage.io!\n"
            + f"Check it out at {published.bioimageio_url}\n",
        )

    def backup(self, destination: str = "deprecated"):
        """backup the whole collection (to zenodo.org)"""
        if destination != "deprecated":
            logger.warning("argument `destination` is deprecated")

        _ = backup(self.client)
        self.generate_collection_json(mode="published")
        self.generate_collection_json(mode="draft")

    def generate_collection_json(
        self,
        mode: Literal["published", "draft"] = "published",
    ):
        """generate the collection.json file --- a summary of the whole collection"""
        RemoteCollection(self.client).generate_collection_json(mode=mode)

    def forward_emails_to_chat(self):
        logger.error("disabled")
        # forward_emails_to_chat(self.client, last_n_days=7)

    def add_chat_message(
        self, concept_id: str, version: str, chat_message: str, author: str
    ) -> Chat:
        """add message to chat

        Returns: updated chat
        """
        chat = Chat(
            messages=[
                Message(author=author, text=chat_message, timestamp=datetime.now())
            ]
        )
        rv = get_remote_resource_version(self.client, concept_id, version)
        rv.extend_chat(chat)
        return rv.chat

    def get_chat(self, concept_id: str, version: str) -> Chat:
        rv = get_remote_resource_version(self.client, concept_id, version)
        return rv.chat
