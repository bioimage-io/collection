import smtplib
from email.mime.text import MIMEText
from typing import List, Union

import markdown
from loguru import logger

from bioimageio_collection_backoffice._settings import settings
from bioimageio_collection_backoffice.mailroom.constants import (
    BOT_EMAIL,
    REPLY_HINT,
    SMTP_PORT,
    SMTP_SERVER,
    STATUS_UPDATE_SUBJECT,
)
from bioimageio_collection_backoffice.remote_collection import (
    Record,
    RecordDraft,
)


def notify_uploader(rv: Union[RecordDraft, Record], subject_end: str, msg: str):
    email, name = rv.get_uploader()
    if email is None:
        raise ValueError("missing uploader email")

    subject = f"{STATUS_UPDATE_SUBJECT}{rv.id} {rv.version} {subject_end.strip()}"
    if email == BOT_EMAIL:
        logger.info("skipping email '{}' to {}", subject, BOT_EMAIL)
        return

    send_email(
        subject=subject,
        body=(
            f"Dear {name},\n"
            + f"{msg.strip()}\n"
            + "Kind regards,\n"
            + "The bioimage.io bot 🦒\n"
            + REPLY_HINT
        ).replace(
            "\n", "\n\n"  # respect newlines in markdown
        ),
        recipients=[email],
    )


def send_email(subject: str, body: str, recipients: List[str]):
    from_addr = BOT_EMAIL
    to_addr = ", ".join(recipients)
    body_html = markdown.markdown(body)
    msg = MIMEText(body_html, "html")
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp_server:
        _ = smtp_server.login(BOT_EMAIL, settings.mail_password.get_secret_value())
        _ = smtp_server.sendmail(BOT_EMAIL, recipients, msg.as_string())

    logger.info("Email '{}' sent to {}", subject, recipients)


if __name__ == "__main__":
    # send_email(
    #     subject=STATUS_UPDATE_SUBJECT + " lazy-bug draft",
    #     body="Staged draft version of your model 'lazy-bug' is now under review.",
    #     recipients=["bioimageiobot@gmail.com"],
    # )

    send_email(
        subject="something is awaiting review ⌛",
        body=(
            "Dear,\n"
            + "Thank you for proposing [this](https://bioimage.io/#/?repo=https%3A%2F%2Fuk1s3.embassy.ebi.ac.uk%2Fpublic-datasets%2Fbioimage.io%2Fcollection_staged.json&id=faithful-chicken)!\n"
            + "Our maintainers will take a look shortly!"
            + "Kind regards,\n"
            + "The bioimage.io bot 🦒\n"
        ),
        recipients=["bioimageiobot@gmail.com"],
    )
