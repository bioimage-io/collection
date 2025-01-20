import getpass
from typing import Literal, Optional

from loguru import logger
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings, extra="ignore"):
    """environment variables for bioimageio_collection_backoffice"""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
    )

    github_issue_nr: Optional[int] = None
    github_output: Optional[str] = None
    github_step_summary: Optional[str] = None
    """see https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/workflow-commands-for-github-actions#adding-a-job-summary"""

    collection_config: str = (
        "https://raw.githubusercontent.com/bioimage-io/collection/main/bioimageio_collection_config.json"
    )
    """collection config"""

    run_url: Optional[str] = None
    """url to logs of the current CI run"""

    s3_host: str = "uk1s3.embassy.ebi.ac.uk"
    s3_bucket: str = "public-datasets"
    s3_folder: str = f"testing.bioimage.io/{getpass.getuser()}/instance"
    s3_pytest_folder: str = f"testing.bioimage.io/{getpass.getuser()}/pytest"
    s3_sandbox_folder: str = "sandbox.bioimage.io"
    s3_test_folder: str = f"testing.bioimage.io/{getpass.getuser()}/sandbox"
    test_package_id: str = "frank-water-buffalo"
    test_package_url: str = (
        "https://uk1s3.embassy.ebi.ac.uk/public-datasets/examples.bioimage.io/frank-water-buffalo_v1.zip"
    )
    zenodo_test_url: Literal["https://sandbox.zenodo.org"] = (
        "https://sandbox.zenodo.org"
    )
    zenodo_url: Literal["https://sandbox.zenodo.org", "https://zenodo.org"] = (
        "https://sandbox.zenodo.org"
    )

    bioimageio_user_id: Optional[str] = None

    # secrets
    mail_password: SecretStr = SecretStr("")
    s3_access_key_id: SecretStr = SecretStr("")
    s3_secret_access_key: SecretStr = SecretStr("")
    zenodo_api_access_token: SecretStr = SecretStr("")
    zenodo_test_api_access_token: SecretStr = SecretStr("")
    github_pat: SecretStr = SecretStr("")


settings = Settings()
logger.info("settings: {}", settings)
