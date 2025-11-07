from pathlib import Path
from typing import Annotated, Sequence

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings, extra="ignore"):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    hypha_api_token: SecretStr
    hypha_base_url: str = "https://hypha.aicell.io"
    summaries: Path = Path("summaries")
    tools: Sequence[str] = ("biapy", "bioimageio.core", "careamics", "ilastik")

    http_timeout: int = 30
    """Timeout for HTTP requests in seconds"""

    def get_hypha_headers(self):
        return {
            "Authorization": f"Bearer {self.hypha_api_token.get_secret_value()}",
            "Content-Type": "application/json",
        }

    collection_config: Annotated[
        "HttpUrl | Path", Field(union_mode="left_to_right")
    ] = Path(__file__).parent / "../../bioimageio_collection_config.json"
    """collection config"""


settings = Settings()  # pyright: ignore[reportCallIssue]
