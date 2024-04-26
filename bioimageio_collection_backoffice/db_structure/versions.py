from __future__ import annotations

from datetime import datetime
from typing import ClassVar, List, Literal, Mapping, NewType, Optional, Union

import pydantic
from typing_extensions import Annotated

from .._settings import settings
from .common import Node

PublishNumber = NewType("PublishNumber", int)
"""n-th published version"""

StageNumber = NewType("StageNumber", int)
"""n-th staged version"""


class _StatusBase(Node, frozen=True):
    timestamp: datetime = datetime.now()
    run_url: Optional[str] = settings.run_url


class _StagedStatusBase(_StatusBase, frozen=True):
    description: str
    num_steps: int = 6

    @pydantic.model_validator(mode="after")
    def _validate_num_steps(self):
        assert self.num_steps >= getattr(self, "step", 0)
        return self


class UnpackingStatus(_StagedStatusBase, frozen=True):
    name: Literal["unpacking"] = "unpacking"
    step: Literal[1] = 1


class UnpackedStatus(_StagedStatusBase, frozen=True):
    name: Literal["unpacked"] = "unpacked"
    description: str = "staging was successful; awaiting automated tests to start ⏳"
    step: Literal[2] = 2


class TestingStatus(_StagedStatusBase, frozen=True):
    name: Literal["testing"] = "testing"
    step: Literal[3] = 3


class AwaitingReviewStatus(_StagedStatusBase, frozen=True):
    name: Literal["awaiting review"] = "awaiting review"
    description: str = (
        "Thank you for your contribution! 🎉"
        "Our bioimage.io maintainers will take a look soon. 🦒"
    )
    step: Literal[4] = 4


class ChangesRequestedStatus(_StagedStatusBase, frozen=True):
    name: Literal["changes requested"] = "changes requested"
    step: Literal[5] = 5


class AcceptedStatus(_StagedStatusBase, frozen=True):
    name: Literal["accepted"] = "accepted"
    description: str = (
        "This staged version has been accepted by a bioimage.io maintainer and is about to be published."
    )
    step: Literal[5] = 5


class SupersededStatus(_StagedStatusBase, frozen=True):
    """following `ChangesRequestedStatus` and staging of a superseding staged version"""

    name: Literal["superseded"] = "superseded"
    step: Literal[6] = 6
    by: StageNumber


class PublishedStagedStatus(_StagedStatusBase, frozen=True):
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


class PublishedStatus(_StatusBase, frozen=True):
    name: Literal["published"] = "published"
    stage_number: StageNumber


PulishedVersionStatus = PublishedStatus


class ErrorStatus(_StatusBase, frozen=True):
    name: Literal["error"] = "error"
    step: Literal[0] = 0
    message: str
    traceback: List[str]
    during: Optional[Union[StagedVersionStatus, PulishedVersionStatus]]


class VersionInfo(Node, frozen=True):
    sem_ver: Optional[str] = None
    timestamp: datetime = datetime.now()


class PublishedVersionInfo(VersionInfo, frozen=True):
    status: Annotated[
        Union[PulishedVersionStatus, ErrorStatus], pydantic.Discriminator("name")
    ]
    doi: Optional[str] = None
    """version specific zenodo DOI"""


class StagedVersionInfo(VersionInfo, frozen=True):
    status: Annotated[
        Union[StagedVersionStatus, ErrorStatus], pydantic.Discriminator("name")
    ]


class Versions(Node, frozen=True):
    """`<id>/versions.json` containing an overview of all published and staged resource versions"""

    file_name: ClassVar[str] = "versions.json"

    published: Mapping[PublishNumber, PublishedVersionInfo] = pydantic.Field(
        default_factory=dict
    )
    staged: Mapping[StageNumber, StagedVersionInfo] = pydantic.Field(
        default_factory=dict
    )
    doi: Optional[str] = None

    def get_updated(self, update: Versions) -> Versions:
        if update.doi is None:
            concept_doi = self.doi
        elif self.doi is None:
            concept_doi = update.doi
        elif self.doi != update.doi:
            raise ValueError("May not overwrite doi")
        else:
            concept_doi = self.doi

        return Versions(
            published={**self.published, **update.published},
            staged={**self.staged, **update.staged},
            doi=concept_doi,
        )
