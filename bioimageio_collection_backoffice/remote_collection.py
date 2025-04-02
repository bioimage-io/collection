from __future__ import annotations

import hashlib
import io
import json
import random
import urllib.request
import zipfile
from abc import ABC
from collections import defaultdict
from dataclasses import dataclass, field
from functools import wraps
from itertools import product
from pathlib import Path
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)
from urllib.parse import SplitResult, urlsplit, urlunsplit

import bioimageio.core
import pydantic
import requests
from bioimageio.spec import ValidationContext
from bioimageio.spec._internal.type_guards import is_dict
from bioimageio.spec.common import HttpUrl
from bioimageio.spec.utils import (
    identify_bioimageio_yaml_file_name,
    is_valid_bioimageio_yaml_name,
)
from loguru import logger
from typing_extensions import Concatenate, ParamSpec, assert_never

from bioimageio_collection_backoffice.gh_utils import set_gh_actions_outputs

from .settings import settings
from .thumbnails import create_thumbnails
from .collection_config import CollectionConfig
from .collection_json import (
    AllVersions,
    AvailableConceptIds,
    CollectionEntry,
    CollectionJson,
    CollectionWebsiteConfig,
    ConceptSummary,
    ConceptVersion,
    Uploader,
)
from .db_structure.chat import Chat, Message
from .db_structure.compatibility import (
    CompatibilityReport,
    TestSummary,
    TestSummaryEntry,
)
from .db_structure.log import Log, LogEntry
from .db_structure.reserved import Reserved
from .db_structure.version_info import (
    AcceptedStatus,
    AwaitingReviewStatus,
    ChangesRequestedStatus,
    DraftInfo,
    DraftStatus,
    RecordInfo,
    TestingStatus,
    UnpackedStatus,
    UnpackingStatus,
    VersionInfo,
    VersionsInfo,
)
from .id_map import IdInfo, IdMap
from .mailroom.constants import BOT_EMAIL
from .remote_base import RemoteBase
from .s3_client import Client
from .common import yaml

LEGACY_DOWNLOAD_COUNTS = {
    "affable-shark": 70601,
    "ambitious-ant": 5830,
    "ambitious-sloth": 12735,
    "amiable-crocodile": 2516,
    "chatty-frog": 54555,
    "conscientious-seashell": 33362,
    "courteous-otter": 4519,
    "creative-panda": 35927,
    "determined-chipmunk": 18747,
    "discreet-rooster": 42990,
    "easy-going-sauropod": 12717,
    "efficient-chipmunk": 3556,
    "emotional-cricket": 36653,
    "fearless-crab": 39638,
    "hiding-blowfish": 41816,
    "hiding-tiger": 45822,
    "humorous-owl": 40313,
    "impartial-shark": 20822,
    "impartial-shrimp": 44942,
    "independent-shrimp": 23638,
    "joyful-deer": 19265,
    "kind-seashell": 40486,
    "laid-back-lobster": 25850,
    "loyal-parrot": 37100,
    "loyal-squid": 30836,
    "modest-octopus": 8531,
    "naked-microbe": 23086,
    "nice-peacock": 13995,
    "noisy-fish": 12501,
    "noisy-hedgehog": 6793,
    "non-judgemental-eagle": 36554,
    "organized-badger": 39777,
    "organized-cricket": 10156,
    "passionate-t-rex": 24267,
    "pioneering-rhino": 28176,
    "placid-llama": 39063,
    "polite-pig": 21235,
    "powerful-chipmunk": 35455,
    "powerful-fish": 31743,
    "shivering-raccoon": 34761,
    "straightforward-crocodile": 25477,
    "thoughtful-turtle": 25874,
    "wild-whale": 29530,
    "willing-hedgehog": 37772,
}

LEGACY_VERSIONS = {
    "10.5281/zenodo.5764892": ["6647674", "6322939"],
    "10.5281/zenodo.6338614": ["6338615"],
    "10.5281/zenodo.5869899": ["6647688", "6321179", "5869900"],
    "10.5281/zenodo.5874741": ["5874742"],
    "10.5281/zenodo.5914248": ["8186255", "6514622", "6514446", "5914249"],
    "10.5281/zenodo.6406756": ["6811922", "6811498", "6406757"],
    "10.5281/zenodo.5874841": ["6630266", "5874842"],
    "10.5281/zenodo.5749843": ["5888237"],
    "10.5281/zenodo.6028097": ["6028098"],
    "10.5281/zenodo.6348084": ["6348085"],
    "10.5281/zenodo.7261974": ["7782776", "7778377", "7688940", "7546703", "7261975"],
    "10.5281/zenodo.6028280": ["6647695", "6028281"],
    "10.5281/zenodo.6200635": ["7702687", "6538890", "6200636"],
    "10.5281/zenodo.6346511": ["7768142", "7701413", "6346512"],
    "10.5281/zenodo.6348728": ["6348729"],
    "10.5281/zenodo.5817052": ["5906839", "5850574"],
    "10.5281/zenodo.5847355": ["6647683", "6322908"],
    "10.5281/zenodo.6406803": ["6406804"],
    "10.5281/zenodo.6200999": ["7690494", "7678300", "6538911", "6224243"],
    "10.5281/zenodo.6384845": ["7774490", "7701638", "6384846"],
    "10.5281/zenodo.6383429": ["7774505", "7701632", "6383430"],
    "10.5281/zenodo.6079314": ["7695872", "7689587", "7688686", "6385590", "6079315"],
    "10.5281/zenodo.6334383": ["7805067", "7701262", "7697068", "6346500", "6334384"],
    "10.5281/zenodo.6334881": ["7805026", "7701241", "7696907", "6346477", "6334882"],
    "10.5281/zenodo.6334777": ["7765026", "7701561", "7696952", "6346524", "6334778"],
    "10.5281/zenodo.5910854": ["6539073", "5911832"],
    "10.5281/zenodo.6334583": [
        "7805434",
        "7768223",
        "7701492",
        "7696919",
        "6346519",
        "6334584",
    ],
    "10.5281/zenodo.6811491": ["6811492"],
    "10.5281/zenodo.6559474": ["6559475"],
    "10.5281/zenodo.5910163": ["5942853"],
    "10.5281/zenodo.6865412": ["6919253"],
    "10.5281/zenodo.7274275": ["8123818", "7274276"],
    "10.5281/zenodo.6808325": ["6808413"],
    "10.5281/zenodo.7315440": ["7315441"],
    "10.5281/zenodo.7380171": ["7405349"],
    "10.5281/zenodo.7614645": ["7642674"],
    "10.5281/zenodo.7772662": ["7781091"],
    "10.5281/zenodo.7786492": ["7786493"],
    "10.5281/zenodo.8421755": ["8432366"],
    "10.5281/zenodo.8064806": ["8073617"],
    "10.5281/zenodo.6559929": ["6559930"],
    "10.5281/zenodo.8419845": ["8420081"],
    "10.5281/zenodo.8420099": ["8420100"],
    "10.5281/zenodo.8401064": ["8429203", "8401065"],
    "10.5281/zenodo.8142283": ["8171247"],
    "10.5281/zenodo.7612115": ["7612152"],
}


