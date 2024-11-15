import pydantic
from ruyaml import YAML

yaml = YAML(typ="safe")


class Node(
    pydantic.BaseModel,
    extra="ignore",
    frozen=True,
    populate_by_name=True,
    revalidate_instances="never",
    validate_assignment=True,
    validate_default=False,
):
    """"""  # avoid inheriting docstring from `pydantic.BaseModel`
