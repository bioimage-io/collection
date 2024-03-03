from __future__ import annotations

import io
import urllib.request
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, Optional, Type, TypeVar

from loguru import logger
from ruyaml import YAML
from typing_extensions import assert_never

from backoffice.s3_structure.chat import Chat
from backoffice.s3_structure.log import Logs

from .s3_client import Client
from .s3_structure.versions import (
    AcceptedStatus,
    AwaitingReviewStatus,
    ChangesRequestedStatus,
    PublishedStagedStatus,
    PublishedStatus,
    PublishedVersionDetails,
    PublishNr,
    StagedVersionDetails,
    StagedVersionStatus,
    StageNr,
    SupersededStatus,
    TestingStatus,
    UnpackedStatus,
    UnpackingStatus,
    Versions,
)

yaml = YAML(typ="safe")

J = TypeVar("J", Versions, Logs, Chat)

Nr = TypeVar("Nr", StageNr, PublishNr)


@dataclass
class RemoteResource:
    """A representation of a bioimage.io resource
    (**not** a specific staged or published version of it)"""

    client: Client
    """Client to connect to remote storage"""
    id: str
    """resource identifier"""

    @property
    def folder(self) -> str:
        """The S3 (sub)prefix of this resource"""
        return self.id

    @property
    def versions_path(self) -> str:
        return f"{self.id}/versions.json"

    def get_versions(self) -> Versions:
        return self._get_json(Versions)

    def get_latest_stage_nr(self) -> Optional[StageNr]:
        versions = self.get_versions()
        if not versions.staged:
            return None
        else:
            return max(versions.staged)

    def get_latest_staged_version(self) -> Optional[StagedVersion]:
        """Get a representation of the latest staged version
        (the one with the highest stage nr)"""
        v = self.get_latest_stage_nr()
        if v is None:
            return None
        else:
            return StagedVersion(client=self.client, id=self.id, nr=v)

    def stage_new_version(self, package_url: str) -> StagedVersion:
        """Stage the content at `package_url` as a new resource version candidate."""
        nr = self.get_latest_stage_nr()
        if nr is None:
            nr = StageNr(1)

        ret = StagedVersion(client=self.client, id=self.id, nr=nr)
        ret.unpack(package_url=package_url)
        return ret

    def _get_json(self, typ: Type[J]) -> J:
        path = f"{self.folder}{type.__name__.lower()}.json"
        data = self.client.load_file(path)
        if data is None:
            return typ()
        else:
            return typ.model_validate_json(data)

    def _extend_json(
        self,
        extension: J,
    ):
        path = f"{self.folder}{extension.__class__.__name__.lower()}.json"
        logger.info("Extending {} with {}", path, extension)
        current = self._get_json(extension.__class__)
        _ = current.extend(extension)
        self.client.put_pydantic(path, current)


@dataclass
class RemoteResourceVersion(RemoteResource, Generic[Nr], ABC):
    """Base class for a resource version (`StagedVersion` or `PublishedVersion`)"""

    nr: Nr
    """version number"""

    @property
    @abstractmethod
    def version_prefix(self) -> str:
        """a prefix to distinguish independent staged and published `version` numbers"""
        pass

    @property
    def folder(self) -> str:
        """The S3 (sub)prefix of this version
        (**sub**)prefix, because the client may prefix this prefix"""
        return f"{self.id}/{self.version_prefix}{self.nr}/"

    @property
    def rdf_url(self) -> str:
        """rdf.yaml download URL"""
        return self.client.get_file_url(f"{self.folder}files/rdf.yaml")

    def get_log(self) -> Logs:
        return self._get_json(Logs)

    def get_chat(self) -> Chat:
        return self._get_json(Chat)

    def extend_log(
        self,
        extension: Logs,
    ):
        """extend log file"""
        self._extend_json(extension)


