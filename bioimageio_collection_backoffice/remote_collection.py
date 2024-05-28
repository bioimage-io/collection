from __future__ import annotations

import io
import json
import random
import urllib.request
import zipfile
from abc import ABC
from collections import defaultdict
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Literal,
    NamedTuple,
    Optional,
    Sequence,
    TypeVar,
    Union,
)
from urllib.parse import urlsplit, urlunsplit

from bioimageio.spec import ValidationContext
from bioimageio.spec.common import HttpUrl
from bioimageio.spec.utils import (
    download,
    get_sha256,
    identify_bioimageio_yaml_file_name,
    is_valid_bioimageio_yaml_name,
)
from loguru import logger
from pydantic import AnyUrl
from ruyaml import YAML
from typing_extensions import Concatenate, ParamSpec

from ._thumbnails import create_thumbnails
from .collection_config import CollectionConfig
from .collection_json import CollectionEntry, CollectionJson, CollectionWebsiteConfig
from .db_structure.chat import Chat, Message
from .db_structure.log import CollectionLog, CollectionLogEntry, Log
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
)
from .mailroom.constants import BOT_EMAIL
from .remote_base import RemoteBase
from .s3_client import Client

yaml = YAML(typ="safe")

LEGACY_DOWNLOAD_COUNTS = {
    "10.5281/zenodo.10366411": 632,
    "10.5281/zenodo.10391887": 754,
    "10.5281/zenodo.10405148": 566,
    "10.5281/zenodo.10406306": 638,
    "10.5281/zenodo.10406343": 644,
    "10.5281/zenodo.10575472": 399,
    "10.5281/zenodo.10577217": 462,
    "10.5281/zenodo.10579555": 319,
    "10.5281/zenodo.10579777": 430,
    "10.5281/zenodo.10579821": 588,
    "10.5281/zenodo.10595427": 480,
    "10.5281/zenodo.10595459": 406,
    "10.5281/zenodo.10659334": 208,
    "10.5281/zenodo.10668824": 2,
    "10.5281/zenodo.11004445": 2,
    "10.5281/zenodo.5744489": 6128,
    "10.5281/zenodo.5749843": 40313,
    "10.5281/zenodo.5764892": 70601,
    "10.5281/zenodo.5817052": 35927,
    "10.5281/zenodo.5847355": 35455,
    "10.5281/zenodo.5869899": 45822,
    "10.5281/zenodo.5874741": 44942,
    "10.5281/zenodo.5874841": 40486,
    "10.5281/zenodo.5910163": 21235,
    "10.5281/zenodo.5910854": 25477,
    "10.5281/zenodo.5914248": 42990,
    "10.5281/zenodo.5940478": 3575,
    "10.5281/zenodo.6028097": 39777,
    "10.5281/zenodo.6028280": 37772,
    "10.5281/zenodo.6079314": 29530,
    "10.5281/zenodo.6200635": 37100,
    "10.5281/zenodo.6200999": 33362,
    "10.5281/zenodo.6326366": 8893,
    "10.5281/zenodo.6334383": 28176,
    "10.5281/zenodo.6334583": 24267,
    "10.5281/zenodo.6334777": 25874,
    "10.5281/zenodo.6334793": 9323,
    "10.5281/zenodo.6334881": 25850,
    "10.5281/zenodo.6338614": 54555,
    "10.5281/zenodo.6346511": 36653,
    "10.5281/zenodo.6348084": 39638,
    "10.5281/zenodo.6348728": 36554,
    "10.5281/zenodo.6383429": 30836,
    "10.5281/zenodo.6384845": 31743,
    "10.5281/zenodo.6406756": 41816,
    "10.5281/zenodo.6406803": 34761,
    "10.5281/zenodo.6518218": 2532,
    "10.5281/zenodo.6518500": 2514,
    "10.5281/zenodo.6518571": 2527,
    "10.5281/zenodo.6518890": 4217,
    "10.5281/zenodo.6554667": 2406,
    "10.5281/zenodo.6559474": 23086,
    "10.5281/zenodo.6559929": 6666,
    "10.5281/zenodo.6808325": 18747,
    "10.5281/zenodo.6811491": 23638,
    "10.5281/zenodo.6817638": 2104,
    "10.5281/zenodo.6821147": 2102,
    "10.5281/zenodo.6827058": 2161,
    "10.5281/zenodo.6865412": 20822,
    "10.5281/zenodo.7052800": 5771,
    "10.5281/zenodo.7053390": 1957,
    "10.5281/zenodo.7139022": 5364,
    "10.5281/zenodo.7254196": 3308,
    "10.5281/zenodo.7261974": 39063,
    "10.5281/zenodo.7274275": 19265,
    "10.5281/zenodo.7315440": 13995,
    "10.5281/zenodo.7372476": 21,
    "10.5281/zenodo.7380171": 12717,
    "10.5281/zenodo.7380213": 1705,
    "10.5281/zenodo.7385954": 3291,
    "10.5281/zenodo.7612115": 2356,
    "10.5281/zenodo.7614645": 12735,
    "10.5281/zenodo.7634388": 1477,
    "10.5281/zenodo.7653695": 1450,
    "10.5281/zenodo.7689187": 1343,
    "10.5281/zenodo.7772662": 12501,
    "10.5281/zenodo.7781877": 2271,
    "10.5281/zenodo.7786492": 10156,
    "10.5281/zenodo.7872357": 2474,
    "10.5281/zenodo.8064806": 6793,
    "10.5281/zenodo.8142283": 2516,
    "10.5281/zenodo.8260660": 693,
    "10.5281/zenodo.8324706": 16,
    "10.5281/zenodo.8346993": 991,
    "10.5281/zenodo.8356515": 1051,
    "10.5281/zenodo.8401064": 3556,
    "10.5281/zenodo.8419845": 5830,
    "10.5281/zenodo.8420099": 4519,
    "10.5281/zenodo.8421755": 8531,
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
        ] + [  # resources in partner folders
            RecordConcept(client=self.client, concept_id=pid + "/" + d.strip("/"))
            for pid in self.partner_ids
            for d in self.client.ls(pid + "/", only_folders=True)
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
        self.config.id_parts.select_type(type_).validate_concept_id(concept_id)

    def generate_concpet_id(self, type_: str):
        """generate a new, unused concept id"""
        id_parts = self.config.id_parts.select_type(type_)
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
        """generate a json file with an overview of all published resources"""
        output_file_name: str = (
            "collection.json" if mode == "published" else f"collection_{mode}.json"
        )
        logger.info("generating {}", output_file_name)

        entries: List[CollectionEntry] = []
        n_resource_versions: Dict[str, int] = defaultdict(lambda: 0)
        n_resources: Dict[str, int] = defaultdict(lambda: 0)
        error_in_published_entry = None
        for rc in self.get_concepts():
            versions: List[Union[RecordDraft, Record]] = (
                [rc.draft]
                if mode == "draft" and rc.draft.exists()
                else [] + rc.get_published_versions()
            )
            try:
                versions_in_collection = create_collection_entries(versions)
            except Exception as e:
                error_in_published_entry = f"failed to create {rc.id} entry: {e}"
                logger.error(error_in_published_entry)
            else:
                if versions_in_collection:
                    n_resources[versions_in_collection[0].type] += 1
                    n_resource_versions[versions_in_collection[0].type] += len(versions)
                    entries.extend(versions_in_collection)

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
                url_root=AnyUrl(self.client.get_file_url(self.folder)),
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
            collection=entries,
        )

        # # check that this generated collection is a valid RDF itself
        # coll_descr = build_description(
        #     collection.model_dump(), context=ValidationContext(perform_io_checks=False)
        # )
        # if not isinstance(coll_descr, CollectionDescr):
        #     raise ValueError(coll_descr.validation_summary.format())

        self.client.put_json(output_file_name, collection.model_dump(mode="json"))

        # raise an error for an invalid (skipped) collection entry
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
            Record(client=self.client, concept_id=self.id, version=version)
            for v in self.client.ls(self.folder, only_folders=True)
            if (version := v.strip("/")) != "draft"
        ]
        versions.sort(key=lambda r: r.info.created, reverse=True)
        return versions

    def draft_new_version(self, package_url: str) -> RecordDraft:
        """Stage the content at `package_url` as a new resource version candidate."""

        draft = self.draft
        draft.unpack(package_url=package_url)
        return draft

    @property
    def doi(self):
        """(version **un**specific) Zenodo concept DOI of the
        latest published version of this resource concept"""
        versions = self.get_published_versions()
        if versions:
            return versions[0].concept_doi
        else:
            return None


