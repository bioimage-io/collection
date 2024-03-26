from io import BytesIO
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Tuple, Union
from zipfile import ZipFile

from bioimageio.spec.common import FileName
from loguru import logger
from PIL import Image

THUMBNAIL_SUFFIX = ".thumbnail.png"


def create_thumbnails(
    rdf: Dict[str, Any], zip: ZipFile
) -> Dict[FileName, Tuple[FileName, bytes]]:
    covers: Union[Any, List[Any]] = rdf.get("covers")
    plan: List[Tuple[Any, Tuple[int, int]]] = []
    if isinstance(covers, list):
        plan.extend((src, (600, 340)) for src in covers)

    badges: Union[Any, List[Any]] = rdf.get("badges")
    if isinstance(badges, list):
        for badge in badges:
            if not isinstance(badge, dict):
                continue

            icon: Any = badge.get("icon")
            plan.append((icon, (320, 320)))

    plan.append((rdf.get("icon"), (320, 320)))

    thumbnails: Dict[FileName, Tuple[FileName, bytes]] = {}
    for src, size in plan:
        thumbnail = _get_thumbnail(src, zip, size)
        if thumbnail is None:
            continue

        name, thumbnail_name, data = thumbnail
        if name in thumbnails:
            if (thumbnail_name, data) != thumbnails[name]:
                logger.error("duplicated thumbnail name '{name}'")

            continue

        thumbnails[name] = (thumbnail_name, data)

    return thumbnails


def _get_thumbnail(
    src: Any, zip: ZipFile, size: Tuple[int, int]
) -> Optional[Tuple[FileName, FileName, bytes]]:
    if not isinstance(src, str) or src.endswith(THUMBNAIL_SUFFIX):
        return  # invalid or already a thumbnail

    zip_file_names = set(zip.namelist())
    if src in zip_file_names:
        src_data = zip.open(src).read()
        image_name = src
    else:
        if isinstance(src, str) and src.startswith("http"):
            logger.info("skipping thumbnail creation for remote {}", src)
        else:
            logger.error("skipping thumbnail creation for {}", src)

        return
        # try:
        #     src_download = download(src)
        # except Exception as e:
        #     logger.error("failed to download {} ({})", src, e)
        #     return

        # image_name = src_download.original_file_name
        # src_data = src_download.path.read_bytes()

    data = _downsize_image(src_data, size)
    if data is None:
        return None
    else:
        thumbnail_name = FileName(
            PurePosixPath(image_name).with_suffix(THUMBNAIL_SUFFIX).name
        )
        return (
            image_name,
            thumbnail_name,
            data,
        )


def _downsize_image(image_data: bytes, size: Tuple[int, int]) -> Optional[bytes]:
    """downsize an image"""

    try:
        with Image.open(BytesIO(image_data)) as img:
            img.thumbnail(size)
            img_bytes_io = BytesIO()
            img.save(img_bytes_io, format="PNG")
            return img_bytes_io.getvalue()
    except Exception as e:
        logger.warning(str(e))
        return None
