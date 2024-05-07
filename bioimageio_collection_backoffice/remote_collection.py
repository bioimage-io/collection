import json
from dataclasses import dataclass
from typing import Any, Dict, List, Union

from .remote_resource import ResourceConcept
from .s3_client import Client


@dataclass
class RemoteCollection:
    """A representation of a (the) bioimage.io collection"""

    client: Client
    """Client to connect to remote storage"""

    def get_resource_concepts(self):
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
