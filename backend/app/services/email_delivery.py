"""Minimal authenticated SMTP delivery for security-sensitive email."""

import smtplib
import ssl
from email.message import EmailMessage

from app.config import (
    SMTP_FROM_EMAIL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_TIMEOUT_SECONDS,
    SMTP_USE_TLS,
    SMTP_USERNAME,
)


class EmailDeliveryError(RuntimeError):
    """Raised when a configured security email cannot be delivered."""


def email_delivery_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM_EMAIL)


def send_security_email(recipient: str, subject: str, body: str) -> None:
    if not email_delivery_configured():
        raise EmailDeliveryError("Security email delivery is not configured.")

    message = EmailMessage()
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    context = ssl.create_default_context()

    try:
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(
                SMTP_HOST,
                SMTP_PORT,
                timeout=SMTP_TIMEOUT_SECONDS,
                context=context,
            ) as client:
                if SMTP_USERNAME:
                    client.login(SMTP_USERNAME, SMTP_PASSWORD)
                client.send_message(message)
            return

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as client:
            if not SMTP_USE_TLS:
                raise EmailDeliveryError("SMTP must use STARTTLS or implicit TLS.")
            client.starttls(context=context)
            if SMTP_USERNAME:
                client.login(SMTP_USERNAME, SMTP_PASSWORD)
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("The security email could not be delivered.") from exc
