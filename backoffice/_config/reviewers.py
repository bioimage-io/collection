from typing import Sequence

from .common import ConfigNode


class Reviewer(ConfigNode, frozen=True):
    id: str
    """hypha id"""
    name: str
    affiliation: str
    orcid: str
    github_user: str
    email: str


Reviewers = Sequence[Reviewer]