T = TypeVar("T")
R = TypeVar("R", "RecordDraft", "Record")
P = ParamSpec("P")


def log(
    func: Callable[Concatenate[R, P], T],
) -> Callable[Concatenate[R, P], T]:
    """method decorator to indicate that a method execution should be logged"""

    @wraps(func)
    def wrapper(self: R, *args: P.args, **kwargs: P.kwargs):
        self.log_message(f"starting: '{func.__name__}'")
        try:
            ret = func(self, *args, **kwargs)
        except Exception as e:
            self.log_error(e)
            raise
        else:
            return ret

    return wrapper


def reviewer_role(
    func: Callable[Concatenate[R, str, P], T],
) -> Callable[Concatenate[R, str, P], T]:
    """method decorator to indicate that a method may only be called by a bioimage.io reviewer"""

    @wraps(func)
    def wrapper(self: R, actor: str, *args: P.args, **kwargs: P.kwargs):
        if not any(r.id == actor for r in self.collection.config.reviewers):
            raise ValueError(f"{actor} is not allowed to trigger '{func.__name__}'")

        return func(self, actor, *args, **kwargs)

    return wrapper


def lock_concept(
    func: Callable[Concatenate[R, P], T],
) -> Callable[Concatenate[R, P], T]:
    """method decorator to indicate that a method may only be called by a bioimage.io reviewer"""

    @wraps(func)
    def wrapper(self: R, *args: P.args, **kwargs: P.kwargs):
        concept_id = self.concept_id
        assert not concept_id.endswith("/"), concept_id
        lock_path = f"{concept_id}/concept-lock"
        if list(self.client.ls(lock_path)):
            raise ValueError(f"{concept_id} is currently locked")

        self.client.put(lock_path, io.BytesIO(b" "), length=1)
        try:
            return func(self, *args, **kwargs)
        finally:
            self.client.rm(lock_path)

    return wrapper


def lock_version(
    func: Callable[Concatenate[R, P], T],
) -> Callable[Concatenate[R, P], T]:
    """method decorator to indicate that a method may only be called by a bioimage.io reviewer"""

    @wraps(func)
    def wrapper(self: R, *args: P.args, **kwargs: P.kwargs):
        concept_id = self.concept_id
        version = self.version
        lock_path = f"{concept_id}/{version}/version-lock"
        if list(self.client.ls(lock_path)):
            raise ValueError(f"{concept_id} is currently locked")

        self.client.put(lock_path, io.BytesIO(b" "), length=1)
        try:
            return func(self, *args, **kwargs)
        finally:
            self.client.rm(lock_path)

    return wrapper


