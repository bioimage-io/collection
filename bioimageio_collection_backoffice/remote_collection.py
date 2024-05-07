import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Union

from bioimageio.spec import ValidationContext, build_description
from bioimageio.spec.collection import CollectionDescr
from loguru import logger
from typing_extensions import assert_never

from .generate_collection_json import (
    create_entry,
    generate_doi_mapping,
    generate_old_doi_mapping,
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
    ) -> None:
        """generate a json file with an overview of all published resources"""
        output_file_name: str = (
            "collection.json" if mode == "published" else f"collection_{mode}.json"
        )
        logger.info("generating {}", output_file_name)

        with collection_template.open() as f:
            collection = json.load(f)

        error_in_published_entry = None
        if mode == "published":
            for rv in self.get_all_published_versions():
                try:
                    entry = create_entry(self.client, rv)
                except Exception as e:
                    error_in_published_entry = (
                        f"failed to create {rv.id} {rv.version} entry: {e}"
                    )
                    logger.error(error_in_published_entry)
                else:
                    collection["collection"].append(entry)
        elif mode == "staged":
            for rv in self.get_all_staged_versions():
                try:
                    entry = create_entry(self.client, rv)
                except Exception as e:
                    logger.info(
                        "failed to create {} {} entry: {}", rv.id, rv.version, e
                    )
                else:
                    collection["collection"].append(entry)
        else:
            assert_never(mode)
        coll_descr = build_description(
            collection, context=ValidationContext(perform_io_checks=False)
        )
        if not isinstance(coll_descr, CollectionDescr):
            logger.error(coll_descr.validation_summary.format())

        if mode == "published":
            generate_old_doi_mapping(self.client, collection)
            generate_doi_mapping(self.client, collection)

        self.client.put_json(output_file_name, collection)
        if error_in_published_entry is not None:
            raise ValueError(error_in_published_entry)

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
