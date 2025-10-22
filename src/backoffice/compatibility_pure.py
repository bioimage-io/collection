from typing import Any, Optional, Sequence

from typing_extensions import Literal, TypedDict


class BadgeDict(TypedDict):
    icon: str
    label: str
    url: str


class ToolCompatibilityReportDict(TypedDict):
    tool: str
    """toolname (including version separated by an underscore)"""

    status: Literal["passed", "failed", "not-applicable"]
    """status of this tool for this resource"""

    error: Optional[str]
    """error message if `status`=='failed'"""

    details: Any
    """details to explain the `status`"""

    badge: Optional[BadgeDict]
    """status badge with a resource specific link to the tool"""

    links: Sequence[str]
    """the checked resource should link these other bioimage.io resources"""
