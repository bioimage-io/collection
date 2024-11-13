from typing import Any, ClassVar, Dict, FrozenSet, Union

import pydantic
from pydantic_core import PydanticUndefined
from typing_extensions import LiteralString


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

    fields_to_set_explicitly: ClassVar[FrozenSet[LiteralString]] = frozenset()
    """set set these fields explicitly with their default value if they are not set,
    such that they are always included even when dumping with 'exlude_unset'"""

    @pydantic.model_validator(mode="before")
    @classmethod
    def set_fields_explicitly(
        cls, data: Union[Any, Dict[str, Any]]
    ) -> Union[Any, Dict[str, Any]]:
        if isinstance(data, dict):
            for name in cls.fields_to_set_explicitly:
                if (
                    name not in data
                    and name in cls.model_fields
                    and (
                        (field_info := cls.model_fields[name]).default
                        is not PydanticUndefined
                        or field_info.default_factory is not None
                    )
                ):
                    data[name] = field_info.get_default(call_default_factory=True)

        return data  # pyright: ignore[reportUnknownVariableType]
