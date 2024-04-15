import email.message
import email.parser
import imaplib
from contextlib import contextmanager
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

from loguru import logger

from .._settings import settings
from ..remote_resource import get_remote_resource_version
from ..s3_client import Client
from ..s3_structure.chat import Chat, Message
from .constants import (
    BOT_EMAIL,
    IMAP_PORT,
    REPLY_HINT,
    SMTP_SERVER,
    STATUS_UPDATE_SUBJECT,
)

FORWARDED_TO_CHAT_FLAT = "forwarded-to-bioimageio-chat"


def forward_emails_to_chat(s3_client: Client, last_n_days: int):
    cutoff_datetime = datetime.now().astimezone() - timedelta(days=last_n_days)
    with _get_imap_client() as imap_client:
        _update_chats(s3_client, imap_client, cutoff_datetime)


@contextmanager
def _get_imap_client():
    imap_client = imaplib.IMAP4_SSL(SMTP_SERVER, IMAP_PORT)
    _ = imap_client.login(BOT_EMAIL, str(settings.mail_password))
    yield imap_client
    _ = imap_client.logout()


def _get_body(msg: email.message.Message):
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get("Content-Disposition"))

            # skip any text/plain (txt) attachments
            if ctype == "text/plain" and "attachment" not in cdispo:
                msg_part = part
                break
        else:
            logger.error("faild to get body from multipart message: {}", msg)
            return None
    else:
        # not multipart - i.e. plain text, no attachments, keeping fingers crossed
        msg_part = msg

    msg_bytes = msg_part.get_payload(decode=True)
    try:
        body = str(msg_bytes, "utf-8")  # pyright: ignore[reportArgumentType]
    except Exception as e:
        logger.error("failed to decode email body: {}", e)
        return None
    else:
        return body


def _update_chats(
    s3_client: Client, imap_client: imaplib.IMAP4_SSL, cutoff_datetime: datetime
):
    _ = imap_client.select("inbox")
    for msg_id, rid, rv, msg, dt in _iterate_relevant_emails(
        imap_client, cutoff_datetime
    ):
        ok, flag_data = imap_client.fetch(str(msg_id), "(FLAGS)")
        if ok != "OK" or len(flag_data) != 1:
            logger.error("failed to get flags for {}", msg_id)
            continue
        try:
            assert isinstance(flag_data[0], bytes), type(flag_data[0])
            flags = str(flag_data[0], "utf-8")
        except Exception as e:
            logger.error("failed to interprete flags '{}': {}", flag_data[0], e)
            continue

        if FORWARDED_TO_CHAT_FLAT in flags:
            continue  # already processed

        body = _get_body(msg)
        if body is None:
            continue

        sender = msg["from"]
        text = "[forwarded from email]\n" + body.replace("> " + REPLY_HINT, "").replace(
            REPLY_HINT, ""
        )
        rr = get_remote_resource_version(s3_client, rid, rv)
        if not rr.exists:
            logger.error("Cannot comment on non-existing resource {} {}", rid, rv)
            continue

        rr.extend_chat(Chat(messages=[Message(author=sender, text=text, timestamp=dt)]))
        _ = imap_client.store(str(msg_id), "+FLAGS", FORWARDED_TO_CHAT_FLAT)


def _iterate_relevant_emails(imap_client: imaplib.IMAP4_SSL, cutoff_datetime: datetime):
    for msg_id, msg, dt in _iterate_emails(imap_client, cutoff_datetime):
        subject = str(msg["subject"])
        if STATUS_UPDATE_SUBJECT not in subject:
            logger.debug("ignoring subject: '{}'", subject)
            continue

        try:
            _, id_version = subject.split(STATUS_UPDATE_SUBJECT)
            resource_id, resource_version = id_version.strip().split(" ")
        except Exception:
            logger.warning("failed to process subject: {}", subject)
            continue

        yield msg_id, resource_id, resource_version, msg, dt


def _iterate_emails(imap_client: imaplib.IMAP4_SSL, cutoff_datetime: datetime):
    data = imap_client.search(None, "ALL")
    mail_ids = data[1]
    if not mail_ids:
        return

    id_list = mail_ids[0].split()
    first_email_id = int(id_list[0])
    latest_email_id = int(id_list[-1])

    for msg_id in range(latest_email_id, first_email_id, -1):
        ok, msg_data = imap_client.fetch(str(msg_id), "(RFC822)")
        if ok != "OK":
            logger.error("failed to fetch email {}", msg_id)
            continue

        parts = [p for p in msg_data if isinstance(p, tuple)]
        if len(parts) == 0:
            logger.error("found email with without any parts")
            continue
        elif len(parts) > 1:
            logger.error(
                "found email with multiple parts. I'll only look at the first part"
            )

        _, msg_part = parts[0]

        msg = email.message_from_string(str(msg_part, "utf-8"))
        dt: Any = parsedate_to_datetime(msg["date"])
        if isinstance(dt, datetime):
            if dt < cutoff_datetime:
                break
        else:
            logger.error("failed to parse email datetime '{}'", msg["date"])

        yield msg_id, msg, dt


if __name__ == "__main__":
    forward_emails_to_chat(Client(), 7)
