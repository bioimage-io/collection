from __future__ import annotations

import io
import sys
import traceback
import urllib.request
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    List,
    NamedTuple,
    Optional,
    Type,
    TypeVar,
    Union,
)

from bioimageio.spec.utils import (
    identify_bioimageio_yaml_file_name,
    is_valid_bioimageio_yaml_name,
)
from loguru import logger
from ruyaml import YAML
from typing_extensions import Concatenate, LiteralString, ParamSpec, assert_never

from ._settings import settings
from ._thumbnails import create_thumbnails
from .db_structure.chat import Chat, Message
from .db_structure.id_parts import IdParts
from .db_structure.log import (
    CollectionLog,
    Log,
)
from .db_structure.versions import (
    AcceptedStatus,
    AwaitingReviewStatus,
    ChangesRequestedStatus,
    ErrorStatus,
    PublishedStagedStatus,
    PublishedStatus,
    PublishedVersionInfo,
    PublishNumber,
    StagedVersionInfo,
    StagedVersionStatus,
    StageNumber,
    SupersededStatus,
    TestingStatus,
    UnpackedStatus,
    UnpackingStatus,
    Versions,
)
from .remote_collection import RemoteCollection
from .resource_id import validate_resource_id
from .reviewer import get_reviewers
from .s3_client import Client

yaml = YAML(typ="safe")


JsonFileT = TypeVar("JsonFileT", Versions, Log, Chat)
NumberT = TypeVar("NumberT", StageNumber, PublishNumber)
InfoT = TypeVar("InfoT", StagedVersionInfo, PublishedVersionInfo)


@dataclass
class RemoteResourceBase:
    client: Client
    """Client to connect to remote storage"""
    id: str
    """resource identifier"""

    @property
    @abstractmethod
    def folder(self) -> str: ...

    def _get_json(self, typ: Type[JsonFileT]) -> JsonFileT:
        path = self.folder + typ.file_name
        data = self.client.load_file(path)
        if data is None:
            return typ()
        else:
            return typ.model_validate_json(data)

    def _extend_json(self, extension: JsonFileT):
        path = self.folder + extension.file_name
        logger.info("Extending {} with {}", path, extension)
        current = self._get_json(extension.__class__)
        updated = current.get_updated(extension)
        self.client.put_pydantic(path, updated)


@dataclass
class ResourceConcept(RemoteResourceBase):
    """A representation of a bioimage.io resource
    (**not** a specific staged or published version of it)"""

    @property
    def folder(self) -> str:
        """The S3 (sub)prefix of this resource"""
        return f"{self.id}/"

    @property
    def versions(self) -> Versions:
        return self._get_json(Versions)

    def get_all_staged_versions(self) -> List[StagedVersion]:
        return [
            StagedVersion(client=self.client, id=self.id, number=v)
            for v in self.versions.staged
        ]

    def get_all_published_versions(self) -> List[PublishedVersion]:
        return [
            PublishedVersion(client=self.client, id=self.id, number=v)
            for v in self.versions.published
        ]

    @property
    def latest_stage_number(self) -> Optional[StageNumber]:
        if not self.versions.staged:
            return None
        else:
            return max(self.versions.staged)

    @property
    def latest_publish_number(self) -> Optional[PublishNumber]:
        if not self.versions.published:
            return None
        else:
            return max(self.versions.published)

    def get_latest_staged_version(self) -> Optional[StagedVersion]:
        """Get a representation of the latest staged version
        (the one with the highest stage number)"""
        nr = self.latest_stage_number
        if nr is None:
            return None
        else:
            return StagedVersion(client=self.client, id=self.id, number=nr)

    def get_latest_published_version(self) -> Optional[PublishedVersion]:
        """Get a representation of the latest published version
        (the one with the highest stage number)"""
        nr = self.latest_publish_number
        if nr is None:
            return None
        else:
            return PublishedVersion(client=self.client, id=self.id, number=nr)

    def stage_new_version(self, package_url: str) -> StagedVersion:
        """Stage the content at `package_url` as a new resource version candidate."""
        nr = self.latest_stage_number
        if nr is None:
            nr = StageNumber(1)
        else:
            nr = StageNumber(nr + 1)

        ret = StagedVersion(client=self.client, id=self.id, number=nr)
        ret.unpack(package_url=package_url)
        return ret

    def extend_versions(
        self,
        update: Versions,
    ):
        self._extend_json(update)

    @property
    def doi(self):
        """(version **un**specific) Zenodo concept DOI of this resource"""
        return self.versions.doi


class Uploader(NamedTuple):
    email: Optional[str]
    name: str


