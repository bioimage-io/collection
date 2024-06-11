from typing import Any, Literal, Optional, Sequence

from pydantic import Field
from typing_extensions import Annotated

from bioimageio_collection_backoffice.collection_json import Badge

from ..common import Node


class CompatiblityReport(Node, frozen=True, extra="allow"):
    tool: Annotated[str, Field(exclude=True)]
    """toolname (including version)"""

    status: Literal["passed", "failed", "not-applicable"]
    """status of this tool for this resource"""

    details: Any
    """details to explain the `status`"""

    badge: Optional[Badge] = None
    """status badge with a resource specific link to the tool"""

    links: Sequence[str] = ()
    """the checked resource should link these other bioimage.io resources"""