@dataclass
class RemoteCollection(RemoteBase):
    """A representation of a (the) bioimage.io collection"""

    client: Client
    """Client to connect to remote storage"""

    @property
    def folder(self) -> str:
        """collection folder is given by the `client` prefix"""
        return ""

    @property
    def url(self) -> str:
        """collection.json url"""
        return ""

    @property
    def config(self) -> CollectionConfig:
        return CollectionConfig.load()

    @property
    def partner_ids(self):
        return tuple(p.id for p in self.config.partners)

    def get_concepts(self):
        return [  # general resources outside partner folders
            RecordConcept(client=self.client, concept_id=concept_id)
            for d in self.client.ls("", only_folders=True)
            if (concept_id := d.strip("/")) not in self.partner_ids
            and not d.startswith(".")
        ] + [  # resources in partner folders
            RecordConcept(client=self.client, concept_id=pid + "/" + d.strip("/"))
            for pid in self.partner_ids
            for d in self.client.ls(pid + "/", only_folders=True)
            if not d.startswith(".")
        ]

    def _select_parts(self, type_: str):
        if type_ == "model":
            return self.config.id_parts.model
        elif type_ == "dataset":
            return self.config.id_parts.dataset
        elif type_ == "notebook":
            return self.config.id_parts.notebook
        else:
            raise NotImplementedError(
                f"handling resource id for type '{type_}' is not yet implemented"
            )

    def validate_concept_id(self, concept_id: str, *, type_: str):
        """check if a concept id follows the defined pattern (not if it exists)"""
        self.config.id_parts[type_].validate_concept_id(concept_id)

    def generate_concept_id(self, type_: str):
        """generate a new, unused concept id"""
        id_parts = self.config.id_parts[type_]
        nouns = list(id_parts.nouns)
        taken = self.get_taken_concept_ids()
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

    def reserve_concept_id(self, concept_id: str):
        if concept_id in self.get_taken_concept_ids():
            raise ValueError(f"'{concept_id}' already taken")

        self._update_json(Reserved())

    def get_taken_concept_ids(self):
        return set(self.client.ls("", only_folders=True))

    def get_drafts(self):
        return [d for c in self.get_concepts() if (d := c.draft).exists()]

    def get_published_versions(self) -> List[Record]:
        return [v for rc in self.get_concepts() for v in rc.get_published_versions()]

    def generate_collection_json(
        self,
        mode: Literal["published", "draft"] = "published",
    ) -> None:
        """generate a json file with an overview of all published resources
        (also generates `versions.json` files for each research concept)
        """
        collection_output_file_name: str = (
            "collection.json" if mode == "published" else f"collection_{mode}.json"
        )
        all_versions_file_name: str = (
            "all_versions.json" if mode == "published" else f"all_versions_{mode}.json"
        )
        available_concept_ids_file_name: str = (
            "available_ids.json"
            if mode == "published"
            else f"available_ids_{mode}.json"
        )
        id_map_file_name = (
            "id_map.json" if mode == "published" else f"id_map_{mode}.json"
        )

        logger.info(
            "generating {}, {}, {}",
            collection_output_file_name,
            all_versions_file_name,
            id_map_file_name,
        )

        collection_entries: List[CollectionEntry] = []
        concepts_summaries: List[ConceptSummary] = []
        n_resource_versions: Dict[str, int] = defaultdict(lambda: 0)
        n_resources: Dict[str, int] = defaultdict(lambda: 0)
        error_in_published_entry = None
        id_map: Dict[str, IdInfo] = {}
        for rc in self.get_concepts():
            versions: Union[List[RecordDraft], List[Record]] = (
                ([rc.draft] if rc.draft.exists() else [])
                if mode == "draft"
                else rc.get_published_versions()
            )
            if not versions:
                continue

            try:
                versions_in_collection, id_map_update = create_collection_entries(
                    versions
                )
            except Exception as e:
                error_in_published_entry = f"failed to create {rc.id} entry: {e}"
                logger.error(error_in_published_entry)
            else:
                id_map.update(id_map_update)
                if versions_in_collection:
                    latest_version = versions_in_collection[0]
                    n_resources[latest_version.type] += 1
                    n_resource_versions[latest_version.type] += len(versions)
                    collection_entries.extend(versions_in_collection)
                    concepts_summaries.append(
                        ConceptSummary(
                            concept=latest_version.id,
                            type=latest_version.type,
                            concept_doi=latest_version.concept_doi,
                            versions=sorted(
                                ConceptVersion(
                                    v=v.version,
                                    created=v.info.created,
                                    doi=v.doi,
                                    source=id_map[v.id].source,
                                    sha256=id_map[v.id].sha256,
                                )
                                for v in versions
                            ),
                        )
                    )

        collection_entries.sort()
        concepts_summaries.sort()
        collection = CollectionJson(
            authors=(template := self.config.collection_template).authors,
            cite=template.cite,
            config=CollectionWebsiteConfig(
                background_image=template.config.background_image,
                default_type=template.config.default_type,
                explore_button_text=template.config.explore_button_text,
                n_resource_versions=n_resource_versions,
                n_resources=n_resources,
                partners=template.config.partners,
                resource_types=list(n_resources) or [template.config.default_type],
                splash_feature_list=template.config.splash_feature_list,
                splash_subtitle=template.config.splash_subtitle,
                splash_title=template.config.splash_title,
                url_root=pydantic.HttpUrl(self.client.get_file_url(self.folder)),
            ),
            description=template.description,
            documentation=template.documentation,
            format_version=template.format_version,
            git_repo=template.git_repo,
            icon=template.icon,
            license=template.license,
            name=template.name,
            tags=template.tags,
            type=template.type,
            version=template.version,
            collection=collection_entries,
        )

        all_versions = AllVersions(entries=concepts_summaries)
        types = ("model", "dataset", "notebook")
        taken_ids = {
            typ: {cs.concept for cs in concepts_summaries if cs.type == typ}
            for typ in types
        }
        available_concept_ids = AvailableConceptIds.model_validate(
            {
                typ: [
                    ci
                    for a, n in product(
                        self.config.id_parts[typ].adjectives,
                        self.config.id_parts[typ].nouns,
                    )
                    if (ci := f"{a}-{n}") not in taken_ids[typ]
                ]
                for typ in types
            }
        )
        # # check that this generated collection is a valid RDF itself
        # coll_descr = build_description(
        #     collection.model_dump(), context=ValidationContext(perform_io_checks=False)
        # )
        # if not isinstance(coll_descr, CollectionDescr):
        #     raise ValueError(coll_descr.validation_summary.format())

        if collection_entries or not list(self.client.ls(collection_output_file_name)):
            self.client.put_json(
                collection_output_file_name,
                collection.model_dump(
                    mode="json", exclude_defaults=mode == "published"
                ),
            )
        else:
            logger.error(
                "Skipping overriding existing {} with an empty list!",
                collection_output_file_name,
            )

        if all_versions or not list(self.client.ls(all_versions_file_name)):
            self.client.put_json(
                all_versions_file_name,
                all_versions.model_dump(mode="json", exclude_defaults=True),
            )
            self.client.put_json(
                available_concept_ids_file_name,
                available_concept_ids.model_dump(mode="json", exclude_defaults=True),
            )
        else:
            logger.error(
                "Skipping overriding existing {} with an empty list!",
                all_versions_file_name,
            )

        if id_map_file_name or not list(self.client.ls(id_map_file_name)):
            self.client.put_json(
                id_map_file_name,
                {
                    k: ii.model_dump(mode="json", exclude_defaults=True)
                    for k, ii in id_map.items()
                },
            )
        else:
            logger.error(
                "Skipping overriding existing {} with an empty mapping!",
                id_map_file_name,
            )

        # raise an error for an invalid (skipped) collection entry
        if error_in_published_entry is not None:
            raise ValueError(error_in_published_entry)

    def get_collection_json(self) -> CollectionJson:
        data = self.client.load_file("collection.json")
        assert data is not None
        collection: Dict[str, List[Dict[str, Any]]] = json.loads(data)
        assert isinstance(
            collection, dict
        )  # TODO: create typed dict for collection.json
        assert all(isinstance(k, str) for k in collection)
        assert "collection" in collection
        assert isinstance(collection["collection"], list)
        assert all(isinstance(e, dict) for e in collection["collection"])
        assert all(isinstance(k, str) for e in collection["collection"] for k in e)
        assert all("name" in e for e in collection["collection"])
        return CollectionJson(**collection)  # type: ignore


