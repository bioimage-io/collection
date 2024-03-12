from backoffice.s3_client import Client


def test_client(client: Client):
    assert client.prefix.startswith("sandbox")
    client.put_json("test/test1.json", "test")
    client.put_json("test/dir/test2.json", "test")
    client.put_json("test/dir/test3.json", "test")
    assert set(client.ls("test/")) == {"test1.json", "dir"}
    client.mv_dir("test/", "test_b/")
    assert not set(client.ls("test/"))
    assert set(client.ls("test_b/")) == {"test1.json", "dir"}
    assert set(client.ls("test_b/dir/")) == {"test2.json", "test3.json"}
    client.rm_dir("test_b/dir/")
    assert set(client.ls("test_b/")) == {"test1.json"}
    client.rm_dir("test/")
