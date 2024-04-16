from urllib.parse import urlparse

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

    discrete_url = urlparse(response.url)
    if discrete_url.query:
        discrete_url = discrete_url._replace(query="***query*hidden***")

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
