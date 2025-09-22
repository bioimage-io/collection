from pathlib import Path
from typing import Sequence

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings, extra="ignore"):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    hypha_api_token: SecretStr
    hypha_base_url: str = "https://hypha.aicell.io"
    summaries: Path = Path("summaries")
    tools: Sequence[str] = ("biapy", "bioimageio.core", "careamics", "ilastik")

    def get_hypha_headers(self):
        return {
            "Authorization": f"Bearer {self.hypha_api_token.get_secret_value()}",
            "Content-Type": "application/json",
        }


settings = Settings()  # pyright: ignore[reportCallIssue]
