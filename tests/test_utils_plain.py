import httpx
from respx import MockRouter


def test_raise_for_status_discretely():
    from backoffice.utils_plain import raise_for_status_discretely

    token = "my_tocken"
    userinfo = "user:password"

    url = f"httpx://{userinfo}@example.com?token={token}#my_fragment"
    _ = respx_mock.get(url).mock(side_effect=httpx.NetworkError("Some error"))
    r = httpx.get(url)
    try:
        raise_for_status_discretely(r)
    except httpx.HttpError as e:
        assert token not in str(e)
        assert userinfo not in str(e)
    else:
        assert False, "httpx.RequestError not raised"