T = TypeVar("T")
RV = TypeVar("RV", "StagedVersion", "PublishedVersion")
P = ParamSpec("P")


def reviewer_role(
    func: Callable[Concatenate[RV, str, P], T],
) -> Callable[Concatenate[RV, str, P], T]:
    """method decorator to indicate that a method may only be called by a bioimage.io reviewer"""

    @wraps(func)
    def wrapper(self: RV, actor: str, *args: P.args, **kwargs: P.kwargs):
        if actor not in get_reviewers():
            self.report_error(f"{actor} is not allowed to trigger '{func.__name__}'")
            sys.exit(1)

        return func(self, actor, *args, **kwargs)

    return wrapper


@dataclass
class RemoteResourceVersion(RemoteResourceBase, Generic[NumberT, InfoT], ABC):
    """Base class for a resource version (`StagedVersion` or `PublishedVersion`)"""

    version_prefix: ClassVar[LiteralString] = ""
    """a prefix to distinguish independent staged and published `version` numbers"""

    number: NumberT
    """version number"""

    concept: ResourceConcept = field(init=False)

    def __post_init__(self):
        self.concept = ResourceConcept(client=self.client, id=self.id)

    @property
    def version(self) -> str:
        """version prefix + version number"""
        return self.version_prefix + str(self.number)

    @property
    @abstractmethod
    def info(self) -> InfoT: ...

    @property
    @abstractmethod
    def exists(self) -> bool: ...

    @property
    def folder(self) -> str:
        """The S3 (sub)prefix of this version
        (**sub**)prefix, because the client may prefix this prefix"""
        return f"{self.id}/{self.version_prefix}{self.number}/"

    @property
    def rdf_path(self) -> str:
        return f"{self.folder}files/bioimageio.yaml"

    @property
    def rdf_url(self) -> str:
        """rdf.yaml download URL"""
        return self.client.get_file_url(self.rdf_path)

    @property
    def log(self) -> Log:
        return self._get_json(Log)

    @property
    def chat(self) -> Chat:
        return self._get_json(Chat)

    def extend_log(
        self,
        extension: Log,
    ):
        """extend log file"""
        self._extend_json(extension)

    def extend_chat(
        self,
        extension: Chat,
    ):
        """extend chat file"""
        self._extend_json(extension)

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

    def report_error(self, msg: str):
        self.extend_log(Log(collection=[CollectionLog(log=msg)]))


