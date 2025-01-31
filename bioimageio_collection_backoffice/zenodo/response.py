from typing import Sequence, Optional
from urllib.parse import urlparse, ParseResult

import pydantic

from bioimageio_collection_backoffice.zenodo.metadata import ConceptId, RecordId, ZenodoDoi

class RecordLinks(pydantic.BaseModel):
    bucket: Optional[ParseResult] = None

    @pydantic.field_validator("bucket", mode="before")
    @classmethod
    def deserialize_url(cls, raw_url: Optional[str]) -> Optional[ParseResult]:
        if raw_url is None:
            return None
        return urlparse(raw_url)

class PrereservedDoi(pydantic.BaseModel):
    doi: ZenodoDoi[RecordId]

class RecordMetadata(pydantic.BaseModel):
    prereserve_doi: PrereservedDoi

class Record(pydantic.BaseModel):
    concept_id: ConceptId = pydantic.Field(alias='conceptrecid')
    id: RecordId
    state: str
    links: RecordLinks
    metadata: RecordMetadata
    doi: Optional[ZenodoDoi[RecordId]] = None
    conceptdoi: Optional[ZenodoDoi[ConceptId]] = None

class QueriedRecordMetadata(pydantic.BaseModel):
    prereserved_doi: PrereservedDoi

# When querying zenodo, records show in a different format then when e.g. creating them
class QueriedRecord(pydantic.BaseModel):
    concept_record_id: ConceptId = pydantic.Field(alias='conceptrecid')
    id: RecordId
    state: str

class RecordQueryResult(pydantic.BaseModel):
    hits: Sequence[QueriedRecord]

class RecordQueryResponse(pydantic.BaseModel):
    hits: RecordQueryResult


