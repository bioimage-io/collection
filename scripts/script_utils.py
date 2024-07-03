import hashlib
from io import BytesIO
from typing import Any, Dict, Optional, Sequence, Union

import requests
from typing_extensions import Literal, NotRequired, TypedDict

try:
    from ruyaml import YAML
except ImportError:
    from ruamel.yaml import YAML

yaml = YAML(typ="safe")


class CompatiblityReport(TypedDict):
    status: Literal["passed", "failed", "not-applicable"]
    """status of this tool for this resource"""

    error: Optional[str]
    """error message if `status`=='failed'"""

    details: Any
    """details to explain the `status`"""

    links: NotRequired[Sequence[str]]
    """the checked resource should link these other bioimage.io resources"""


def download_and_check_hash(url: str, sha256: str) -> bytes:
    r = requests.get(url)
    r.raise_for_status()
    data = r.content

    actual = hashlib.sha256(data).hexdigest()
    if actual != sha256:
        raise ValueError(
            f"found sha256='{actual}' for downlaoded {url}, but exptected '{sha256}'"
        )

    return data


def download_rdf(rdf_url: str, sha256: str) -> Dict[str, Any]:
    rdf_data = download_and_check_hash(rdf_url, sha256)
    rdf: Union[Any, Dict[Any, Any]] = yaml.load(BytesIO(rdf_data))
    assert isinstance(rdf, dict)
    assert all(isinstance(k, str) for k in rdf)
    return rdf
