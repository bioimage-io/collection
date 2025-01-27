from pathlib import PurePosixPath
from typing import Any, Optional, Sequence, Mapping, Literal
import sys
from io import IOBase
import json

import pydantic
import requests
from loguru import logger

from bioimageio_collection_backoffice.requests_utils import raise_for_status_discretely
from bioimageio_collection_backoffice.zenodo.metadata import ConceptId, RecordId
from bioimageio_collection_backoffice.zenodo.request_args import OpenAccessDatasetMetadataArgs, OpenAccessSoftwareMetadataArgs
from bioimageio_collection_backoffice.zenodo.response import QueriedRecord, Record, RecordQueryResponse

class Client:
    def __init__(
        self,
        *,
        session: Optional[requests.Session]=None,
        access_token: str,
        api_hostname: str,
    ) -> None:
        self.session = session or requests.Session()
        self.access_token = access_token
        self.api_hostname = api_hostname
        super().__init__()

    def _get(self, *, endpoint: PurePosixPath, params: Mapping[str, str]) -> requests.Response:
        url = f'https://{self.api_hostname}{endpoint}'
        params={
            "access_token": self.access_token,
            **params,
        }
        logger.debug(f"GET to {url}")
        logger.debug(f"PAYLOAD: {json.dumps({**params, 'access_token': '--redacted--'}, indent=4)}")
        resp = self.session.get(
            url,
            params=params,
            json={},
            headers={"Content-Type": "application/json"}
        )
        logger.debug(f"RESPONSE PAYLOAD: {json.dumps(resp.json(), indent=4)}")
        raise_for_status_discretely(resp)
        return resp

    def _send(
        self,
        *,
        method: Literal["post", "put", "delete"],
        endpoint: PurePosixPath,
        payload: pydantic.JsonValue
    ) -> requests.Response:
        url = f'https://{self.api_hostname}{endpoint}'
        logger.debug(f"{method} to {url}", file=sys.stderr)
        logger.debug(f"PAYLOAD: {json.dumps(payload, indent=4)}")
        resp = self.session.request(
            method,
            url,
            params={"access_token": self.access_token},
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"}
        )
        if resp.headers.get("Content-Type") == "application/json":
            logger.debug(f"Response: {json.dumps(resp.json(), indent=4)}")
        raise_for_status_discretely(resp)
        return resp

    def _post(self, *, endpoint: PurePosixPath, payload: pydantic.JsonValue) -> requests.Response:
        return self._send(method="post", endpoint=endpoint, payload=payload)

    def _put(self, *, endpoint: PurePosixPath, payload: pydantic.JsonValue) -> requests.Response:
        return self._send(method="put", endpoint=endpoint, payload=payload)

    def _delete(self, *, endpoint: PurePosixPath) -> requests.Response:
        return self._send(method="delete", endpoint=endpoint, payload={})

    def delete_record(self, *, record: RecordId):
        _ = self._delete(endpoint=PurePosixPath(f"/api/deposit/depositions/{record.id}"))

    def get_concept_versions(self, concept_id: Optional[ConceptId]) -> Sequence[QueriedRecord]:
        params = {"all_versions": "1"}
        if concept_id is not None:
            params["q"] = f'conceptrecid:{concept_id}'
        resp = self._get(
            endpoint=PurePosixPath('/api/records'),
            params=params,
        )
        parsed_resp = RecordQueryResponse.model_validate_json(resp.content)
        return parsed_resp.hits.hits

    def create_new_concept_version(self, concept_id: ConceptId) -> Record:
        version_ids = sorted([v.id for v in self.get_concept_versions(concept_id)])
        if len(version_ids) == 0:
            raise RuntimeError(f"A limitation of zenodo's API prevents creating new versions for concept {concept_id}")
        latest_version_id = version_ids[-1]
        resp = self._post(
            endpoint=PurePosixPath(f"/api/deposit/depositions/{latest_version_id}/actions/newversion"),
            payload={},
        )
        parsed_resp = Record.model_validate_json(resp.content)
        return parsed_resp

    def create_new_concept(self) -> Record:
        resp = self._post(endpoint=PurePosixPath('/api/deposit/depositions'), payload={})
        return Record.model_validate_json(resp.content)

    def add_metadata_to_record(
        self,
        *,
        record_id: RecordId,
        metadata: "OpenAccessSoftwareMetadataArgs | OpenAccessDatasetMetadataArgs",
    ):
        _ = self._put(
            endpoint=PurePosixPath(f'/api/deposit/depositions/{record_id}'),
            payload={"metadata": metadata.model_dump()},
        )

    def add_file_to_record(self, *, record: Record, file_name: str, data: IOBase) -> Any:
        bucket_url = record.links.bucket
        if bucket_url is None:
            raise ValueError(f"Record has no bucket url") # FIXME: should bucket really be optional?
        resp = self.session.put(
            f"{bucket_url.geturl()}/{file_name}", # FIXME: use a URL implementation instead of fstring
            data=data,
            params={"access_token": self.access_token},
        )
        if resp.headers.get("Content-Type") == "application/json":
            logger.debug(f"Response: {json.dumps(resp.json(), indent=4)}")
        raise_for_status_discretely(resp)

    def publish(self, *, record_id: RecordId) -> Record:
        resp = self._post(
            endpoint=PurePosixPath(f'/api/deposit/depositions/{record_id}/actions/publish'),
            payload={},
        )
        return Record.model_validate_json(resp.content)

