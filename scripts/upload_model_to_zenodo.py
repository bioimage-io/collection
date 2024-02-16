import argparse
import logging
import os
import pprint
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urljoin, urlparse

import requests  # type: ignore
import spdx_license_list  # type: ignore

from loguru import logger  # type: ignore
from packaging.version import parse as parse_version
from ruyaml import YAML  # type: ignore
from s3_client import create_client, version_from_resource_path_or_s3
from update_status import update_status

yaml = YAML(typ="safe")

spdx_licenses = [item.id for item in spdx_license_list.LICENSES.values()]

GOOD_STATUS_CODES = (
    200,  # OK 	Request succeeded. Response included. Usually sent for GET/PUT/PATCH requests.
    201,  # Created 	Request succeeded. Response included. Usually sent for POST requests
    202,  # Accepted 	Request succeeded. Response included. Usually sent for POST requests,
    # where background processing is needed to fulfill the request.
    204,  # No Content 	Request succeeded. No response included. Usually sent for DELETE requests.
)
ACCESS_TOKEN = os.getenv("ZENODO_API_ACCESS_TOKEN")
S3_HOST = os.getenv("S3_HOST")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY_ID")
S3_SECRET_KEY = os.getenv("S3_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_FOLDER = os.getenv("S3_FOLDER")
ZENODO_URL = os.getenv("ZENODO_URL")

MAX_RDF_VERSION = parse_version("0.5.0")


logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True


def assert_good_response(response, message, info=None):
    if response.status_code not in GOOD_STATUS_CODES:
        pprint.pprint(response)
        pprint.pprint(response.content)
        if info:
            pprint.pprint(info)
        raise Exception(message)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("resource_path", help="Resource path")
    return parser


def get_args(argv: Optional[list] = None):
    """
    $Get command-line arguments
    """
    parser = create_parser()
    return parser.parse_args(argv)


def main():
    args = get_args()
    headers = {"Content-Type": "application/json"}
    params = {"access_token": ACCESS_TOKEN}

    client = create_client()
    resource_path, version = version_from_resource_path_or_s3(args.resource_path, client)

    s3_path = f"{resource_path}/{version}/files"

    # List the files at the model URL
    file_urls = client.get_file_urls(path=s3_path)
    logger.info("Using file URLs:\n{}", "\n".join((str(obj) for obj in file_urls)))

    # Create empty deposition
    response = requests.post(
        f"{ZENODO_URL}/api/deposit/depositions", params=params, json={}, headers=headers
    )
    assert_good_response(response, "Failed to create deposition")

    # Use the bucket link
    deposition_info = response.json()
    bucket_url = deposition_info["links"]["bucket"]

    rdf_text = client.load_file(Path(s3_path, "rdf.yaml"))
    rdf = yaml.load(rdf_text)
    if not isinstance(rdf, dict):
        raise Exception("Failed to load rdf.yaml from S3")

    # PUT files to the deposition
    for file_url in file_urls:
        response = put_file_from_url(file_url, bucket_url, params)
        assert_good_response(response, f"Failed to PUT file from {file_url}")

    # Report deposition URL
    deposition_id = deposition_info["id"]
    deposition_doi = deposition_info["metadata"]["prereserve_doi"]["doi"]

    docstring = rdf.get("documentation", "")
    if not docstring.startswith("http") and docstring.endswith(".md"):
        # docstring should point to one of the files present...

        # Get the file URL
        docstring = docstring.replace("./", "")
        text = client.load_file(Path(s3_path, docstring))
        # Load markdown?
        docstring = text

        # const file = this.zipPackage.files[
        # this.rdf.documentation.replace("./", "")
        # ];
        # if (file) {
        # docstring = await file.async("string"); // get markdown
        # docstring = DOMPurify.sanitize(marked(docstring));
        # }

    base_url = f"{ZENODO_URL}/record/{deposition_id}/files/"

    metadata = rdf_to_metadata(rdf, base_url, deposition_info, docstring)

    response = requests.put(
        f"{ZENODO_URL}/api/deposit/depositions/%s" % deposition_id,
        params={"access_token": ACCESS_TOKEN},
        json={"metadata": metadata},
        headers=headers,
    )
    assert_good_response(
        response, "Failed to put metadata", info={"metadata": metadata}
    )

    update_status(
        args.resource_path,
        "Would be publishing now...(but leaving as draft)",
        step=None,
        num_steps=None,
    )
    return

    response = requests.post(
        f"{ZENODO_URL}/api/deposit/depositions/%s/actions/publish" % deposition_id,
        params=params,
    )

    assert_good_response(response, "Failed to publish deposition")

    update_status(
        args.resource_path,
        f"The deposition DOI is {deposition_doi}",
        step=None,
        num_steps=None,
    )


def put_file_from_url(file_url: str, destination_url: str, params: dict) -> dict:
    """Gets a remote file and pushes it up to a destination"""
    # TODO: Can we use stream=True and pass response.raw into requests.put?
    filename = Path(urlparse(file_url).path).name
    response = requests.get(file_url)
    file_like = BytesIO(response.content)
    return put_file(file_like, filename, destination_url, params)
    # response = requests.get(file_url, stream=True)
    # return put_file(response.raw, filename, destination_url, params)


def put_file_path(path: str | Path, url: str, params: dict) -> dict:
    """PUT file to url with params, given a file-path"""
    path = Path(path)
    filename = path.name
    with path.open(mode="rb") as fileobj:
        response = put_file(fileobj, filename, url, params)
    return response


def put_file(file_object, name, url, params):
    response = requests.put(
        "%s/%s" % (url, name),
        data=file_object,
        params=params,
    )
    return response


def rdf_authors_to_metadata_creators(rdf):
    if "authors" not in rdf:
        return []
    authors = rdf["authors"]

    creators = []
    for author in authors:
        if isinstance(author, str):
            creator = {"name": author.split(";")[0], "affiliation": ""}
        else:
            creator = {
                "name": author["name"].split(";")[0],
                "affiliation": author["affiliation"],
            }
            if "orcid" in author:
                creator["orcid"] = author["orcid"]
        creators.append(creator)
    return creators


def rdf_to_metadata(
    rdf: dict,
    base_url: str,
    deposition_info: dict,
    docstring: str,
    additional_note="(Uploaded via https://bioimage.io)",
) -> dict:

    creators = rdf_authors_to_metadata_creators(rdf)
    rdf["config"]["_deposit"] = deposition_info
    url = quote_plus(f"{rdf['config']['_deposit']['id']}")
    docstring_html = ""
    if docstring:
        docstring_html = f"<p>{docstring}</p>"
    description = f"""<a href="https://bioimage.io/#/p/zenodo:{url}"><span class="label label-success">Download RDF Package</span></a><br><p>{docstring_html}</p>"""
    keywords = ["bioimage.io", "bioimage.io:" + rdf["type"]]
    related_identifiers = generate_related_identifiers_from_rdf(rdf, base_url)
    metadata = {
        "title": rdf["name"],
        "description": description,
        "access_right": "open",
        "license": rdf["license"],
        "upload_type": "other",
        "creators": creators,
        "publication_date": datetime.now().date().isoformat(),
        "keywords": keywords + rdf["tags"],
        "notes": rdf["description"] + additional_note,
        "related_identifiers": related_identifiers,
        "communities": [],
    }
    return metadata


def generate_related_identifiers_from_rdf(rdf, base_url):
    related_identifiers = []
    covers = []
    for cover in rdf.get("covers", ()):
        if not cover.startswith("http"):
            cover = urljoin(base_url, cover)
        covers.append(cover)

        related_identifiers.append(
            {
                "relation": "hasPart",  # is part of this upload
                "identifier": cover,
                "resource_type": "image-figure",
                "scheme": "url",
            }
        )

    for link in rdf.get("links", ()):
        related_identifiers.append(
            {
                "identifier": f"https://bioimage.io/#/r/{quote_plus(link)}",
                "relation": "references",  # // is referenced by this upload
                "resource_type": "other",
                "scheme": "url",
            }
        )

    #  rdf.yaml or model.yaml
    if rdf["rdf_source"].startswith("http"):
        rdf_file = rdf["rdf_source"]
    else:
        rdf_file = urljoin(base_url, rdf["rdf_source"])
    # When we update an existing deposit, make sure we save the relative link
    if rdf_file.startswith("http") and ("api/files" in rdf_file):
        rdf_file = rdf_file.split("/")
        rdf_file = rdf_file[-1]
        rdf_file = urljoin(base_url, rdf_file)

    related_identifiers.append(
        {
            "identifier": rdf_file,
            "relation": "isCompiledBy",  # // compiled/created this upload
            "resource_type": "other",
            "scheme": "url",
        }
    )

    documentation = rdf.get("documentation")
    if documentation:
        if not documentation.startswith("http"):
            documentation = urljoin(base_url, documentation)

        related_identifiers.append(
            {
                "identifier": documentation,
                "relation": "isDocumentedBy",  # is referenced by this upload
                "resource_type": "publication-technicalnote",
                "scheme": "url",
            }
        )
    return related_identifiers


if __name__ == "__main__":
    main()
