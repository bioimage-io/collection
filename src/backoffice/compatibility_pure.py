"""Pure Python alternative data models for compatibility reports

Usable when installing backoffice without dependencies."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from typing_extensions import Literal, TypedDict

PartnerToolName = Literal[
    "ilastik",
    "deepimagej",
    "icy",
    "biapy",
    "careamics",
]
ToolName = Literal["bioimageio.core", PartnerToolName]

PARTNER_TOOL_NAMES = (
    "ilastik",
    "deepimagej",
    "icy",
    "biapy",
    "careamics",
)
TOOL_NAMES = ("bioimageio.core", *PARTNER_TOOL_NAMES)
ToolNameVersioned = str


class BadgeDict(TypedDict):
    icon: str
    label: str
    url: str


class ToolCompatibilityReportDict(TypedDict):
    status: Literal["passed", "failed", "not-applicable"]
    """status of this tool for this resource"""

    error: str | None
    """error message if `status`=='failed'"""

    details: Any
    """details to explain the `status`"""

    badge: BadgeDict | None
    """status badge with a resource specific link to the tool"""

    links: Sequence[str]
    """the checked resource should link these other bioimage.io resources"""