@dataclass
class RecordConcept(RemoteBase):
    """A representation of a bioimage.io resource
    (**not** a specific staged or published version of it)"""

    collection: RemoteCollection = field(init=False)
    concept_id: str

    @property
    def id(self):
        return self.concept_id

    def __post_init__(self):
        self.collection = RemoteCollection(client=self.client)

    @property
    def draft(self) -> RecordDraft:
        return RecordDraft(client=self.client, concept_id=self.id)

    def get_published_versions(self) -> List[Record]:
        """Get representations of the published version"""
        versions = [
            rec
            for v in self.client.ls(self.folder, only_folders=True)
            if (version := v.strip("/")) != "draft"
            and (
                rec := Record(client=self.client, concept_id=self.id, version=version)
            ).exists()
        ]
        versions.sort(key=lambda r: r.info.created, reverse=True)
        return versions

    @property
    def doi(self):
        """(version **un**specific) Zenodo concept DOI of the
        latest published version of this resource concept"""
        versions = self.get_published_versions()
        if versions:
            return versions[0].concept_doi
        else:
            return None


@dataclass
class RecordBase(RemoteBase, ABC):
    """Base class for a `RecordDraft` and `Record`"""

    concept_id: str
    concept: RecordConcept = field(init=False)

    def __post_init__(self):
        self.concept_id = self.concept_id.strip("/")
        assert self.concept_id, "missing concept_id"
        self.concept = RecordConcept(client=self.client, concept_id=self.concept_id)

    @property
    def collection(self):
        return self.concept.collection

    def exists(self):
        return bool(list(self.client.ls(self.rdf_path, only_files=True)))

    @property
    def rdf_path(self) -> str:
        return f"{self.folder}files/rdf.yaml"  # TODO: transition to bioimageio.yaml eventually

    def get_rdf(self) -> Dict[str, Any]:
        rdf_data = self.client.load_file(self.rdf_path)
        if rdf_data is None:
            return {}
        else:
            return yaml.load(rdf_data.decode())

    @property
    def rdf_url(self) -> str:
        """rdf.yaml download URL"""
        return self.client.get_file_url(self.rdf_path)

    @property
    def chat(self) -> Chat:
        return self._get_json(Chat)

    def add_log_entry(self, log_entry: LogEntry):
        """add a log entry"""
        self.extend_log(Log(entries=[log_entry]))

    def extend_log(
        self,
        extension: Log,
    ):
        """extend log file"""
        self._update_json(extension)

    def extend_chat(
        self,
        extension: Chat,
    ):
        """extend chat file"""
        self._update_json(extension)

    def get_uploader(self):
        rdf = self.get_rdf()
        return Uploader.model_validate(rdf["uploader"])

    def get_file_url(self, path: str):
        return self.client.get_file_url(f"{self.folder}files/{path}")

    def get_file_urls(self):
        return self.client.get_file_urls(f"{self.folder}files/")

    def get_file_paths(self):
        return [
            f"{self.folder}files/{p}" for p in self.client.ls(f"{self.folder}files/")
        ]

    def get_all_compatibility_reports(self, tool: Optional[str] = None):
        """get all compatibility reports"""
        tools = [
            d[:-5]
            for d in self.client.ls(f"{self.folder}compatibility/", only_files=True)
            if d.endswith(".json") and (tool is None or d[:-5] == tool)
        ]
        reports_data = {
            t: self.client.load_file(self.get_compatibility_report_path(t))
            for t in tools
        }
        return [
            CompatibilityReport.model_validate({**json.loads(d), "tool": t})
            for t, d in reports_data.items()
            if d is not None
        ]

    def get_compatibility_report_path(self, tool: str):
        return f"{self.folder}compatibility/{tool}.json"

    def set_compatibility_report(self, report: CompatibilityReport) -> None:
        path = self.get_compatibility_report_path(report.tool)
        self.client.put_and_cache(path, report.model_dump_json().encode())


