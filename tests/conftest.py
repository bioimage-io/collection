from pathlib import Path

import pytest

from bioimageio_collection_backoffice import BackOffice
from bioimageio_collection_backoffice._settings import settings
from bioimageio_collection_backoffice.s3_client import Client


@pytest.fixture(scope="session")
def backoffice():
    bo = BackOffice(
        host=settings.s3_host,
        bucket=settings.s3_bucket,
        prefix=settings.s3_pytest_folder + "/backoffice",
    )
    bo.client.rm_dir("")  # wipe s3 test folder
    yield bo
    bo.client.rm_dir("")  # wipe s3 test folder


@pytest.fixture(scope="session")
def client():
    """a client of a test instance of a bioimageio collection"""
    cl = Client(
        host=settings.s3_host,
        bucket=settings.s3_bucket,
        prefix=settings.s3_pytest_folder + "/client",
    )
    cl.rm_dir("")  # wipe s3 test folder
    yield cl
    cl.rm_dir("")  # wipe s3 test folder


@pytest.fixture(scope="session")
def non_collection_client():
    """a client fixture without implying it maintains a bioimageio collection"""
    cl = Client(
        host=settings.s3_host,
        bucket=settings.s3_bucket,
        prefix=settings.s3_pytest_folder + "/other",
    )
    cl.rm_dir("")  # wipe s3 test folder
    yield cl
    cl.rm_dir("")  # wipe s3 test folder


@pytest.fixture(scope="session")
def s3_test_folder_url(client: "Client"):
    return client.get_file_url("")


@pytest.fixture(scope="session")
def package_url():
    return settings.test_package_url


@pytest.fixture(scope="session")
def package_id():
    return settings.test_package_id


@pytest.fixture(scope="session")
def collection_template_path():
    return Path(__file__).parent.parent / "collection_template.json"
