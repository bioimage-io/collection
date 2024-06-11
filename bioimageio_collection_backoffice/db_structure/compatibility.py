from typing import Any, Literal

from pydantic import Field
from typing_extensions import Annotated

from ..common import Node


class CompatiblityReport(Node, frozen=True, extra="allow"):
    tool: Annotated[str, Field(exclude=True)]
    """toolname (including version)"""

    status: Literal["passed", "failed", "not-applicable"]
    """status of this tool for this resource"""

    details: Any
    """details to explain the `status`"""