@dataclass
class StagedVersion(RemoteResourceVersion[StageNumber, StagedVersionInfo]):
    """A staged resource version"""

    version_prefix: ClassVar[LiteralString] = "staged/"
    """The 'staged/' prefix identifies the `version` as a stage number
    (opposed to a published resource version)."""

    number: StageNumber
    """stage number (**not** future resource version)"""

    @property
    def info(self):
        assert self.exists
        return self.concept.versions.staged[self.number]

    def set_error_status(self, msg: str):
        info = self.concept.versions.staged.get(self.number)
        current_status = None if info is None else info.status
        if isinstance(current_status, ErrorStatus):
            logger.error("error: {}", current_status)
            return

        error_status = ErrorStatus(
            timestamp=datetime.now(),
            run_url=settings.run_url,
            message=msg,
            traceback=traceback.format_stack(),
            during=current_status,
        )
        if info is None:
            info = StagedVersionInfo(status=error_status)

        version_update = Versions(
            staged={
                self.number: StagedVersionInfo(
                    sem_ver=info.sem_ver, timestamp=info.timestamp, status=error_status
                )
            }
        )
        self.concept.extend_versions(version_update)
        return

    def unpack(self, package_url: str):
        previous_version = self.concept.get_latest_published_version()
        if previous_version is None:
            previous_rdf = None
        else:
            previous_rdf_data = self.client.load_file(previous_version.rdf_path)
            if previous_rdf_data is None:
                self.set_error_status("Failed to load previous published version's RDF")
                sys.exit(1)

            previous_rdf: Optional[Dict[Any, Any]] = yaml.load(
                io.BytesIO(previous_rdf_data)
            )
            assert isinstance(previous_rdf, dict)

        # ensure we have a chat.json
        self.extend_chat(Chat())

        # ensure we have a log.json
        self.extend_log(Log())

        # set first status (this also write versions.json)
        self._set_status(
            UnpackingStatus(description=f"unzipping {package_url} to {self.folder}")
        )

        # Download the model zip file
        try:
            remotezip = urllib.request.urlopen(package_url)
        except Exception as e:
            self.set_error_status(f"failed to open {package_url}: {e}")
            sys.exit(1)

        zipinmemory = io.BytesIO(remotezip.read())

        # Unzip the zip file
        zipobj = zipfile.ZipFile(zipinmemory)

        file_names = set(zipobj.namelist())
        bioimageio_yaml_file_name = identify_bioimageio_yaml_file_name(file_names)

        rdf: Union[Any, Dict[Any, Any]] = yaml.load(
            zipobj.open(bioimageio_yaml_file_name).read().decode()
        )
        if not isinstance(rdf, dict):
            self.set_error_status(
                f"Expected {bioimageio_yaml_file_name} to hold a dictionary"
            )
            sys.exit(1)

        if (rdf_id := rdf.get("id")) is None:
            rdf["id"] = self.id
        elif rdf_id != self.id:
            self.set_error_status(
                f"Expected package for {self.id}, "
                + f"but got packaged {rdf_id} ({package_url})"
            )
            sys.exit(1)

        if "name" not in rdf:
            self.set_error_status(f"Missing 'name' in {package_url}")
            sys.exit(1)

        collection = RemoteCollection(self.client).get_collection_json()
        for e in collection["collection"]:
            if e["name"] == rdf["name"]:
                if e["id"] != rdf["id"]:
                    self.set_error_status(
                        f"Another resource with name='{rdf['name']}' already exists ({e['id']})"
                    )
                    sys.exit(1)
                break

        # set matching id_emoji
        id_parts = IdParts.load()
        rdf["id_emoji"] = id_parts.get_icon(self.id)
        if rdf["id_emoji"] is None:
            self.set_error_status(f"Failed to get icon for {self.id}")
            sys.exit(1)

        # overwrite version information
        rdf["version_number"] = self.number

        validate_resource_id(rdf["id"], type_=rdf["type"])

        if (
            "uploader" not in rdf
            or not isinstance(rdf["uploader"], dict)
            or "email" not in rdf["uploader"]
        ):
            self.set_error_status("RDF is missing `uploader.email` field.")
            sys.exit(1)
        elif not isinstance(rdf["uploader"]["email"], str):
            self.set_error_status("RDF has invalid `uploader.email` field.")
            sys.exit(1)

        uploader = rdf["uploader"]["email"]
        if previous_rdf is not None:
            prev_authors: List[Dict[str, str]] = previous_rdf["authors"]
            assert isinstance(prev_authors, list)
            prev_maintainers: List[Dict[str, str]] = (
                previous_rdf.get("maintainers", []) + prev_authors
            )
            maintainer_emails = [a["email"] for a in prev_maintainers if "email" in a]
            if (
                uploader != previous_rdf["uploader"]["email"]
                and uploader not in maintainer_emails
                and uploader not in [r.email for r in get_reviewers().values()]
            ):
                self.set_error_status(
                    f"uploader '{uploader}' is not a maintainer of {self.id} nor a registered bioimageio reviewer."
                )
                sys.exit()

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
        upload("bioimageio.yaml", rdf_data)
        upload("rdf.yaml", rdf_data)

        file_names.remove(bioimageio_yaml_file_name)
        for other in {fn for fn in file_names if is_valid_bioimageio_yaml_name(fn)}:
            logger.warning("ignoring alternative bioimageio.yaml source '{other}'")
            file_names.remove(other)

        for file_name in file_names:
            file_data = zipobj.open(file_name).read()
            upload(file_name, file_data)

        self._set_status(UnpackedStatus())
        self.supersede_previously_staged_versions()

    @property
    def exists(self):
        return self.number in self.concept.versions.staged

    def set_testing_status(self, description: str):
        self._set_status(TestingStatus(description=description))

    def await_review(self):
        """set status to 'awaiting review'"""
        self._set_status(AwaitingReviewStatus())

    @reviewer_role
    def request_changes(self, reviewer: str, reason: str):

        reviewer = get_reviewers()[reviewer.lower()].name  # map to reviewer name
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

    def mark_as_superseded(self, description: str, by: StageNumber):  # TODO: use this!
        self._set_status(SupersededStatus(description=description, by=by))

    def supersede_previously_staged_versions(self):
        for nr, details in self.concept.versions.staged.items():
            if nr >= self.number:  # ignore newer staged versions
                continue
            if isinstance(details.status, (SupersededStatus, PublishedStagedStatus)):
                pass
            elif isinstance(
                details.status,
                (
                    ErrorStatus,
                    UnpackingStatus,
                    UnpackedStatus,
                    TestingStatus,
                    AwaitingReviewStatus,
                    ChangesRequestedStatus,
                    AcceptedStatus,
                ),
            ):
                superseded = StagedVersion(client=self.client, id=self.id, number=nr)
                superseded.mark_as_superseded(
                    f"Superseded by {self.number}", self.number
                )
            else:
                assert_never(details.status)

    @reviewer_role
    def publish(self, reviewer: str) -> PublishedVersion:
        """mark this staged version candidate as accepted and try to publish it"""
        reviewer = get_reviewers()[reviewer.lower()].name  # map to reviewer name
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
        if not self.concept.versions.published:
            next_publish_nr = PublishNumber(1)
        else:
            next_publish_nr = PublishNumber(max(self.concept.versions.published) + 1)

        logger.debug("Publishing {} as version nr {}", self.folder, next_publish_nr)

        # load rdf
        staged_rdf_path = f"{self.folder}files/bioimageio.yaml"
        rdf_data = self.client.load_file(staged_rdf_path)
        if rdf_data is None:
            self.set_error_status(f"Failed to load staged RDF from {staged_rdf_path}")
            sys.exit(1)

        rdf = yaml.load(io.BytesIO(rdf_data))

        sem_ver = rdf.get("version")
        if sem_ver is not None:
            sem_ver = str(sem_ver)
            if sem_ver in {v.sem_ver for v in self.concept.versions.published.values()}:
                self.set_error_status(f"Trying to publish {sem_ver} again!")
                sys.exit(1)

        ret = PublishedVersion(client=self.client, id=self.id, number=next_publish_nr)

        # move all files
        self.client.cp_dir(self.folder, ret.folder)

        # overwrite bioimageio.yaml and rdf.yaml with updated version_number
        rdf["version_number"] = ret.number
        stream = io.StringIO()
        yaml.dump(rdf, stream)
        rdf_data = stream.getvalue().encode()
        for fn in ("rdf.yaml", "bioimageio.yaml"):
            self.client.put(
                f"{ret.folder}files/{fn}", io.BytesIO(rdf_data), length=len(rdf_data)
            )
        # self.client.rm_obj(staged_rdf_path)

        verions_update = Versions(
            staged={
                self.number: StagedVersionInfo(
                    sem_ver=self.concept.versions.staged[self.number].sem_ver,
                    timestamp=self.concept.versions.staged[self.number].timestamp,
                    status=PublishedStagedStatus(publish_number=next_publish_nr),
                )
            },
            published={
                next_publish_nr: PublishedVersionInfo(
                    sem_ver=sem_ver,
                    status=PublishedStatus(stage_number=self.number),
                )
            },
        )
        self.concept.extend_versions(verions_update)

        # TODO: clean up staged files?
        # remove all uploaded files from this staged version
        # self.client.rm_dir(f"{self.folder}/files/")
        return ret

    def _set_status(self, value: StagedVersionStatus):
        info = self.concept.versions.staged.get(
            self.number, StagedVersionInfo(status=value)
        )
        self.extend_log(
            Log(collection=[CollectionLog(log=f"updating status to {value}")])
        )
        if value.step < info.status.step:
            self.set_error_status(f"Cannot proceed from {info.status} to {value}")
            return

        if value.step not in (info.status.step, info.status.step + 1) and not (
            info.status.name == "awaiting review" and value.name == "superseded"
        ):
            logger.warning("Proceeding from {} to {}", info.status, value)

        updated_info = info.model_copy(update=dict(status=value))
        versions_update = Versions(staged={self.number: updated_info})
        self.concept.extend_versions(versions_update)

    def lock_publish(self):
        """Creates publish lock in DB"""
        self.client.put_and_cache(self.publish_lockfile_path, b" ")

    def unlock_publish(self):
        """Releases publish lock in DB"""
        self.client.rm(self.publish_lockfile_path)

    @property
    def publish_lockfile_path(self):
        return f"{self.concept.folder}lock-publish"


@dataclass
class PublishedVersion(RemoteResourceVersion[PublishNumber, PublishedVersionInfo]):
    """A representation of a published resource version"""

    @property
    def exists(self):
        return self.number in self.concept.versions.published

    @property
    def info(self):
        return self.concept.versions.published[self.number]

    @property
    def doi(self):
        """get version specific DOI of Zenodo record"""
        return self.concept.versions.published[self.number].doi


def get_remote_resource_version(client: Client, id: str, version: str):
    if version.startswith("staged/"):
        number = int(version[len("staged/") :])
        return StagedVersion(client=client, id=id, number=StageNumber(number))
    else:
        number = int(version)
        return PublishedVersion(client=client, id=id, number=PublishNumber(number))
