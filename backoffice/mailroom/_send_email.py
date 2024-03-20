import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.utils import format_datetime

from dotenv import load_dotenv
from loguru import logger

from backoffice.mailroom.constants import (
    BOT_EMAIL,
    SMTP_PORT,
    SMTP_SERVER,
    STATUS_UPDATE_SUBJECT,
)

_ = load_dotenv()


def send_email(subject: str, body: str, recipients: list[str]):
    from_addr = BOT_EMAIL
    to_addr = ", ".join(recipients)
    # message_text = (
    #     f"From: {from_addr}\n"
    #     + f"To: {to_addr}\n"
    #     + f"Subject: {subject}\n"
    #     + f"Date: {format_datetime(datetime.now().astimezone())}\n\n"
    #     + body
    # )
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
