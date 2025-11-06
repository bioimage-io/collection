import httpx
from respx import MockRouter


def test_raise_for_status_discretely(respx_mock: MockRouter):
    from backoffice.utils_pure import raise_for_status_discretely

    token = "my_tocken"
    userinfo = "user:password"

    url = f"httpx://{userinfo}@example.com?token={token}#my_fragment"
    _ = respx_mock.get(url).mock(
        return_value=httpx.Response(403, json={"error": "forbidden"})
    )
    r = httpx.get(url)
    try:
        raise_for_status_discretely(r)
    except httpx.HTTPError as e:
        assert token not in str(e)
        assert userinfo not in str(e)
    else:
        assert False, "httpx.HTTPError not raised"
