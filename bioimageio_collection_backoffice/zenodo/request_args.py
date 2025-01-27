from typing import List, Optional, Literal, Any
import datetime


import pydantic

from bioimageio_collection_backoffice.zenodo.metadata import LicenseName


class RecordCreator(pydantic.BaseModel):
    name: str
    affiliation: Optional[str] = None
    orcid: Optional[str] = None
    gnd: Optional[str] = None

class _MetadataArgsBase(pydantic.BaseModel):
    title: str
    description: str
    creators: List[RecordCreator]
    keywords: Optional[List[str]]
    notes: Optional[str]
    publication_date: datetime.date
    prereserve_doi: bool

    @pydantic.field_serializer('publication_date')
    def serialize_publication_date(self, date: datetime.date, _info: Any):
        return date.isoformat()

class _SoftwareMetadataArgs(_MetadataArgsBase):
    upload_type: Literal["software"] = "software"

class _DatasetMetadataArgs(_MetadataArgsBase):
    upload_type: Literal["dataset"] = "dataset"

class _OpenAccess(pydantic.BaseModel):
    access_right: Literal["open"] = "open"
    license: LicenseName

# Subclassing and multi-inheritance was the most natural way of
# flattening fields into the metadata base class

class OpenAccessSoftwareMetadataArgs(_SoftwareMetadataArgs, _OpenAccess):
    pass

class OpenAccessDatasetMetadataArgs(_DatasetMetadataArgs, _OpenAccess):
    pass

