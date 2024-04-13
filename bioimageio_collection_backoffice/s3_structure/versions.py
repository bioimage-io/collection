from __future__ import annotations

from datetime import datetime
from typing import Dict, Literal, NewType, Optional, Union

import pydantic
from typing_extensions import Annotated

from .common import Node

PublishNumber = NewType("PublishNumber", int)
"""n-th published version"""

StageNumber = NewType("StageNumber", int)
"""n-th staged version"""


class _StatusBase(Node):
    timestamp: datetime = datetime.now()


class _StagedStatusBase(_StatusBase):
    description: str
    num_steps: Literal[6] = 6

    @pydantic.model_validator(mode="after")
    def _validate_num_steps(self):
        assert self.num_steps >= getattr(self, "step", 0)
        return self


class UnpackingStatus(_StagedStatusBase):
    name: Literal["unpacking"] = "unpacking"
    step: Literal[1] = 1


class UnpackedStatus(_StagedStatusBase):
    name: Literal["unpacked"] = "unpacked"
    description: str = "staging was successful; awaiting automated tests to start ⏳"
    step: Literal[2] = 2


class TestingStatus(_StagedStatusBase):
    name: Literal["testing"] = "testing"
    step: Literal[3] = 3


class AwaitingReviewStatus(_StagedStatusBase):
    name: Literal["awaiting review"] = "awaiting review"
    description: str = (
        "Thank you for your contribution! 🎉"
        "Our bioimage.io maintainers will take a look soon. 🦒"
    )

    step: Literal[4] = 4


class ChangesRequestedStatus(_StagedStatusBase):
    name: Literal["changes requested"] = "changes requested"
    step: Literal[5] = 5


class AcceptedStatus(_StagedStatusBase):
    name: Literal["accepted"] = "accepted"
    description: str = (
        "This staged version has been accepted by a bioimage.io maintainer and is about to be published."
    )
    step: Literal[5] = 5


class SupersededStatus(_StagedStatusBase):
    """following `ChangesRequestedStatus` and staging of a superseding staged version"""

    name: Literal["superseded"] = "superseded"
    step: Literal[6] = 6
    by: StageNumber


class PublishedStagedStatus(_StagedStatusBase):
    """following `AcceptedStatus`"""

    name: Literal["published"] = "published"
    description: str = "published! 🎉"
    step: Literal[6] = 6
    publish_number: PublishNumber


StagedVersionStatus = Annotated[
    Union[
        UnpackingStatus,
        UnpackedStatus,
        TestingStatus,
        AwaitingReviewStatus,
        ChangesRequestedStatus,
        AcceptedStatus,
        SupersededStatus,
        PublishedStagedStatus,
    ],
    pydantic.Discriminator("name"),
]


class PublishedStatus(_StatusBase):
    name: Literal["published"] = "published"
    stage_number: StageNumber


PulishedVersionStatus = PublishedStatus


class VersionInfo(Node):
    sem_ver: Optional[str] = None
    timestamp: datetime = datetime.now()


class PublishedVersionInfo(VersionInfo):
    status: PublishedStatus
    doi: Optional[str] = None
    """version specific zenodo DOI"""


class StagedVersionInfo(VersionInfo):
    status: StagedVersionStatus


class Versions(Node):
    """`<id>/versions.json` containing an overview of all published and staged resource versions"""

    published: Dict[PublishNumber, PublishedVersionInfo] = pydantic.Field(
        default_factory=dict
    )
    staged: Dict[StageNumber, StagedVersionInfo] = pydantic.Field(default_factory=dict)
    concept_doi: Optional[str] = None

    def extend(self, other: Versions) -> None:
        assert set(self.model_fields) == {"published", "staged", "concept_doi"}, set(
            self.model_fields
        )
        if self.concept_doi is None:
            self.concept_doi = other.concept_doi
        elif other.concept_doi is None:
            pass
        elif self.concept_doi != other.concept_doi:
            raise ValueError("May not overwrite concept_doi")

        self.published.update(other.published)
        self.staged.update(other.staged)