@dataclass
class StagedVersion(RemoteResourceVersion[StageNr]):
    """A staged resource version"""

    nr: StageNr
    """stage number (**not** future resource version)"""

    @property
    def version_prefix(self):
        """The 'staged/' prefix identifies the `version` as a stage number
        (opposed to a published resource version)."""
        return "staged/"

    def unpack(self, package_url: str):
        self._set_status(
            UnpackingStatus(description=f"unzipping {package_url} to {self.folder}")
        )

        # Download the model zip file
        try:
            remotezip = urllib.request.urlopen(package_url)
        except Exception:
            logger.error("failed to open {}", package_url)
            raise

        zipinmemory = io.BytesIO(remotezip.read())

        # Unzip the zip file
        zipobj = zipfile.ZipFile(zipinmemory)

        rdf = yaml.load(zipobj.open("rdf.yaml").read().decode())
        if (rdf_id := rdf.get("id")) is None:
            rdf["id"] = self.id
        elif rdf_id != self.id:
            raise ValueError(
                f"Expected package for {self.id}, "
                f"but got packaged {rdf_id} ({package_url})"
            )

        # overwrite version information
        rdf["version_nr"] = self.nr

        if rdf.get("id_emoji") is None:
            # TODO: set `id_emoji` according to id
            raise ValueError(f"RDF in {package_url} is missing `id_emoji`")

        for filename in zipobj.namelist():
            file_data = zipobj.open(filename).read()
            path = f"{self.folder}files/{filename}"
            self.client.put(path, io.BytesIO(file_data), length=len(file_data))

        self._set_status(UnpackedStatus())

    def set_testing_status(self, description: str):
        self._set_status(TestingStatus(description=description))

    def await_review(self):
        """set status to 'awaiting review'"""
        self._set_status(AwaitingReviewStatus())

    def request_changes(self, reason: str):
        self._set_status(ChangesRequestedStatus(description=reason))

    def mark_as_superseded(self, description: str, by: StageNr):
        self._set_status(SupersededStatus(description=description, by=by))

    def publish(self) -> PublishedVersion:
        """mark this staged version candidate as accepted and try to publish it"""
        self._set_status(AcceptedStatus())
        versions = self.get_versions()
        # check status of older staged versions
        for nr, details in versions.staged.items():
            if nr >= self.nr:  # ignore newer staged versions
                continue
            if isinstance(details.status, (SupersededStatus, PublishedStagedStatus)):
                pass
            elif isinstance(
                details.status,
                (
                    UnpackingStatus,
                    UnpackedStatus,
                    TestingStatus,
                    AwaitingReviewStatus,
                    ChangesRequestedStatus,
                    AcceptedStatus,
                ),
            ):
                superseded = StagedVersion(client=self.client, id=self.id, nr=nr)
                superseded.mark_as_superseded(f"Superseded by {self.nr}", self.nr)
            else:
                assert_never(details.status)

        if not versions.published:
            next_publish_nr = PublishNr(1)
        else:
            next_publish_nr = PublishNr(max(versions.published) + 1)

        logger.debug("Publishing {} as version nr {}", self.folder, next_publish_nr)

        # load rdf
        staged_rdf_path = f"{self.folder}files/rdf.yaml"
        rdf_data = self.client.load_file(staged_rdf_path)
        rdf = yaml.load(rdf_data)

        sem_ver = rdf.get("version")
        if sem_ver is not None and sem_ver in {
            v.sem_ver for v in versions.published.values()
        }:
            raise RuntimeError(f"Trying to publish {sem_ver} again!")

        ret = PublishedVersion(client=self.client, id=self.id, nr=next_publish_nr)

        # copy rdf.yaml and set version in it
        rdf["version_nr"] = ret.nr
        stream = io.StringIO()
        yaml.dump(rdf, stream)
        rdf_data = stream.read().encode()
        self.client.put(
            f"{ret.folder}files/rdf.yaml", io.BytesIO(rdf_data), length=len(rdf_data)
        )
        # self.client.rm_obj(staged_rdf_path)

        # move all other files
        self.client.cp_dir(self.folder, ret.folder)

        versions.staged[self.nr].status = PublishedStagedStatus(
            publish_nr=next_publish_nr
        )
        versions.published[next_publish_nr] = PublishedVersionDetails(
            sem_ver=sem_ver, status=PublishedStatus(stage_nr=self.nr)
        )
        self._extend_json(versions)

        # TODO: clean up staged files?
        # remove all uploaded files from this staged version
        # self.client.rm_dir(f"{self.folder}/files/")
        return ret

    def _set_status(self, value: StagedVersionStatus):
        version = self.get_versions()
        details = version.staged.setdefault(self.nr, StagedVersionDetails(status=value))
        if value.step < details.status.step:
            logger.error("Cannot proceed from {} to {}", details.status, value)
            return

        if value.step not in (details.status.step, details.status.step + 1) and not (
            details.status.name == "awaiting review" and value.name == "superseded"
        ):
            logger.warning("Proceeding from {} to {}", details.status, value)

        details.status = value
        self._extend_json(version)


@dataclass
class PublishedVersion(RemoteResourceVersion[PublishNr]):
    """A representation of a published resource version"""

    @property
    def version_prefix(self):
        """published versions do not have a prefix"""
        return ""
