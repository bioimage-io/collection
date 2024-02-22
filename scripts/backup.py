import os

import typer
from dotenv import load_dotenv
from loguru import logger
from utils.s3_client import Client

_ = load_dotenv()


def backup():
    """backup collection

    Returns:
        list of folders and file names backed up
    """
    client = Client()
    content_to_backup = list(client.ls(""))
    destination = os.environ["ZENODO_URL"]
    logger.error("Backup to '{}': {}", destination, content_to_backup)
    return content_to_backup


if __name__ == "__main__":
    typer.run(backup)