@dataclass
class RecordDraft(RecordBase):
    """A staged resource version"""

    version: ClassVar[str] = "draft"
    doi: ClassVar[None] = None

    @property
    def folder(self) -> str:
        """The S3 (sub)prefix of this version
        (**sub**)prefix, because the client may prefix this prefix"""
        return f"{self.id}/"

    @property
    def id(self) -> str:
        return f"{self.concept_id}/draft"

    @property
    def info(self) -> DraftInfo:
        return self._get_json(DraftInfo)

    def update_info(self, update: DraftInfo):
        self._update_json(update)

    @property
    def bioimageio_url(self):
        return f"https://bioimage.io/#/?repo={self.collection.client.get_file_url('collection_draft.json')}&id={self.concept_id}"

    @property
    def concept_doi(self):
        """concept DOI of Zenodo record"""
        return self.concept.doi

    @log
    @lock_concept
    def unpack(self, package_url: str, package_zip: Optional[zipfile.ZipFile] = None):
        previous_versions = self.concept.get_published_versions()
        if not previous_versions:
            previous_rdf = None
        else:
            previous_rdf = previous_versions[0].get_rdf()

        # ensure we have a chat.json
        self.extend_chat(Chat())

        self.add_log_entry(
            LogEntry(
                message="new status: unpacking",
                details={"package_url": package_url},
            )
        )

        if package_zip is None:
            package_zip = load_from_package_url(package_url)

        file_names = set(package_zip.namelist())
        bioimageio_yaml_file_name = identify_bioimageio_yaml_file_name(file_names)

        rdf = load_rdf_from_package_zip(package_zip, bioimageio_yaml_file_name)

        if (rdf_id := rdf.get("id")) is None:
            rdf["id"] = self.concept_id
        elif rdf_id != self.concept_id:
            raise ValueError(
                f"Expected package for {self.concept_id}, "
                + f"but found id {rdf_id} in {package_url}"
            )

        if "name" not in rdf:
            raise ValueError(f"Missing 'name' in {package_url}")

        self._set_status(
            UnpackingStatus(description=f"unzipping {package_url} to {self.folder}")
        )

        collection_data = self.client.load_file("collection.json")
        assert collection_data is not None
        collection = json.loads(collection_data)
        for e in collection["collection"]:
            if e["name"] == rdf["name"]:
                if e["id"] != rdf["id"]:
                    self.add_log_entry(
                        LogEntry(
                            message=f"error: Another resource with name='{rdf['name']}' already exists ({e['id']})"
                        )
                    )
                break

        # set matching id_emoji
        rdf["id_emoji"] = self.collection.config.id_parts.get_icon(self.concept_id)
        if rdf["id_emoji"] is None:
            self.add_log_entry(
                LogEntry(message=f"error: Failed to get icon for {self.concept_id}")
            )

        if not str(rdf["id"]):
            raise ValueError(f"Invalid `id`: {rdf['id']}")

        reviewers = {r.id: r for r in self.collection.config.reviewers}
        if "uploader" in rdf:
            given_uploader_email: Any = (
                None if not is_dict(rdf["uploader"]) else rdf["uploader"].get("email")
            )
            if not isinstance(given_uploader_email, str) or not given_uploader_email:
                raise ValueError("RDF is missing `uploader.email` field.")

            if settings.bioimageio_user_id not in reviewers:
                # verify that uploader email matches bioimageio id
                req = requests.get(
                    f"https://api.github.com/search/users?q={given_uploader_email}+in:email"
                )
                req.raise_for_status()
                response = req.json()
                if response["total_count"] != 1:
                    raise ValueError(
                        "Failed to identify GitHub account of"
                        + f" '{given_uploader_email}' from `uploader.email` field."
                    )

                if settings.bioimageio_user_id != (
                    expected_user := f"github|{response['items'][0]['id']}"
                ):
                    raise ValueError(
                        f"Upload triggered by '{settings.bioimageio_user_id}',"
                        + f" but found GitHub user '{expected_user}' associated with"
                        + f" '{given_uploader_email}' specified in `uploader.email`."
                    )

        elif settings.bioimageio_user_id in reviewers:
            rdf["uploader"] = dict(
                name=reviewers[settings.bioimageio_user_id].name,
                email=reviewers[settings.bioimageio_user_id].email,
            )
        else:
            raise ValueError("RDF is missing `uploader.email` field.")

        uploader: Any = rdf["uploader"]["email"]
        if previous_rdf is not None:
            prev_authors: List[Dict[str, str]] = previous_rdf["authors"]
            prev_uploader: List[Dict[str, str]] = [previous_rdf["uploader"]]
            assert isinstance(prev_authors, list)
            prev_maintainers: List[Dict[str, str]] = (
                previous_rdf.get("maintainers", []) + prev_authors + prev_uploader
            )
            maintainer_emails = [a["email"] for a in prev_maintainers if "email" in a]
            if (
                uploader != previous_rdf.get("uploader", {}).get("email", BOT_EMAIL)
                and uploader not in maintainer_emails
                and uploader not in [r.email for r in self.collection.config.reviewers]
            ):
                raise ValueError(
                    f"uploader '{uploader}' is not a maintainer of '{self.id}'"
                    + " nor a registered bioimageio reviewer."
                )

        # clean up any previous draft files
        self.client.rm_dir(self.folder + "files/")

        # upload new draft files
        def upload(file_name: str, file_data: bytes):
            path = f"{self.folder}files/{file_name}"
            self.client.put(path, io.BytesIO(file_data), length=len(file_data))

        thumbnails = create_thumbnails(rdf, package_zip)
        config = rdf.setdefault("config", {})
        if is_dict(config):
            bioimageio_config: Any = config.setdefault("bioimageio", {})
            if is_dict(bioimageio_config):
                thumbnail_config: Any = bioimageio_config.setdefault("thumbnails", {})
                if is_dict(thumbnail_config):
                    for oname, (tname, tdata) in thumbnails.items():
                        upload(tname, tdata)
                        thumbnail_config[oname] = tname

                if rdf["id_emoji"] is not None:
                    # we have a valid new collection id
                    # remove any nickname from config.bioimageio
                    #   that may have been kept if reusing an older model
                    bioimageio_config.pop("nickname", None)
                    bioimageio_config.pop("nickname_icon", None)

        rdf_io = io.BytesIO()
        yaml.dump(rdf, rdf_io)
        rdf_data = rdf_io.getvalue()
        upload("rdf.yaml", rdf_data)

        file_names.remove(bioimageio_yaml_file_name)
        for other in {fn for fn in file_names if is_valid_bioimageio_yaml_name(fn)}:
            logger.warning("ignoring alternative rdf.yaml source '{other}'")
            file_names.remove(other)

        for file_name in file_names:
            file_data = package_zip.open(file_name).read()
            upload(file_name, file_data)

        self._set_status(UnpackedStatus())

    def set_testing_status(self, description: str):
        self._set_status(TestingStatus(description=description))

    def await_review(self):
        """set status to 'awaiting review'"""
        self._set_status(AwaitingReviewStatus())

    @reviewer_role
    def request_changes(self, reviewer: str, reason: str):
        # map reviewer id to name
        for r in self.collection.config.reviewers:
            if reviewer == r.id:
                break
        else:
            raise ValueError(reviewer)

        description = (
            f'<a href= "mailto: {r.email}"> {r.name}</a> requested changes: {reason}'
        )
        plain_description = f"{r.name} requested changes: {reason}"
        self._set_status(ChangesRequestedStatus(description=description))
        self.extend_chat(
            Chat(messages=[Message(author="system", text=plain_description)])
        )

    @log
    @reviewer_role
    @lock_concept
    def publish(self, reviewer: str) -> Record:
        """mark this staged version candidate as accepted and try to publish it"""
        # map reviewer id to name
        for r in self.collection.config.reviewers:
            if reviewer == r.id:
                reviewer = r.name
                break

        self._set_status(AcceptedStatus())
        self.extend_chat(
            Chat(
                messages=[
                    Message(
                        author="system",
                        text=f"{reviewer} accepted {self.id} {self.version}",
                    )
                ]
            )
        )

        logger.debug("Publishing {}", self.folder)

        rdf_data = self.client.load_file(self.rdf_path)
        if rdf_data is None:
            raise RuntimeError(f"Failed to load staged RDF from {self.rdf_path}")

        rdf: Dict[Any, Any] = yaml.load(rdf_data.decode())
        assert isinstance(rdf, dict)
        version = rdf.get("version", "1")
        if not isinstance(version, (int, float, str)):
            raise ValueError(f"Invalid `version`: '{version}'")
        else:
            version = str(version)
            if version in {v.version for v in self.concept.get_published_versions()}:
                raise ValueError(f"Trying to publish version '{version}' again!")

        # remember previously published concept doi
        if previous_versions := self.concept.get_published_versions():
            concept_doi = previous_versions[0].info.concept_doi
        else:
            concept_doi = None

        published = Record(
            client=self.client, concept_id=self.concept_id, version=version
        )

        # move all files
        self.client.cp_dir(self.folder, published.folder)

        # overwrite rdf.yaml with updated version_number
        stream = io.StringIO()
        yaml.dump(rdf, stream)
        rdf_data = stream.getvalue().encode()
        self.client.put(self.rdf_path, io.BytesIO(rdf_data), length=len(rdf_data))
        self.client.rm_dir(self.folder)

        published.update_info(RecordInfo(concept_doi=concept_doi))
        return published

    def _set_status(self, value: DraftStatus):
        current_status = self.info.status
        self.add_log_entry(
            LogEntry(message=f"new status: {value.description}", details=value)
        )
        if value.name == "testing" or current_status is None:
            pass
        elif value.step < current_status.step:
            logger.warning("Proceeding from {} to {}", current_status, value)

        self._update_json(DraftInfo(status=value))


