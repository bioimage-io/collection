from dotenv import load_dotenv
from loguru import logger

from backoffice.s3_client import Client

_ = load_dotenv()


def backup(client: Client, destination: str):
    """backup collection

    Returns:
        list of folders and file names backed up
    """
    content_to_backup = list(client.ls(""))
    logger.error("Not implemented: Backup to '{}': {}", destination, content_to_backup)
    return content_to_backup
