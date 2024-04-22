from typing import Dict

import requests
from pydantic import BaseModel

from ._settings import settings


class Reviewer(BaseModel):
    name: str
    affiliation: str
    orcid: str
    github_user: str 


# load mapping of user-ids to Reviewer (info)
# for bioimage.io maintainers
REVIEWERS: Dict[str, Reviewer] = {
    k: Reviewer.model_validate(v)
    for k, v in requests.get(settings.reviewers).json().items()
}
assert all(
    isinstance(name, str) for name in REVIEWERS
), "Maintainer name has to be string"
