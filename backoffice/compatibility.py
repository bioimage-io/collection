import warnings
from typing import Any, Literal, Mapping, Optional, Sequence, Union

from annotated_types import Interval
from packaging.version import Version
from pydantic import BaseModel, Field, HttpUrl, computed_field, model_validator
from typing_extensions import Annotated

PartnerToolName = Literal[
    "ilastik",
    "deepimagej",
    "icy",
    "biapy",
    "careamics",
]
ToolName = Literal["bioimageio.spec", "bioimageio.core", *PartnerToolName]

PARTNER_TOOL_NAMES = (
    "ilastik",
    "deepimagej",
    "icy",
    "biapy",
    "careamics",
)
TOOL_NAMES = ("bioimageio.spec", "bioimageio.core", *PARTNER_TOOL_NAMES)

ToolNameVersioned = str


class Node(BaseModel):
    pass


class Badge(Node):
    icon: HttpUrl
    label: str
    url: HttpUrl


class ToolReportDetails(Node, extra="allow"):
    traceback: Optional[Sequence[str]] = None
    warnings: Optional[Mapping[str, Any]] = None
    metadata_completeness: Optional[float] = None


class ToolCompatibilityReport(Node, extra="allow"):
    """Used to report on the compatibility of resource description
    in the bioimageio collection for a version specific tool.
    """

    tool: Annotated[ToolName, Field(exclude=True, pattern=r"^[^_]+_[^_]+$")]
    """tool name"""

    tool_version: Annotated[str, Field(exclude=True, pattern=r"^[^_]+_[^_]+$")]
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
        if "score" not in values:
            values["score"] = 1.0 if values.get("status") == "passed" else 0.0

        return values

    error: Optional[str]
    """error message if `status`=='failed'"""

    details: Union[Any, ToolReportDetails] = None
    """details to explain the `status`"""

    badge: Optional[Badge] = None
    """status badge with a resource specific link to the tool"""

    links: Sequence[str] = ()
    """the checked resource should link these other bioimage.io resources"""


class CompatibilityScores(Node):
    tool_compatibility_version_specific: Mapping[
        ToolNameVersioned, Annotated[float, Interval(ge=0, le=1.0)]
    ]

    metadata_completeness: Annotated[float, Interval(ge=0, le=1.0)]
    """Score for metadata completeness, evaluated by bioimageio.spec"""

    @computed_field
    @property
    def metadata_format(self) -> Annotated[float, Interval(ge=0, le=1.0)]:
        """Score for metadata formatting, validated by bioimageio.spec"""
        return self.tool_compatibility.get("bioimageio.spec", 0.0)

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

            if tool_name not in grouped:
                grouped[tool_name] = {}

            grouped[tool_name][version] = grouped[tool_name].get(version, 0.0) + value

            grouped[tool_name][version] = value - malus

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
        """Overall partner tool compatibility score."""
        top4 = sorted(
            [v for k, v in self.tool_compatibility.items() if k in PARTNER_TOOL_NAMES],
            reverse=True,
        )[:4]
        assert top4
        return sum(top4) / len(top4)

    @computed_field
    @property
    def overall_compatibility(self) -> Annotated[float, Interval(ge=0, le=1.0)]:
        """Weighted, overall score between 0 and 1.
        Note: The scoring scheme is subject to arbitrary changes.
        """
        return (
            0.1 * self.metadata_format
            + 0.2 * self.metadata_completeness
            + 0.3 * self.core_compatibility
            + 0.4 * self.overall_partner_tool_compatibility
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

    tests: Mapping[ToolNameVersioned, ToolCompatibilityReport]
    """Compatibility reports for each tool version evaluated."""
