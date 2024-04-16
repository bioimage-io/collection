import random

from .db_structure.id_parts import IdParts
from .s3_client import Client


def _select_parts(type_: str):
    all_id_parts = IdParts.load()
    if type_ == "model":
        return all_id_parts.model
    elif type_ == "dataset":
        return all_id_parts.dataset
    elif type_ == "notebook":
        return all_id_parts.notebook
    else:
        raise NotImplementedError(
            f"handling resource id for type '{type_}' is not yet implemented"
        )


def validate_resource_id(resource_id: str, *, type_: str):
    _select_parts(type_).validate_resource_id(resource_id)


def generate_resource_id(client: Client, type_: str):
    taken = set(client.ls("", only_folders=True))
    id_parts = _select_parts(type_)
    nouns = list(id_parts.nouns)
    n = 9999
    for _ in range(n):
        adj = random.choice(id_parts.adjectives)
        noun = random.choice(nouns)
        resource_id = f"{adj}-{noun}"
        if resource_id not in taken:
            return resource_id

    raise RuntimeError(
        f"I tried {n} times to generate an available {type_} resource id, but failed."
    )
