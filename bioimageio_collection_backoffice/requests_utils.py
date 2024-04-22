from io import BytesIO
from pathlib import PurePosixPath
from typing import Any, Dict
from urllib.parse import urlparse, urlunparse

import requests


def raise_for_status_discretely(response: requests.Response):
    """Raises :class:`HTTPError`, if one occurred,
    **but** removes query from url to avoid leaking access tokens, etc.

    adapted from requests.Response.raise_for_status
    """

    http_error_msg = ""
    if isinstance(response.reason, bytes):
        # We attempt to decode utf-8 first because some servers
        # choose to localize their reason strings. If the string
        # isn't utf-8, we fall back to iso-8859-1 for all other
        # encodings. (See PR #3538)
        try:
            reason = response.reason.decode("utf-8")
        except UnicodeDecodeError:
            reason = response.reason.decode("iso-8859-1")
    else:
        reason = response.reason

    parsed_url = urlparse(response.url)
    if parsed_url.query:
        parsed_url = parsed_url._replace(query="***query*hidden***")
        discrete_url = urlunparse(parsed_url)
    else:
        discrete_url = response.url

    if 400 <= response.status_code < 500:
        http_error_msg = (
            f"{response.status_code} Client Error: {reason} for url: {discrete_url}"
        )

    elif 500 <= response.status_code < 600:
        http_error_msg = (
            f"{response.status_code} Server Error: {reason} for url: {discrete_url}"
        )

    if http_error_msg:
        raise requests.HTTPError(http_error_msg)


def put_file_from_url(
    file_url: str, destination_url: str, params: Dict[str, Any]
) -> None:
    """Gets a remote file and pushes it up to a destination"""
    filename = PurePosixPath(urlparse(file_url).path).name
    response = requests.get(file_url)
    file_like = BytesIO(response.content)
    put_file(file_like, f"{destination_url}/{filename}", params)
    # TODO: Can we use stream=True and pass response.raw into requests.put?
    #   response = requests.get(file_url, stream=True)
    #   put_file(response.raw, filename, destination_url, params)


def put_file(file_object: BytesIO, url: str, params: Dict[str, Any]):
    r = requests.put(
        url,
        data=file_object,
        params=params,
    )
    raise_for_status_discretely(r)
