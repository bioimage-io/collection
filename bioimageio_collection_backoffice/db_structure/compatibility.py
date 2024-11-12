from typing import Any, Literal, Mapping, Optional, Sequence

from pydantic import Field
from typing_extensions import Annotated

from ..collection_json import Badge
from ..common import Node


class CompatibilityReport(Node, frozen=True, extra="allow"):
    tool: Annotated[str, Field(exclude=True, pattern=r"^[^_]+_[^_]+$")]
    """toolname (including version separated by an underscore)"""

    @property
    def tool_wo_version(self) -> str:
        """assuming a pattern of <tool>_"""
        return self.tool.split("_")[0]

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
