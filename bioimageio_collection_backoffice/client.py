from typing import Union

from .folder_client import FolderClient
from .s3_client import S3Client

Client = Union[S3Client, FolderClient]