class Uploader(NamedTuple):
    email: Optional[str]
    name: str


@dataclass
class RecordBase(RemoteBase, ABC):
    """Base class for a `RemoteDraft` and `RemoteVersion`"""

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

    @property
    def rdf_url(self) -> str:
        """rdf.yaml download URL"""
        return self.client.get_file_url(self.rdf_path)

    @property
    def chat(self) -> Chat:
        return self._get_json(Chat)

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
        rdf_data = self.client.load_file(self.rdf_path)
        assert rdf_data is not None
        rdf = yaml.load(io.BytesIO(rdf_data))
        try:
            uploader = rdf["uploader"]
            email = uploader["email"]
            name = uploader.get(
                "name", f"{rdf.get('type', 'bioimage.io resource')} contributor"
            )
        except Exception as e:
            logger.error("failed to extract uploader from rdf: {}", e)
            email = None
            name = "bioimage.io resource contributor"

        return Uploader(email=email, name=name)

    def get_file_url(self, path: str):
        return self.client.get_file_url(f"{self.folder}files/{path}")

    def get_file_urls(self):
        return self.client.get_file_urls(f"{self.folder}files/")


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

    @property
    def bioimageio_url(self):
        return f"https://bioimage.io/#/?repo={self.collection.client.get_file_url('collection_draft.json')}&id={self.id}"

    @property
    def concept_doi(self):
        """concept DOI of Zenodo record"""
        return self.concept.doi

    @log
    @lock_concept
    def unpack(self, package_url: str):
        previous_versions = self.concept.get_published_versions()
        if not previous_versions:
            previous_rdf = None
        else:
            previous_rdf_data = self.client.load_file(previous_versions[0].rdf_path)
            if previous_rdf_data is None:
                raise ValueError("Failed to load previous published version's RDF")

            previous_rdf: Optional[Dict[Any, Any]] = yaml.load(
                io.BytesIO(previous_rdf_data)
            )
            assert isinstance(previous_rdf, dict)

        # ensure we have a chat.json
        self.extend_chat(Chat())

        self.extend_log(
            Log(
                collection=[
                    CollectionLog(
                        log=CollectionLogEntry(
                            message="new status: unpacking",
                            details={"package_url": package_url},
                        )
                    )
                ]
            )
        )

        # Download the model zip file
        try:
            remotezip = urllib.request.urlopen(package_url)
        except Exception as e:
            raise RuntimeError(f"failed to open {package_url}: {e}")

        zipinmemory = io.BytesIO(remotezip.read())

        # Unzip the zip file
        zipobj = zipfile.ZipFile(zipinmemory)

        file_names = set(zipobj.namelist())
        bioimageio_yaml_file_name = identify_bioimageio_yaml_file_name(file_names)

        rdf: Union[Any, Dict[Any, Any]] = yaml.load(
            zipobj.open(bioimageio_yaml_file_name).read().decode()
        )
        if not isinstance(rdf, dict):
            raise ValueError(
                f"Expected {bioimageio_yaml_file_name} to hold a dictionary"
            )

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
                    self.extend_log(
                        Log(
                            collection=[
                                CollectionLog(
                                    log=CollectionLogEntry(
                                        message=f"error: Another resource with name='{rdf['name']}' already exists ({e['id']})"
                                    )
                                )
                            ]
                        )
                    )
                break

        # set matching id_emoji
        rdf["id_emoji"] = self.collection.config.id_parts.get_icon(self.id)
        if rdf["id_emoji"] is None:
            self.extend_log(
                Log(
                    collection=[
                        CollectionLog(
                            log=CollectionLogEntry(
                                message=f"error: Failed to get icon for {self.id}"
                            )
                        )
                    ]
                )
            )

        if "id" not in rdf:
            raise ValueError("Missing `id` field")

        if not str(rdf["id"]):
            raise ValueError(f"Invalid `id`: {rdf['id']}")

        if "version" not in rdf:
            raise ValueError("Missing `version` field")

        if (
            "uploader" not in rdf
            or not isinstance(rdf["uploader"], dict)
            or "email" not in rdf["uploader"]
        ):
            raise ValueError("RDF is missing `uploader.email` field.")
        elif not isinstance(rdf["uploader"]["email"], str):
            raise ValueError("RDF has invalid `uploader.email` field.")

        uploader = rdf["uploader"]["email"]
        if previous_rdf is not None:
            prev_authors: List[Dict[str, str]] = previous_rdf["authors"]
            assert isinstance(prev_authors, list)
            prev_maintainers: List[Dict[str, str]] = (
                previous_rdf.get("maintainers", []) + prev_authors
            )
            maintainer_emails = [a["email"] for a in prev_maintainers if "email" in a]
            if (
                uploader != previous_rdf.get("uploader", {}).get("email", BOT_EMAIL)
                and uploader not in maintainer_emails
                and uploader not in [r.email for r in self.collection.config.reviewers]
            ):
                raise ValueError(
                    f"uploader '{uploader}' is not a maintainer of '{self.id}' nor a registered bioimageio reviewer."
                )

        # clean up any previous draft files
        self.client.rm_dir(self.folder + "files/")

        # upload new draft files
        def upload(file_name: str, file_data: bytes):
            path = f"{self.folder}files/{file_name}"
            self.client.put(path, io.BytesIO(file_data), length=len(file_data))

        thumbnails = create_thumbnails(rdf, zipobj)
        config = rdf.setdefault("config", {})
        if isinstance(config, dict):
            bioimageio_config: Any = config.setdefault("bioimageio", {})
            if isinstance(bioimageio_config, dict):
                thumbnail_config: Any = bioimageio_config.setdefault("thumbnails", {})
                if isinstance(thumbnail_config, dict):
                    for oname, (tname, tdata) in thumbnails.items():
                        upload(tname, tdata)
                        thumbnail_config[oname] = tname

        rdf_io = io.BytesIO()
        yaml.dump(rdf, rdf_io)
        rdf_data = rdf_io.getvalue()
        upload("rdf.yaml", rdf_data)

        file_names.remove(bioimageio_yaml_file_name)
        for other in {fn for fn in file_names if is_valid_bioimageio_yaml_name(fn)}:
            logger.warning("ignoring alternative rdf.yaml source '{other}'")
            file_names.remove(other)

        for file_name in file_names:
            file_data = zipobj.open(file_name).read()
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
                reviewer = r.name
                break

        self._set_status(ChangesRequestedStatus(description=reason))
        self.extend_chat(
            Chat(
                messages=[
                    Message(
                        author="system", text=f"{reviewer} requested changes: {reason}"
                    )
                ]
            )
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

        rdf: Union[Any, Dict[Any, Any]] = yaml.load(io.BytesIO(rdf_data))
        assert isinstance(rdf, dict)
        version = rdf.get("version")
        if version is None:
            raise ValueError("Missing `version`")
        else:
            version = str(version)
            if version in {v.version for v in self.concept.get_published_versions()}:
                raise ValueError(f"Trying to publish version '{version}' again!")

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
        return published

    def _set_status(self, value: DraftStatus):
        current_status = self.info.status
        self.extend_log(
            Log(
                collection=[
                    CollectionLog(
                        log=CollectionLogEntry(
                            message=f"set new status: {value.name}", details=value
                        )
                    )
                ]
            )
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
        return f"https://bioimage.io/#/?id={self.concept_id}/{self.version}"

    @property
    def info(self) -> RecordInfo:
        return self._get_json(RecordInfo)

    def set_dois(self, *, doi: str, concept_doi: str):
        if self.doi is not None:
            raise ValueError(f"May not overwrite existing doi={self.doi} with {doi}")
        if self.concept_doi is not None:
            raise ValueError(
                f"May not overwrite existing concept_doi={self.concept_doi} with {concept_doi}"
            )

        self._update_json(RecordInfo(doi=doi, concept_doi=concept_doi))


def get_remote_resource_version(client: Client, concept_id: str, version: str):
    version = version.strip("/")
    if version == "draft":
        rv = RecordDraft(client=client, concept_id=concept_id)
    else:
        rv = Record(client=client, concept_id=concept_id, version=version)

    if not rv.exists():
        raise ValueError(f"'{rv.id}' not found")

    return rv


def create_collection_entries(
    versions: Sequence[Union[Record, RecordDraft]],
) -> List[CollectionEntry]:
    """create collection entries from a single (draft) record"""
    if not versions:
        return []

    rv = versions[0]
    with ValidationContext(perform_io_checks=False):
        rdf_url = HttpUrl(rv.rdf_url)

    root_url = str(rdf_url.parent)
    assert root_url == (
        (
            root := (
                rv.client.get_file_url("").strip("/")
                + "/"
                + rv.folder.strip("/")
                + "/files"
            )
        )
    ), (root_url, root)
    parsed_root = urlsplit(root_url)
    rdf_path = download(rdf_url).path
    rdf: Union[Any, Dict[Any, Any]] = yaml.load(rdf_path)
    assert isinstance(rdf, dict)

    try:
        thumbnails = rdf["config"]["bioimageio"]["thumbnails"]
    except KeyError:
        thumbnails: Dict[Any, Any] = {}
    else:
        if not isinstance(thumbnails, dict):
            thumbnails = {}

    def resolve_relative_path(src: Union[Any, Dict[Any, Any], List[Any]]) -> Any:
        if isinstance(src, dict):
            return {k: resolve_relative_path(v) for k, v in src.items()}

        if isinstance(src, list):
            return [resolve_relative_path(s) for s in src]

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

    def maybe_swap_with_thumbnail(
        src: Union[Any, Dict[Any, Any], List[Any]],
    ) -> Any:
        if isinstance(src, dict):
            return {k: maybe_swap_with_thumbnail(v) for k, v in src.items()}

        if isinstance(src, list):
            return [maybe_swap_with_thumbnail(s) for s in src]

        if isinstance(src, str):
            clean_name = Path(src).name  # remove any leading './'
            if clean_name in thumbnails:
                return rv.get_file_url(thumbnails[clean_name])
            else:
                return src

        return src

    try:
        nickname = rdf["config"]["bioimageio"]["nickname"]
        nickname_icon = rdf["config"]["bioimageio"]["nickname_icon"]
    except Exception:
        nickname = rdf["id"]
        nickname_icon = rdf["id_emoji"]

    try:
        # preserve old zenodo doi for legacy records
        concept_doi = rdf["config"]["_conceptdoi"]
        download_count: Union[Literal["?"], int] = LEGACY_DOWNLOAD_COUNTS.get(
            concept_doi, "?"
        )
    except KeyError:
        concept_doi = rv.concept_doi
        download_count = "?"

    return [
        CollectionEntry(
            authors=rdf.get("authors", []),
            badges=resolve_relative_path(
                maybe_swap_with_thumbnail(rdf.get("badges", []))
            ),
            concept_doi=concept_doi,
            concept_id=rv.concept_id,
            covers=resolve_relative_path(
                maybe_swap_with_thumbnail(rdf.get("covers", []))
            ),
            created=rv.info.created,
            description=rdf["description"],
            download_count=download_count,
            download_url=rdf["download_url"] if "download_url" in rdf else None,
            icon=resolve_relative_path(
                maybe_swap_with_thumbnail(rdf["icon"])
                if "icon" in rdf
                else rdf.get("id_emoji")
            ),
            id=rdf["id"],
            license=rdf["license"],
            links=rdf.get("links", []),
            name=rdf["name"],
            nickname_icon=nickname_icon,
            nickname=nickname,
            rdf_sha256=get_sha256(rdf_path),
            rdf_source=AnyUrl(rv.rdf_url),
            root_url=root_url,
            tags=rdf.get("tags", []),
            training_data=rdf["training_data"] if "training_data" in rdf else None,
            type=rdf["type"],
            versions=[v.version for v in versions],
            dois=[v.doi for v in versions],
        )
    ]
