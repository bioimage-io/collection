import os
import smtplib
from email.mime.text import MIMEText
from typing import List, Union

from dotenv import load_dotenv
from loguru import logger

from backoffice.mailroom.constants import (
    BOT_EMAIL,
    REPLY_HINT,
    SMTP_PORT,
    SMTP_SERVER,
    STATUS_UPDATE_SUBJECT,
)
from backoffice.remote_resource import PublishedVersion, StagedVersion

_ = load_dotenv()


def notify_uploader(
    rv: Union[StagedVersion, PublishedVersion], subject_end: str, msg: str
):
    email, name = rv.get_uploader()
    if email is None:
        logger.error("missing uploader email for {} {}", rv.id, rv.version)
    else:
        send_email(
            subject=f"{STATUS_UPDATE_SUBJECT}{rv.id} {rv.version} {subject_end.strip()}",
            body=(
                f"Dear {name},\n"
                + f"{msg.strip()}\n"
                + "Kind regards,\n"
                + "The bioimage.io bot 🦒\n"
                + REPLY_HINT
            ),
            recipients=[email],
        )


def send_email(subject: str, body: str, recipients: List[str]):
    from_addr = BOT_EMAIL
    to_addr = ", ".join(recipients)
    msg = MIMEText(body)
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp_server:
        _ = smtp_server.login(BOT_EMAIL, os.environ["MAIL_PASSWORD"])
        _ = smtp_server.sendmail(BOT_EMAIL, recipients, msg.as_string())

    logger.info("Email '{}' sent to {}", subject, recipients)


if __name__ == "__main__":
    send_email(
        subject=STATUS_UPDATE_SUBJECT + " lazy-bug staged/2",
        body="Staged version 2 of your model 'lazy-bug' is now under review.",
        recipients=["thefynnbe@gmail.com"],
    )
