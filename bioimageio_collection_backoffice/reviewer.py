from functools import lru_cache
from typing import Dict

import requests
from pydantic import BaseModel

from ._settings import settings


class Reviewer(BaseModel):
    name: str
    affiliation: str
    orcid: str
    github_user: str
    email: str


@lru_cache
def get_reviewers():
    """load mapping of user-ids to Reviewer (info)
    for bioimage.io reviewers"""
    ret: Dict[str, Reviewer] = {
        k: Reviewer.model_validate(v)
        for k, v in requests.get(settings.reviewers).json().items()
    }
    assert all(isinstance(name, str) for name in ret), "reviewer name has to be string"
    return ret
