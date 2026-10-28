"""Outbound email via SMTP. Returns False (never pretends) when unconfigured or failing."""
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings
from app.core.logging_config import logger


def send_email(to: str, subject: str, body: str) -> bool:
    if not settings.smtp_configured:
        return False
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = settings.SMTP_FROM, to, subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_STARTTLS:
                smtp.starttls(context=ssl.create_default_context())
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        logger.exception("Email delivery failed")
        return False
