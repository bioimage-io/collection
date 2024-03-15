import os
from pathlib import Path

import pytest

from backoffice import BackOffice
from backoffice.s3_client import Client


@pytest.fixture(scope="session")
def backoffice():
    bo = BackOffice(
        host=os.environ["S3_HOST"],
        bucket=os.environ["S3_TEST_BUCKET"],
        prefix=os.environ["S3_TEST_FOLDER"] + "/pytest/backoffice",
    )
    bo.client.rm_dir("")  # wipe s3 test folder
    yield bo
    bo.client.rm_dir("")  # wipe s3 test folder


@pytest.fixture(scope="session")
def client():
    cl = Client(
        host=os.environ["S3_HOST"],
        bucket=os.environ["S3_TEST_BUCKET"],
        prefix=os.environ["S3_PYTEST_FOLDER"] + "/client",
    )
    cl.rm_dir("")  # wipe s3 test folder
    yield cl
    cl.rm_dir("")  # wipe s3 test folder


@pytest.fixture(scope="session")
def s3_test_folder_url(client: "Client"):
    return client.get_file_url("")


@pytest.fixture(scope="session")
def package_url():
    return os.environ["TEST_PACKAGE_URL"]


@pytest.fixture(scope="session")
def package_id():
    return os.environ["TEST_PACKAGE_ID"]


@pytest.fixture(scope="session")
def collection_template_path():
    return Path(__file__).parent.parent / "collection_template.json"