@dataclass
class Record(RecordBase):
    """A representation of a published resource version"""

    version: str
    """a (semantic) version string"""

    @property
    def id(self) -> str:
        return f"{self.concept_id}/{self.version}"

    @property
    def doi(self):
        """version specific DOI of Zenodo record"""
        return self.info.doi

    @property
    def concept_doi(self):
        """concept DOI of Zenodo record"""
        return self.info.concept_doi

    @property
    def bioimageio_url(self):
        return f"https://bioimage.io/#/?id={self.concept_id}"

    @property
    def info(self) -> RecordInfo:
        return self._get_json(RecordInfo)

    def update_info(self, update: RecordInfo):
        self._update_json(update)

    def set_dois(self, *, doi: str, concept_doi: str):
        if self.doi is not None:
            raise ValueError(f"May not overwrite existing doi={self.doi} with {doi}")
        if self.concept_doi is not None:
            raise ValueError(
                f"May not overwrite existing concept_doi={self.concept_doi} with {concept_doi}"
            )

        self._update_json(RecordInfo(doi=doi, concept_doi=concept_doi))


def load_rdf_from_package_zip(
    package_zip: zipfile.ZipFile, bioimageio_yaml_file_name: str
):
    rdf: Dict[Any, Any] = yaml.load(
        package_zip.open(bioimageio_yaml_file_name).read().decode()
    )
    if not isinstance(rdf, dict):
        raise ValueError(f"Expected {bioimageio_yaml_file_name} to hold a dictionary")
    return rdf


