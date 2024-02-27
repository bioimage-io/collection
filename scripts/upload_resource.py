"""This script was used internally to upload previously contributed resources to bioimage.io that were managed through the old bioimage-io/collection-bioimage-io repo"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, List, Sequence, Tuple, Union

import pooch
from bioimageio.spec import (
    InvalidDescr,
    ValidationContext,
    build_description,
    load_description,
    save_bioimageio_package,
)
from bioimageio.spec._internal.utils import get_parent_url
from bioimageio.spec.common import BioimageioYamlContent, BioimageioYamlSource, HttpUrl
from dotenv import load_dotenv
from minio import Minio
from ruyaml import YAML
from tqdm import tqdm

_ = load_dotenv()

yaml = YAML(typ="safe")
logger = logging.getLogger(__name__)

# COLLECTION_URL = "https://raw.githubusercontent.com/bioimage-io/collection-bioimage-io/gh-pages/collection.json"
COLLECTION_URL = "https://raw.githubusercontent.com/bioimage-io/collection-bioimage-io/bd814413906ad105e8732a50b51a954aae25771b/collection.json"
COLLECTION_SHA256 = "44d3bdc9120139f864a76da8669c7ad8d77fd4c09b66fb4319db826326691614"
UPLOAD_URL = "https://oc.embl.de/index.php/s/mdE3in0099rQFwW"

COLLECTION_FOLDER = (
    Path(__file__).parent.parent.parent / "collection-bioimage-io/collection"
)


@dataclass
class Client:
    host: str = os.environ["S3_HOST"]
    bucket: str = os.environ["S3_BUCKET"]
    root_folder: str = os.environ["S3_FOLDER"]
    _client: Minio = field(init=False)

    def __post_init__(self):
        self._client = Minio(
            self.host,
            access_key=os.environ["S3_ACCESS_KEY_ID"],
            secret_key=os.environ["S3_SECRET_ACCESS_KEY"],
        )
        assert self._client.bucket_exists(self.bucket)

    def put(self, path: str, file_object: BinaryIO, length: int = -1) -> None:
        # For unknown length (ie without reading file into mem) give `part_size`
        part_size = 0
        if length == -1:
            part_size = 10 * 1024 * 1024

        path = f"{self.root_folder}/{path}"
        _ = self._client.put_object(
            self.bucket,
            path,
            file_object,
            length=length,
            part_size=part_size,
        )
        logger.warning("uploaded https://%s/%s/%s", self.host, self.bucket, path)

    def upload_file(self, file: Path, upload_name: str):
        with file.open("rb") as f:
            self.put(f"uploads/{upload_name}", f)


def upload_resource(
    source: str = "rdf.yaml",
    *additional_sources: str,
):
    upload_resources([(src, Path()) for src in [source, *additional_sources]])


def upload_resources(
    sources: Sequence[Tuple[BioimageioYamlSource, Union[HttpUrl, Path]]],
):
    client = Client()
    # with TemporaryDirectory() as tmp_dir:
    tmp_dir = Path(
        (
            f"upload_tmp_{datetime.now()}".replace(":", "-")
            .replace(".", "-")
            .replace(" ", "-")
        )
    )
    upload_count = 0
    tmp_dir.mkdir()
    for i, (src, root) in enumerate(tqdm(sources)):
        out = Path(tmp_dir) / str(i)
        out.mkdir()
        with ValidationContext(root=root):
            if isinstance(src, dict):
                rd = build_description(src)
            else:
                rd = load_description(src)

            assert not isinstance(rd, InvalidDescr), rd.validation_summary.format()
            fname = f"{rd.id}_v{rd.version}.zip"
            if fname in UPLOADED:
                continue
            try:
                package = save_bioimageio_package(rd, output_path=out / fname)
            except Exception as e:
                raise ValueError(f"failed to package {root}") from e

        client.upload_file(package, fname)
        upload_count += 1

    print(f"uploaded {upload_count}")


def get_model_urls_from_collection_json():
    collection_path = Path(pooch.retrieve(COLLECTION_URL, known_hash=COLLECTION_SHA256))  # type: ignore

    with collection_path.open() as f:
        collection = json.load(f)

    return [
        entry["rdf_source"]
        for entry in collection["collection"]
        if entry["type"] == "model"
    ]


def get_model_urls_from_collection_folder(start: int = 0, end: int = 9999):
    assert COLLECTION_FOLDER.exists()
    ret: List[Tuple[BioimageioYamlContent, HttpUrl]] = []
    count = 0
    for i, resource_path in enumerate(
        sorted(COLLECTION_FOLDER.glob("**/resource.yaml"))[start:end], start=start
    ):
        logger.info("processing %d %s", i, resource_path.relative_to(COLLECTION_FOLDER))
        resource = yaml.load(resource_path)
        if resource["status"] != "accepted":
            continue

        if resource["type"] != "model":
            continue

        rdf_base = dict(resource)
        _ = rdf_base.pop("doi", None)
        _ = rdf_base.pop("owners", None)
        _ = rdf_base.pop("status", None)
        _ = rdf_base.pop("versions", None)

        nickname = rdf_base.pop("nickname")
        nickname_icon = rdf_base.pop("nickname_icon")

        v = 0
        # for version in resource["versions"][::-1]:
        version = resource["versions"][0]  # only upload latest version
        if version.pop("status", None) != "accepted":
            continue

        rdf = dict(rdf_base)
        rdf_source = version.pop("rdf_source")
        _ = version.pop("doi", None)
        _ = version.pop("version_name", None)
        version_id = version.pop("version_id", None)
        created = version.pop("created", None)
        if created is not None:
            version["timestamp"] = created

        if rdf_source.startswith("https://zenodo.org/api/files/"):
            # convert source from old zenodo api
            assert version_id is not None
            rdf_name = rdf_source.split("/")[-1]
            new_rdf_source = (
                f"https://zenodo.org/api/records/{version_id}/files/{rdf_name}/content"
            )
            logger.warning("converting %s to %s", rdf_source, new_rdf_source)
            rdf_source = new_rdf_source

        remote_update_path = Path(pooch.retrieve(rdf_source, known_hash=None))  # type: ignore
        remote_update = yaml.load(remote_update_path)
        rdf.update(remote_update)
        rdf.update(version)
        rdf["id"] = nickname
        rdf["id_emoji"] = nickname_icon

        _ = rdf.pop("download_url", None)

        v += 1
        rdf["version"] = v
        ret.append((rdf, get_parent_url(rdf_source)))
        count += 1

    return ret


UPLOADED = {
    "funny-butterfly_v1.zip",
    "committed-turkey_v1.zip",
    "pioneering-goat_v1.zip",
    "frank-water-buffalo_v1.zip",
    "decisive-panda_v1.zip",
    "greedy-shark_v1.zip",
    "lucky-fox_v1.zip",
    "humorous-owl_v1.zip",
    "affable-shark_v1.zip",
    "creative-panda_v1.zip",
    "powerful-chipmunk_v1.zip",
    "hiding-tiger_v1.zip",
    "impartial-shrimp_v1.zip",
    "kind-seashell_v1.zip",
    "polite-pig_v1.zip",
    "straightforward-crocodile_v1.zip",
    "discreet-rooster_v1.zip",
    "organized-badger_v1.zip",
    "willing-hedgehog_v1.zip",
    "wild-whale_v1.zip",
    "loyal-parrot_v1.zip",
    "conscientious-seashell_v1.zip",
    "pioneering-rhino_v1.zip",
    "passionate-t-rex_v1.zip",
    "thoughtful-turtle_v1.zip",
    "chatty-frog_v1.zip",
    "emotional-cricket_v1.zip",
    "fearless-crab_v1.zip",
    "non-judgemental-eagle_v1.zip",
    "loyal-squid_v1.zip",
    "powerful-fish_v1.zip",
    "hiding-blowfish_v1.zip",
    "shivering-raccoon_v1.zip",
    "naked-microbe_v1.zip",
    "determined-chipmunk_v1.zip",
    "independent-shrimp_v1.zip",
    "impartial-shark_v1.zip",
    "placid-llama_v1.zip",
    "joyful-deer_v1.zip",
    "nice-peacock_v1.zip",
    "easy-going-sauropod_v1.zip",
    "ambitious-sloth_v1.zip",
    "noisy-fish_v1.zip",
    "organized-cricket_v1.zip",
    "noisy-hedgehog_v1.zip",
    "amiable-crocodile_v1.zip",
    "efficient-chipmunk_v1.zip",
    "ambitious-ant_v1.zip",
    "courteous-otter_v1.zip",
    "modest-octopus_v1.zip",
    "laid-back-lobster_v1.zip",
    "determined-hedgehog_v1.zip",
}

if __name__ == "__main__":
    # model_urls = get_model_urls_from_collection_json()
    model_urls = get_model_urls_from_collection_folder(start=0)
    upload_resources(model_urls)
