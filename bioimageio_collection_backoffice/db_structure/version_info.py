from __future__ import annotations

from datetime import datetime
from typing import ClassVar, List, Literal, Optional, Sequence, Union

import pydantic
from typing_extensions import Annotated

from .._settings import settings
from ..common import Node


class _StatusBase(Node, frozen=True):
    timestamp: datetime = pydantic.Field(default_factory=datetime.now)
    run_url: Optional[str] = settings.run_url


class _DraftStatusBase(_StatusBase, frozen=True):
    description: str
    num_steps: int = 6

    @pydantic.model_validator(mode="after")
    def _validate_num_steps(self):
        assert self.num_steps >= getattr(self, "step", 0)
        return self


class UnpackingStatus(_DraftStatusBase, frozen=True):
    name: Literal["unpacking"] = "unpacking"
    step: Literal[1] = 1


class UnpackedStatus(_DraftStatusBase, frozen=True):
    name: Literal["unpacked"] = "unpacked"
    description: str = "staging was successful; awaiting automated tests to start ⏳"
    step: Literal[2] = 2


class TestingStatus(_DraftStatusBase, frozen=True):
    name: Literal["testing"] = "testing"
    step: Literal[3] = 3


class AwaitingReviewStatus(_DraftStatusBase, frozen=True):
    name: Literal["awaiting review"] = "awaiting review"
    description: str = (
        "Thank you for your contribution! 🎉"
        "Our bioimage.io maintainers will take a look soon. 🦒"
    )
    step: Literal[4] = 4


class ChangesRequestedStatus(_DraftStatusBase, frozen=True):
    name: Literal["changes requested"] = "changes requested"
    step: Literal[5] = 5


class AcceptedStatus(_DraftStatusBase, frozen=True):
    name: Literal["accepted"] = "accepted"
    description: str = (
        "This staged version has been accepted by a bioimage.io maintainer and is about to be published."
    )
    step: Literal[5] = 5


class PublishedDraftStatus(_DraftStatusBase, frozen=True):
    """following `AcceptedStatus`"""

    name: Literal["published"] = "published"
    description: str = "published! (this draft will be deleted shortly)"
    step: Literal[6] = 6


DraftStatus = Annotated[
    Union[
        UnpackingStatus,
        UnpackedStatus,
        TestingStatus,
        AwaitingReviewStatus,
        ChangesRequestedStatus,
        AcceptedStatus,
        PublishedDraftStatus,
    ],
    pydantic.Discriminator("name"),
]


class ErrorStatus(_StatusBase, frozen=True):
    name: Literal["error"] = "error"
    step: Literal[0] = 0
    message: str
    traceback: List[str]
    during: Optional[DraftStatus]


class DraftInfo(Node, frozen=True):
    """`<concept_id>/draft/draft.json` contains the collection entry metadata"""

    file_name: ClassVar[str] = "draft.json"

    status: Optional[
        Annotated[Union[DraftStatus, ErrorStatus], pydantic.Discriminator("name")]
    ] = None
    created: datetime = pydantic.Field(default_factory=datetime.now)

    def get_updated(self, update: DraftInfo) -> DraftInfo:
        return DraftInfo(created=self.created, status=update.status)


class RecordInfo(Node, frozen=True):
    """`<concept_id>/info.json` contains the collection entry metadata"""

    file_name: ClassVar[str] = "info.json"

    created: datetime = pydantic.Field(default_factory=datetime.now)

    concept_doi: Optional[str] = None

    doi: Optional[str] = None
    """version specific DOI"""

    download_count: Union[int, Literal["?"]] = "?"

    def get_updated(self, update: RecordInfo) -> RecordInfo:
        return RecordInfo(
            created=self.created,
            concept_doi=self.concept_doi or update.concept_doi,
            doi=self.doi or update.doi,
            download_count=(
                self.download_count
                if update.download_count == "?"
                else update.download_count
            ),
        )


class VersionInfo(Node, frozen=True):

    created: datetime = pydantic.Field(default_factory=datetime.now)

    doi: Optional[str] = None
    """version specific DOI"""


class VersionsInfo(Node, frozen=True):
    concept_doi: Optional[str] = None
    versions: Sequence[VersionInfo] = ()