def load_from_package_url(package_url: str):
    # Download the model zip file
    try:
        remotezip = urllib.request.urlopen(package_url)
    except Exception as e:
        raise RuntimeError(f"failed to open {package_url}: {e}")

    zipinmemory = io.BytesIO(remotezip.read())
    return zipfile.ZipFile(zipinmemory)


def draft_new_version(
    collection: RemoteCollection, package_url: str, concept_id: str = ""
) -> RecordDraft:
    """Stage the content at `package_url` as a new resource version candidate.

    Args:
        package_url: upload source
        concept_id: (optional) overwrite any resource id given in **package_url**
    """
    if not concept_id:
        package_zip = load_from_package_url(package_url)
        bioimageio_yaml_file_name = identify_bioimageio_yaml_file_name(
            package_zip.namelist()
        )
        rdf = load_rdf_from_package_zip(package_zip, bioimageio_yaml_file_name)
        concept_id = (
            found if isinstance((found := rdf.get("id")), str) and found else ""
        )
        if not concept_id:
            typ = rdf.get("type")
            if not isinstance(typ, str) or not typ:
                raise ValueError(
                    f"'`type` field of {bioimageio_yaml_file_name}' in '{package_url}'"
                    + " is missing/invalid ."
                )

            concept_id = collection.generate_concept_id(typ)

    set_gh_actions_outputs(concept_id=concept_id)
    draft = RecordDraft(collection.client, concept_id=concept_id)
    draft.unpack(package_url=package_url)
    return draft


def get_remote_resource_version(
    client: Client, concept_id: str, version: Union[int, float, str]
):
    version = str(version).strip("/")
    if version == "draft":
        rv = RecordDraft(client=client, concept_id=concept_id)
    elif version == "latest":
        versions = RecordConcept(
            client=client, concept_id=concept_id
        ).get_published_versions()
        if versions:
            rv = versions[0]
        else:
            raise ValueError(
                f"no published version of '{concept_id}' found."
                + f" Try '{concept_id}/draft' for the unpublished draft."
            )
    else:
        rv = Record(client=client, concept_id=concept_id, version=version)

    if not rv.exists():
        raise ValueError(f"'{rv.id}' not found")

    return rv


def maybe_swap_with_thumbnail(
    src: Union[Any, Dict[Any, Any], List[Any]], thumbnails: Mapping[str, str]
) -> Any:
    if isinstance(src, dict):
        src_dict: Dict[Any, Any] = src
        return {
            k: maybe_swap_with_thumbnail(v, thumbnails) for k, v in src_dict.items()
        }

    if isinstance(src, list):
        src_list: List[Any] = src
        return [maybe_swap_with_thumbnail(s, thumbnails) for s in src_list]

    if isinstance(src, str) and not src.startswith("https://"):
        clean_name = Path(src).name  # remove any leading './'
        if clean_name in thumbnails:
            return thumbnails[clean_name]
        else:
            return src

    return src


def resolve_relative_path(
    src: Union[Any, Dict[Any, Any], List[Any]], parsed_root: SplitResult
) -> Any:
    if isinstance(src, dict):
        src_dict: Dict[Any, Any] = src
        return {k: resolve_relative_path(v, parsed_root) for k, v in src_dict.items()}

    if isinstance(src, list):
        src_list: List[Any] = src
        return [resolve_relative_path(s, parsed_root) for s in src_list]

    if isinstance(src, str):
        if src.startswith("http") or src.startswith("/") or "." not in src:
            return src
        else:
            return HttpUrl(
                urlunsplit(
                    (
                        parsed_root.scheme,
                        parsed_root.netloc,
                        parsed_root.path + "/" + src,
                        parsed_root.query,
                        parsed_root.fragment,
                    )
                )
            )

    return src


