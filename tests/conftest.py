import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from scripts.utils.s3_client import Client


@pytest.fixture(scope="session")
def client():
    from scripts.utils.s3_client import Client

    cl = Client(
        host=os.environ["S3_HOST"],
        bucket=os.environ["S3_TEST_BUCKET"],
        prefix=os.environ["S3_TEST_FOLDER"],
    )
    yield cl
    cl.rm_dir("")  # wipe s3 test folder


@pytest.fixture(scope="session")
def s3_test_folder_url(client: "Client"):
    return client.get_file_url("")


@pytest.fixture(scope="session")
def package_url():
    return os.getenv(
        "TEST_PACKAGE_URL",
        "https://uk1s3.embassy.ebi.ac.uk/public-datasets/sandbox.bioimage.io/uploads/frank-water-buffalov1.zip",
    )


@pytest.fixture(scope="session")
def package_id():
    return os.getenv("TEST_PACKAGE_ID", "frank-water-buffalo")
