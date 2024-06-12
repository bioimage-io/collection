from typing import Any, Literal, Mapping, Optional, Sequence

from pydantic import Field
from typing_extensions import Annotated

from ..collection_json import Badge
from ..common import Node


class CompatiblityReport(Node, frozen=True, extra="allow"):
    tool: Annotated[str, Field(exclude=True)]
    """toolname (including version)"""

    status: Literal["passed", "failed", "not-applicable"]
    """status of this tool for this resource"""

    error: Optional[str]
    """error message if `status`=='failed'"""

    details: Any
    """details to explain the `status`"""

    badge: Optional[Badge] = None
    """status badge with a resource specific link to the tool"""

    links: Sequence[str] = ()
    """the checked resource should link these other bioimage.io resources"""


class TestSummaryEntry(Node, frozen=True):
    error: Optional[str]
    name: str
    status: Literal["passed", "failed"]
    traceback: Optional[Sequence[str]]
    warnings: Optional[Mapping[str, Any]]


ToolName = str


class TestSummary(Node, frozen=True):
    status: Literal["passed", "failed"]
    tests: Mapping[ToolName, Sequence[TestSummaryEntry]]
