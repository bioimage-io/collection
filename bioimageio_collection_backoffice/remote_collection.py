import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Union

from bioimageio.spec import ValidationContext, build_description
from bioimageio.spec.collection import CollectionDescr
from loguru import logger
from typing_extensions import assert_never

from .db_structure.partners import Partners
from .generate_collection_json import (
    create_entry,
    generate_doi_mapping,
    generate_old_doi_mapping,
)
from .remote_base import RemoteBase
from .s3_client import Client


@dataclass
class RemoteCollection(RemoteBase):
    """A representation of a (the) bioimage.io collection"""

    client: Client
    """Client to connect to remote storage"""

    @property
    def folder(self) -> str:
        """collection folder is given by the `client` prefix"""
        return ""

    partners_json = "partners.json"

    @property
    def partners(self) -> Partners:
        return self._get_json(Partners)

    @property
    def get_partner_ids(self):
        return tuple(p.id for p in self.partners.active)

    def get_resource_concepts(self):
        from .remote_resource import ResourceConcept

        partner_ids = self.get_partner_ids
        return [  # general resources outside partner folders
            ResourceConcept(client=self.client, id=d)
            for d in self.client.ls("", only_folders=True)
            if d.strip("/") not in partner_ids
        ] + [  # resources in partner folders
            ResourceConcept(client=self.client, id=d)
            for pid in partner_ids
            for d in self.client.ls(pid, only_folders=True)
        ]

    def get_all_staged_versions(self):
        for rc in self.get_resource_concepts():
            for v in rc.get_all_staged_versions():
                if v.info.status.name in ("superseded", "published"):
                    # TODO: clean up superseded (and published) staged versions after x months
                    continue

                yield v

    def get_all_published_versions(self):
        for rc in self.get_resource_concepts():
            for v in rc.get_all_published_versions():
                yield v

    def generate_collection_json(
        self,
        collection_template: Path = Path(
            "collection_template.json"
        ),  # TODO: fill template with 'partners.json' and use remote template
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
                    if entry is not None:
                        collection["collection"].append(entry)
                        if entry["version"] == max(entry["versions"]):
                            latest_entry = dict(entry)
                            version_suffix = f"/{entry['version']}"
                            assert isinstance(entry["id"], str)
                            assert entry["id"].endswith(version_suffix)
                            latest_entry["id"] = entry["id"][: -len(version_suffix)]
                            collection["collection"].append(latest_entry)

        elif mode == "staged":
            for rv in self.get_all_staged_versions():
                try:
                    entry = create_entry(self.client, rv)
                except Exception as e:
                    logger.info(
                        "failed to create {} {} entry: {}", rv.id, rv.version, e
                    )
                else:
                    if entry is not None:
                        collection["collection"].append(entry)
                        if int(entry["version"][len("staged/")]) == max(
                            int(v[len("staged/") :]) for v in entry["versions"]
                        ):
                            latest_entry = dict(entry)
                            version_suffix = f"/{entry['version']}"
                            assert isinstance(entry["id"], str)
                            assert entry["id"].endswith(version_suffix)
                            latest_entry["id"] = (
                                entry["id"][: -len(version_suffix)] + "/staged"
                            )
                            collection["collection"].append(latest_entry)
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