def create_collection_entries(
    versions: Sequence[Union[Record, RecordDraft]],
) -> Tuple[List[CollectionEntry], IdMap]:
    """create collection entries from a single (draft) record"""
    if not versions:
        return [], {}

    rdf: Optional[Dict[str, Any]] = None
    record_version: Optional[Union[Record, RecordDraft]] = None
    concept: Optional[str] = None
    id_info: Optional[IdInfo] = None

    id_map: Dict[str, IdInfo] = {}
    version_infos: List[VersionInfo] = []
    for record_version in versions[::-1]:  # process oldest to newest
        rdf_version_data = record_version.client.load_file(record_version.rdf_path)
        if rdf_version_data is None:
            logger.error("failed to load {}", record_version.rdf_path)
            continue

        id_info = IdInfo(
            source=record_version.rdf_url,
            sha256=hashlib.sha256(rdf_version_data).hexdigest(),
        )
        id_map[record_version.id] = id_info
        id_map[record_version.concept_id] = id_info

        if record_version.doi is not None:
            id_map[record_version.doi] = id_info

        if record_version.concept_doi is not None:
            id_map[record_version.concept_doi] = id_info

        rdf = record_version.get_rdf()
        if (version_id := rdf["id"]) is not None and version_id not in id_map:
            id_map[version_id] = id_info

        if rdf["id"].startswith("10.5281/zenodo."):
            # legacy models
            concept_end = rdf["id"].rfind("/")
            concept = rdf["id"][:concept_end]
        else:
            concept = rdf["id"]

        assert concept is not None
        id_map[concept] = id_info

        version_infos.append(
            VersionInfo(
                v=record_version.version,
                created=record_version.info.created,
                doi=(
                    None
                    if isinstance(record_version, RecordDraft)
                    else record_version.info.doi
                ),
            )
        )
        compat_reports = record_version.get_all_compatibility_reports()
        compat_tests: Dict[str, List[TestSummaryEntry]] = {}
        bioimageio_status = "failed"
        for r in compat_reports:
            if r.status == "not-applicable":
                continue

            if r.tool == f"bioimageio.core_{bioimageio.core.__version__}":
                bioimageio_status = r.status

            compat_tests.setdefault(r.tool, []).append(
                TestSummaryEntry(
                    error=r.error,
                    name="compatibility check",
                    status=r.status,
                    traceback=None,
                    warnings=None,
                )
            )

        test_summary = TestSummary(
            status=bioimageio_status, tests=compat_tests
        ).model_dump(mode="json")
        record_version.client.put_yaml(
            test_summary, f"{record_version.folder}test_summary.yaml"
        )

    assert rdf is not None
    assert record_version is not None
    assert concept is not None
    assert id_info is not None

    # create an explicit entry only for the latest version
    #   (all versions are referenced under `versions`)
    # upload 'versions.json' summary
    if isinstance(record_version, Record):
        versions_info = VersionsInfo(
            concept_doi=record_version.concept_doi, versions=version_infos[::-1]
        )
        record_version.concept.client.put_json(
            f"{record_version.concept.folder}versions.json",
            versions_info.model_dump(mode="json"),
        )
        status = None
    elif isinstance(record_version, RecordDraft):
        status = record_version.info.status
    else:
        assert_never(record_version)

    try:
        # legacy nickname
        nickname = str(rdf["config"]["bioimageio"]["nickname"])
        nickname_icon = str(rdf["config"]["bioimageio"]["nickname_icon"])
    except KeyError:
        # id is nickname
        nickname = None
        nickname_icon = rdf.get("id_emoji")

    if nickname == concept:
        nickname = None

    if nickname is not None:
        id_map[nickname] = id_info

    legacy_download_count = LEGACY_DOWNLOAD_COUNTS.get(nickname or concept, 0)

    # TODO: read new download count
    download_count = "?" if legacy_download_count == 0 else legacy_download_count

    # ingest compatibility reports
    links = set(rdf.get("links", []))
    tags = set(rdf.get("tags", []))
    compat_reports = record_version.get_all_compatibility_reports()

    def get_compat_tag(tool: str):
        """make a special, derived tag for the automatic compatibility check result

        of a tool to avoid overwriting plain manual tags like 'ilastik'.
        """
        return f"{tool}-compatible"

    # remove all version unspecific tool tags
    for r in compat_reports:
        tags.discard(get_compat_tag(r.tool_wo_version))

    # update links and tags with compatible tools
    for r in compat_reports:
        if r.status == "passed":
            links.update(r.links)
            tags.add(get_compat_tag(r.tool))  # add version unspecific tag
            tags.add(get_compat_tag(r.tool_wo_version))
        else:
            tags.discard(get_compat_tag(r.tool))

    try:
        thumbnails = rdf["config"]["bioimageio"]["thumbnails"]
    except KeyError:
        thumbnails: Dict[Any, Any] = {}
    else:
        if not isinstance(thumbnails, dict):
            thumbnails = {}

    # get parsed root
    with ValidationContext(perform_io_checks=False):
        rdf_url = HttpUrl(record_version.rdf_url)

    root_url = str(rdf_url.parent)
    assert root_url == ((root := record_version.get_file_url("").strip("/"))), (
        root_url,
        root,
    )
    parsed_root = urlsplit(root_url)

    return [
        CollectionEntry(
            authors=rdf.get("authors", []),
            uploader=rdf.get("uploader", dict(email="bioimageiobot@gmail.com")),
            badges=resolve_relative_path(
                maybe_swap_with_thumbnail(rdf.get("badges", []), thumbnails),
                parsed_root,
            ),
            concept_doi=record_version.concept_doi,
            covers=resolve_relative_path(
                maybe_swap_with_thumbnail(rdf.get("covers", []), thumbnails),
                parsed_root,
            ),
            created=record_version.info.created,
            description=rdf["description"],
            download_count=download_count,
            download_url=rdf["download_url"] if "download_url" in rdf else None,
            icon=resolve_relative_path(
                maybe_swap_with_thumbnail(rdf.get("icon"), thumbnails), parsed_root
            ),
            id=concept,
            license=rdf.get("license"),
            links=list(links),
            name=rdf["name"],
            nickname_icon=nickname_icon,
            nickname=nickname,
            rdf_source=pydantic.HttpUrl(record_version.rdf_url),
            root_url=root_url,
            tags=list(tags),
            training_data=rdf["training_data"] if "training_data" in rdf else None,
            type=rdf["type"],
            source=rdf.get("source"),
            status=status,
        )
    ], id_map
