from typing import Dict

import requests

from ._settings import settings

# load mapping of GitHub account names to plain names for bioimage.io maintainers
REVIEWERS: Dict[str, str] = requests.get(settings.reviewers).json()
assert all(
    r.lower() == r for r in REVIEWERS
), "Maintainer GitHub account name has to be lower case"
assert all(
    isinstance(name, str) for name in REVIEWERS
), "Maintainer name has to be string"
