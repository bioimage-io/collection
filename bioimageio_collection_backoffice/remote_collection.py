from dataclasses import dataclass

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