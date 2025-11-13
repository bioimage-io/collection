"""data models for compatibility reports"""

import warnings
from typing import Any, List, Literal, Mapping, Optional, Sequence, Union

from annotated_types import Interval
from packaging.version import Version

try:
    from pydantic import BaseModel, Field, HttpUrl, computed_field, model_validator
except ImportError as e:
    raise ImportError(
        "pydantic is required for backoffice.compatibility. "
        "Please install `backoffice[dev]` or use backoffice.compatibility_pure instead."
    ) from e

from typing_extensions import Annotated

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


class Node(BaseModel):
    """Base data model with common config"""

    pass


class Badge(Node):
    icon: HttpUrl
    label: str
    url: HttpUrl


class ToolReportDetails(Node, extra="allow"):
    traceback: Optional[Sequence[str]] = None
    warnings: Optional[Mapping[str, Any]] = None
    metadata_completeness: Optional[float] = None
    status: Union[Literal["passed", "valid-format", "failed"], Any] = None


class ToolCompatibilityReport(Node, extra="allow"):
    """Used to report on the compatibility of resource description
    in the bioimageio collection for a version specific tool.
    """

    tool: Annotated[ToolName, Field(exclude=True, pattern=r"^[a-zA-Z0-9-\.]+$")]
    """tool name"""

    tool_version: Annotated[str, Field(exclude=True, pattern=r"^[a-z0-9\.-]+$")]
    """tool version, ideally in SemVer 2.0 format"""

    @property
    def report_name(self) -> str:
        return f"{self.tool}_{self.tool_version}"

    status: Literal["passed", "failed", "not-applicable"]
    """status of this tool for this resource"""

    score: Annotated[float, Interval(ge=0, le=1.0)]
    """score for the compatibility of this tool with the resource"""

    @model_validator(mode="before")
    @classmethod
    def _set_default_score(cls, values: dict[str, Any]) -> dict[str, Any]:
        if isinstance(values, dict) and "score" not in values:
            values["score"] = 1.0 if values.get("status") == "passed" else 0.0

        return values

    error: Optional[str]
    """error message if `status`=='failed'"""

    details: Union[ToolReportDetails, str, List[str], None] = None
    """details to explain the `status`"""

    badge: Optional[Badge] = None
    """status badge with a resource specific link to the tool"""

    links: Sequence[str] = ()
    """the checked resource should link these other bioimage.io resources"""


class CompatibilityScores(Node):
    tool_compatibility_version_specific: Mapping[
        ToolNameVersioned, Annotated[float, Interval(ge=0, le=1.0)]
    ]

    metadata_completeness: Annotated[float, Interval(ge=0, le=1.0)] = 0.0
    """Score for metadata completeness.

    A measure of how many optional fields in the resource RDF are filled out.
    """

    metadata_format: Annotated[float, Interval(ge=0, le=1.0)] = 0.0
    """Score for metadata formatting.

    - 1.0: resource RDF conforms to the latest spec version
    - 0.5: resource RDF conforms to an older spec version
    - 0.0: resource RDF does not conform to any known spec version
"""

    @computed_field
    @property
    def core_compatibility(self) -> float:
        return self.tool_compatibility.get("bioimageio.core", 0.0)

    @computed_field
    @property
    def tool_compatibility(
        self,
    ) -> Mapping[ToolName, Annotated[float, Interval(ge=0, le=1.0)]]:
        """Aggregated tool compatibility score"""
        grouped: dict[ToolName, dict[Version, float]] = {}
        for tool, value in self.tool_compatibility_version_specific.items():
            assert value <= 1.0, f"Tool {tool} has a compatibility score > 1.0: {value}"
            tool_name, tool_version = tool.split("_", 1)
            if tool_name not in TOOL_NAMES:
                warnings.warn(f"Tool {tool_name} is not a valid ToolName")
                continue

            malus = 0.0
            try:
                version = Version(tool_version)
            except Exception:
                version = Version("0.0.0")
                malus += 0.1  # penalize non-semver versions

            grouped.setdefault(tool_name, {})[version] = max(0, value - malus)

        for tool in list(grouped):
            if not grouped[tool]:
                del grouped[tool]

        agglomerated: dict[ToolName, float] = {}
        for tool, version_scores in grouped.items():
            latest_version = max(version_scores.keys())

            if version_scores[latest_version] >= 0.8:
                # if the latest version is compatible use it as the score
                score = version_scores[latest_version]
            else:
                # average the top 4 scores to score max 0.8
                # as penalty if the last_version isn't fully compatible
                top4 = sorted(version_scores.values(), reverse=True)[:4]
                score = min(0.8, sum(top4) / len(top4))

            agglomerated[tool] = score

        return agglomerated

    @computed_field
    @property
    def overall_partner_tool_compatibility(
        self,
    ) -> Annotated[float, Interval(ge=0, le=1.0)]:
        """Overall partner tool compatibility score.
        Note:
            - Currently implemented as: Average of the top 3 partner tool compatibility scores.
            - Implementation is subject to change in the future.
        """
        top3 = sorted(
            [v for k, v in self.tool_compatibility.items() if k in PARTNER_TOOL_NAMES],
            reverse=True,
        )[:3]
        if not top3:
            return 0.0
        else:
            return sum(top3) / 3

    @computed_field
    @property
    def overall_compatibility(self) -> Annotated[float, Interval(ge=0, le=1.0)]:
        """Weighted, overall score between 0 and 1.
        Note: The scoring scheme is subject to change in the future.
        """
        return (
            0.25 * self.metadata_format
            + 0.25 * self.metadata_completeness
            + 0.25 * self.core_compatibility
            + 0.25 * self.overall_partner_tool_compatibility
        )


class InitialSummary(Node):
    rdf_content: dict[str, Any]
    """The RDF content of the original rdf.yaml file."""

    rdf_yaml_sha256: str
    """SHA-256 of the original RDF YAML file."""

    status: Literal["passed", "failed", "untested"]
    """status of the bioimageio.core reproducibility tests."""


class CompatibilitySummary(InitialSummary):
    scores: CompatibilityScores
    """Scores for compatibility with the bioimage.io community tools."""

    tests: Mapping[ToolName, Mapping[str, ToolCompatibilityReport]]
    """Compatibility reports for each tool for each version."""
