import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Union

from .generate_collection_json import (
    generate_collection_json as generate_collection_json_impl,
)
from .s3_client import Client


@dataclass
class RemoteCollection:
    """A representation of a (the) bioimage.io collection"""

    client: Client
    """Client to connect to remote storage"""

    def get_resource_concepts(self):
        from .remote_resource import ResourceConcept

        return (
            ResourceConcept(client=self.client, id=d)
            for d in self.client.ls("", only_folders=True)
        )

    def get_all_staged_versions(self):
        for rc in self.get_resource_concepts():
            for v in rc.get_all_staged_versions():
                yield v

    def get_all_published_versions(self):
        for rc in self.get_resource_concepts():
            for v in rc.get_all_published_versions():
                yield v

    def generate_collection_json(
        self,
        collection_template: Path = Path("collection_template.json"),
        mode: Literal["published", "staged"] = "published",
    ):
        generate_collection_json_impl(self.client, collection_template, mode)

    def get_collection_json(self):
        data = self.client.load_file("collection.json")
        assert data is not None
        collection: Union[Any, Dict[str, Union[Any, List[Dict[str, Any]]]]] = (
            json.loads(data)
        )
        assert isinstance(
            collection, dict
        )  # TODO: create typed dict for collection.json
        assert all(isinstance(k, str) for k in collection)
        assert "collection" in collection
        assert isinstance(collection["collection"], list)
        assert all(isinstance(e, dict) for e in collection["collection"])
        assert all(isinstance(k, str) for e in collection["collection"] for k in e)
        assert all("name" in e for e in collection["collection"])
        return collection
