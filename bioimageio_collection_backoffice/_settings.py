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

    github_output: Optional[str] = None
    collection_config: str = (
        "https://raw.githubusercontent.com/bioimage-io/collection/main/bioimageio_collection_config.json"
    )
    """collection config"""

    run_url: Optional[str] = None
    """url to logs of the current CI run"""

    s3_bucket: str = "public-datasets"
    s3_folder: str = "sandbox.bioimage.io"
    s3_host: str = "uk1s3.embassy.ebi.ac.uk"
    s3_pytest_folder: str = "testing.bioimage.io/user_pytest"
    s3_sandbox_folder: str = "sandbox.bioimage.io"
    s3_test_bucket: str = "public-datasets"
    s3_test_folder: str = "testing.bioimage.io/user_sandbox"
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

    # secrets
    mail_password: SecretStr = SecretStr("")
    s3_access_key_id: SecretStr = SecretStr("")
    s3_secret_access_key: SecretStr = SecretStr("")
    zenodo_api_access_token: SecretStr = SecretStr("")
    zenodo_test_api_access_token: SecretStr = SecretStr("")
    github_pat: SecretStr = SecretStr("")


settings = Settings()
logger.info("settings: {}", settings)
